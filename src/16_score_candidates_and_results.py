"""

Purpose:
    Build, score, and export candidate coordinated groups for a given split.

Where to place:
    ruby_coordination_task/src/16_score_candidates_and_results.py

What it does:
    1. Loads data/<split>/posts.jsonl and embeddings.parquet.
    2. Generates candidate groups from shared co-activity keys:
       hashtags, urls, mentions, reply_to_post_id, thread_id, quoted_post_id.
    3. Computes evidence features:
       - number of posts
       - number of accounts
       - time span
       - semantic/content similarity using cosine similarity over embeddings
       - target specificity
       - crowd penalty
    4. Produces a coordination_score.
    5. Removes duplicate/overlapping groups.
    6. Writes:
       outputs/<split>/scored_candidate_groups.csv
       outputs/<split>/results.json

Run from project root:
    python src/16_score_candidates_and_results.py --split dev
    python src/16_score_candidates_and_results.py --split eval

Recommended final eval command:
    python src/16_score_candidates_and_results.py --split eval --min-score 0.50 --max-results 150
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


LIST_FIELDS = {
    "hashtag": "hashtags",
    "url": "urls",
    "mention": "mentions",
}

SINGLE_FIELDS = {
    "reply_to_post_id": "reply_to_post_id",
    "thread_id": "thread_id",
    "quoted_post_id": "quoted_post_id",
}

# These defaults keep the pipeline simple and explainable.
MIN_POSTS = 3
MIN_ACCOUNTS = 3
MAX_POSTS_FOR_SIMILARITY = 80
MAX_GROUP_SIZE_FOR_OUTPUT = 300


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------

def load_posts(data_dir: Path) -> pd.DataFrame:
    posts_path = data_dir / "posts.jsonl"
    if not posts_path.exists():
        raise FileNotFoundError(f"Could not find {posts_path}")

    posts = pd.read_json(posts_path, lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")
    return posts


def load_embeddings(data_dir: Path) -> Dict[str, np.ndarray]:
    """
    Loads embeddings and returns {post_id: vector}.

    Handles both common formats:
      - post_id + vector column such as 'embedding' or 'vector'
      - post_id + many numeric dimension columns
    """
    emb_path = data_dir / "embeddings.parquet"
    if not emb_path.exists():
        raise FileNotFoundError(f"Could not find {emb_path}")

    emb = pd.read_parquet(emb_path)

    if "post_id" not in emb.columns:
        raise ValueError("embeddings.parquet must contain a 'post_id' column")

    vector_col = None
    for candidate in ["embedding", "vector", "embeddings"]:
        if candidate in emb.columns:
            vector_col = candidate
            break

    embedding_map: Dict[str, np.ndarray] = {}

    if vector_col is not None:
        for _, row in emb[["post_id", vector_col]].iterrows():
            embedding_map[str(row["post_id"])] = np.asarray(row[vector_col], dtype=np.float32)
        return embedding_map

    numeric_cols = [
        col for col in emb.columns
        if col != "post_id" and pd.api.types.is_numeric_dtype(emb[col])
    ]

    if not numeric_cols:
        raise ValueError("Could not identify embedding vector columns in embeddings.parquet")

    vectors = emb[numeric_cols].to_numpy(dtype=np.float32)
    post_ids = emb["post_id"].astype(str).to_numpy()

    for post_id, vec in zip(post_ids, vectors):
        embedding_map[post_id] = vec

    return embedding_map


# ---------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------

def clean_key_value(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def add_candidate_event(
    rows: List[dict],
    key_type: str,
    key_value: str,
    post_id: str,
    account_id: str,
    created_at,
) -> None:
    key_value = clean_key_value(key_value)
    if not key_value:
        return

    rows.append({
        "key_type": key_type,
        "key_value": key_value,
        "post_id": str(post_id),
        "account_id": str(account_id),
        "created_at": created_at,
    })


def build_candidate_events(posts: pd.DataFrame) -> pd.DataFrame:
    """
    Converts posts into candidate-event rows:
        one row = one post belongs to one shared co-activity key.
    """
    rows: List[dict] = []

    for _, row in posts.iterrows():
        post_id = row["post_id"]
        account_id = row["account_id"]
        created_at = row["created_at"]

        for key_type, field in LIST_FIELDS.items():
            values = row.get(field)
            if isinstance(values, list):
                for value in values:
                    add_candidate_event(rows, key_type, value, post_id, account_id, created_at)

        for key_type, field in SINGLE_FIELDS.items():
            value = row.get(field)
            add_candidate_event(rows, key_type, value, post_id, account_id, created_at)

    return pd.DataFrame(rows)


def summarise_candidates(candidate_events: pd.DataFrame) -> pd.DataFrame:
    """
    Creates one row per candidate group.
    """
    rows: List[dict] = []

    if len(candidate_events) == 0:
        return pd.DataFrame()

    for (key_type, key_value), group in candidate_events.groupby(["key_type", "key_value"]):
        post_ids = group["post_id"].drop_duplicates().tolist()
        account_ids = group["account_id"].drop_duplicates().tolist()

        post_count = len(post_ids)
        account_count = len(account_ids)

        if post_count < MIN_POSTS or account_count < MIN_ACCOUNTS:
            continue

        start_time = group["created_at"].min()
        end_time = group["created_at"].max()

        if pd.isna(start_time) or pd.isna(end_time):
            time_span_minutes = np.nan
        else:
            time_span_minutes = (end_time - start_time).total_seconds() / 60

        rows.append({
            "key_type": key_type,
            "key_value": key_value,
            "post_count": post_count,
            "account_count": account_count,
            "time_span_minutes": time_span_minutes,
            "first_time": str(start_time),
            "last_time": str(end_time),
            "post_ids": post_ids,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Similarity features
# ---------------------------------------------------------------------

def choose_even_sample(items: Sequence[str], max_items: int) -> List[str]:
    items = list(items)
    if len(items) <= max_items:
        return items
    indices = np.linspace(0, len(items) - 1, max_items).round().astype(int)
    return [items[i] for i in indices]


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    if len(vectors) == 0:
        return np.empty((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit_vectors = vectors / norms
    return unit_vectors @ unit_vectors.T


def similarity_features(post_ids: Sequence[str], embedding_map: Dict[str, np.ndarray]) -> dict:
    sampled_ids = choose_even_sample(post_ids, MAX_POSTS_FOR_SIMILARITY)

    vectors = []
    for post_id in sampled_ids:
        vec = embedding_map.get(str(post_id))
        if vec is not None:
            vectors.append(vec)

    if len(vectors) < 2:
        return {
            "avg_cosine_similarity": np.nan,
            "max_cosine_similarity": np.nan,
            "share_pairs_above_080": np.nan,
            "similarity_posts_used": len(vectors),
        }

    matrix = cosine_similarity_matrix(np.vstack(vectors).astype(np.float32))
    upper = matrix[np.triu_indices_from(matrix, k=1)]

    return {
        "avg_cosine_similarity": float(np.mean(upper)),
        "max_cosine_similarity": float(np.max(upper)),
        "share_pairs_above_080": float(np.mean(upper >= 0.80)),
        "similarity_posts_used": int(len(vectors)),
    }


# ---------------------------------------------------------------------
# Scoring logic
# ---------------------------------------------------------------------

def target_weight(key_type: str, post_count: int, account_count: int) -> float:
    """
    Specific targets are stronger than broad crowd keys.
    """
    if key_type == "url":
        return 1.00
    if key_type == "quoted_post_id":
        return 0.95
    if key_type == "reply_to_post_id":
        return 0.90
    if key_type == "thread_id":
        return 0.75
    if key_type == "mention":
        # Very large mentions are often public pile-ons or broad attention.
        return 0.45 if (post_count >= 75 or account_count >= 50) else 0.65
    if key_type == "hashtag":
        return 0.30
    return 0.50


def time_burst_score(time_span_minutes: Optional[float]) -> float:
    if time_span_minutes is None or pd.isna(time_span_minutes):
        return 0.0
    if time_span_minutes <= 10:
        return 1.00
    if time_span_minutes <= 60:
        return 0.90
    if time_span_minutes <= 6 * 60:
        return 0.75
    if time_span_minutes <= 24 * 60:
        return 0.60
    if time_span_minutes <= 7 * 24 * 60:
        return 0.35
    if time_span_minutes <= 30 * 24 * 60:
        return 0.20
    return 0.05


def similarity_score(avg_similarity: Optional[float]) -> float:
    if avg_similarity is None or pd.isna(avg_similarity):
        return 0.0
    # Values below about 0.35 are weak for this use-case.
    return float(np.clip((avg_similarity - 0.35) / 0.55, 0, 1))


def account_diversity_score(post_count: int, account_count: int) -> float:
    if post_count <= 0 or account_count < 3:
        return 0.0
    diversity = account_count / max(post_count, 1)
    size_bonus = min(account_count / 10.0, 1.0)
    return float(0.5 * min(diversity, 1.0) + 0.5 * size_bonus)


def crowd_penalty(
    key_type: str,
    post_count: int,
    account_count: int,
    time_span_minutes: Optional[float],
    avg_similarity: Optional[float],
) -> float:
    """
    Penalises groups that look like broad organic crowds.
    """
    penalty = 0.0

    days = None
    if time_span_minutes is not None and not pd.isna(time_span_minutes):
        days = time_span_minutes / (24 * 60)

    if key_type == "hashtag":
        penalty += 0.25

    if key_type == "mention" and (post_count >= 75 or account_count >= 50):
        penalty += 0.20

    if days is not None and days > 30:
        penalty += 0.20

    if post_count >= 100 and (pd.isna(avg_similarity) or avg_similarity < 0.65):
        penalty += 0.20

    if account_count < 3:
        penalty += 0.50

    return float(min(penalty, 0.75))


def coordination_score(row: pd.Series) -> float:
    key_type = row["key_type"]
    post_count = int(row["post_count"])
    account_count = int(row["account_count"])
    time_span_minutes = row["time_span_minutes"]
    avg_similarity = row["avg_cosine_similarity"]

    tw = target_weight(key_type, post_count, account_count)
    tb = time_burst_score(time_span_minutes)
    sim = similarity_score(avg_similarity)
    div = account_diversity_score(post_count, account_count)
    pen = crowd_penalty(key_type, post_count, account_count, time_span_minutes, avg_similarity)

    score = (
        0.30 * sim
        + 0.25 * tb
        + 0.25 * tw
        + 0.20 * div
        - pen
    )

    return float(np.clip(score, 0.0, 1.0))


def suggested_label(row: pd.Series, min_score: float) -> bool:
    return bool(row["coordination_score"] >= min_score)


# ---------------------------------------------------------------------
# Deduplication / overlap handling
# ---------------------------------------------------------------------

def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def remove_overlapping_groups(scored: pd.DataFrame, max_overlap: float = 0.75) -> pd.DataFrame:
    """
    Keep highest-scoring groups and remove near-duplicates.
    Example: the same posts may be grouped by both a hashtag and a mention.
    """
    kept_rows = []
    kept_post_sets: List[set] = []

    sorted_df = scored.sort_values("coordination_score", ascending=False).reset_index(drop=True)

    for _, row in sorted_df.iterrows():
        post_set = set(row["post_ids"])
        too_similar = False

        for existing in kept_post_sets:
            overlap = jaccard(post_set, existing)
            if overlap >= max_overlap:
                too_similar = True
                break

        if not too_similar:
            kept_rows.append(row)
            kept_post_sets.append(post_set)

    if not kept_rows:
        return pd.DataFrame(columns=scored.columns)

    return pd.DataFrame(kept_rows)


# ---------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------

def post_ids_to_string(post_ids: Sequence[str], max_ids: int = 20) -> str:
    shown = list(post_ids)[:max_ids]
    suffix = "" if len(post_ids) <= max_ids else f" | ... +{len(post_ids)-max_ids} more"
    return " | ".join(shown) + suffix


def save_scored_csv(scored: pd.DataFrame, out_path: Path) -> None:
    csv_df = scored.copy()
    csv_df["sample_post_ids"] = csv_df["post_ids"].apply(post_ids_to_string)
    csv_df = csv_df.drop(columns=["post_ids"])
    csv_df.to_csv(out_path, index=False)


def save_results_json(scored: pd.DataFrame, out_path: Path, min_score: float, max_results: int) -> None:
    clusters = []

    selected = scored.sort_values("coordination_score", ascending=False).head(max_results)

    for _, row in selected.iterrows():
        post_ids = list(row["post_ids"])

        # Avoid accidentally writing huge broad-crowd clusters.
        if len(post_ids) > MAX_GROUP_SIZE_FOR_OUTPUT:
            post_ids = post_ids[:MAX_GROUP_SIZE_FOR_OUTPUT]

        clusters.append({
            "post_ids": post_ids,
            "is_coordinated": bool(row["coordination_score"] >= min_score),
            "coordination_score": float(row["coordination_score"]),
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"clusters": clusters}, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "eval"])
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--min-score", type=float, default=0.50)
    parser.add_argument("--max-results", type=int, default=150)
    parser.add_argument("--max-overlap", type=float, default=0.75)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    data_dir = project_root / "data" / args.split
    outputs_dir = project_root / "outputs" / args.split
    outputs_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.split} data...")
    posts = load_posts(data_dir)
    embeddings = load_embeddings(data_dir)

    print("Posts:", len(posts))
    print("Embeddings:", len(embeddings))

    print("Building candidate events...")
    candidate_events = build_candidate_events(posts)
    print("Candidate event rows:", len(candidate_events))

    print("Summarising candidate groups...")
    candidates = summarise_candidates(candidate_events)
    print("Candidate groups:", len(candidates))

    if len(candidates) == 0:
        save_results_json(candidates, outputs_dir / "results.json", args.min_score, args.max_results)
        print("No candidates found.")
        return

    print("Computing similarity features and scores...")
    sim_rows = []
    for _, row in candidates.iterrows():
        sim_rows.append(similarity_features(row["post_ids"], embeddings))

    sim_df = pd.DataFrame(sim_rows)
    scored = pd.concat([candidates.reset_index(drop=True), sim_df], axis=1)
    scored["coordination_score"] = scored.apply(coordination_score, axis=1)
    scored["is_coordinated_suggested"] = scored["coordination_score"] >= args.min_score

    print("Removing overlapping duplicate groups...")
    scored_dedup = remove_overlapping_groups(scored, max_overlap=args.max_overlap)
    print("Groups after overlap filtering:", len(scored_dedup))

    scored_dedup = scored_dedup.sort_values("coordination_score", ascending=False).reset_index(drop=True)

    scored_path = outputs_dir / "scored_candidate_groups.csv"
    results_path = outputs_dir / "results.json"

    save_scored_csv(scored_dedup, scored_path)
    save_results_json(scored_dedup, results_path, args.min_score, args.max_results)

    print("Saved:")
    print(scored_path)
    print(results_path)

    print("\nTop 10 scored groups:")
    cols = [
        "key_type", "key_value", "post_count", "account_count",
        "time_span_minutes", "avg_cosine_similarity", "coordination_score",
        "is_coordinated_suggested",
    ]
    print(scored_dedup[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
