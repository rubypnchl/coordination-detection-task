"""
Purpose:
    Fill evidence columns for manual review of candidate groups.

What this script does:
    - Reads candidate groups from outputs/<split>/review_notes.csv
      or outputs/<split>/review_candidates.csv.
    - Reconstructs the posts in each candidate group from data/<split>/posts.jsonl.
    - Uses embeddings.parquet to compute semantic/content similarity with cosine similarity.
    - Automatically suggests:
        content_similarity
        timing_pattern
        target_specificity
        suggested_manual_assessment
        suggested_why_this_matters
        coordination_score
    - Writes outputs/<split>/review_notes_auto.csv.

Important:
    This does NOT replace human review. I have manually checked/edited the final assessment.

Run from project root:
    python src/15_review_features.py --split dev

Optional:
    python src/15_review_features.py --split dev --fill-empty
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


LIST_FIELDS = {"hashtag": "hashtags", "url": "urls", "mention": "mentions"}
SINGLE_FIELDS = {
    "reply_to_post_id": "reply_to_post_id",
    "thread_id": "thread_id",
    "quoted_post_id": "quoted_post_id",
}


# -----------------------------
# Loading
# -----------------------------

def load_posts(data_dir: Path) -> pd.DataFrame:
    posts_path = data_dir / "posts.jsonl"
    if not posts_path.exists():
        raise FileNotFoundError(f"Could not find {posts_path}")

    posts = pd.read_json(posts_path, lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")
    return posts


def load_review_table(outputs_dir: Path) -> pd.DataFrame:
    """
    Fall back to review_candidates.csv if needed.
    """
    manual_path = outputs_dir / "review_notes.csv"
    review_path = outputs_dir / "review_candidates.csv"

    if manual_path.exists():
        return pd.read_csv(manual_path)

    if review_path.exists():
        return pd.read_csv(review_path)

    raise FileNotFoundError(
        f"Could not find {manual_path} or {review_path}. "
        "Run Step 2/3 scripts first."
    )


def load_embeddings(data_dir: Path) -> Dict[str, np.ndarray]:
    """
    Loads embeddings and returns {post_id: vector}.

    The assignment says embeddings.parquet stores post_id -> 1024-d int8 vector.
    Different parquet writers may store vectors either as:
      1. a single list/array column, e.g. 'embedding' or 'vector', or
      2. many numeric columns plus post_id.

    This function handles both patterns.
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
            vec = np.asarray(row[vector_col], dtype=np.float32)
            embedding_map[str(row["post_id"])] = vec
        return embedding_map

    # Otherwise assume every numeric column except post_id is one embedding dimension.
    numeric_cols = [
        col for col in emb.columns
        if col != "post_id" and pd.api.types.is_numeric_dtype(emb[col])
    ]

    if not numeric_cols:
        raise ValueError(
            "Could not identify embedding vectors. Expected a vector column "
            "('embedding'/'vector') or numeric dimension columns."
        )

    vectors = emb[numeric_cols].to_numpy(dtype=np.float32)
    post_ids = emb["post_id"].astype(str).to_numpy()

    for post_id, vec in zip(post_ids, vectors):
        embedding_map[post_id] = vec

    return embedding_map


# -----------------------------
# Candidate membership
# -----------------------------

def normalise_key_value(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def list_contains(values, key_value: str) -> bool:
    if not isinstance(values, list):
        return False
    return key_value in [str(v).strip() for v in values]


def get_candidate_posts(posts: pd.DataFrame, key_type: str, key_value: str) -> pd.DataFrame:
    """
    Reconstructs group membership from key_type/key_value.
    This mirrors candidate generation from Step 2.
    """
    key_type = str(key_type).strip()
    key_value = normalise_key_value(key_value)

    if key_type in LIST_FIELDS:
        field = LIST_FIELDS[key_type]
        mask = posts[field].apply(lambda values: list_contains(values, key_value))
        return posts[mask].copy()

    if key_type in SINGLE_FIELDS:
        field = SINGLE_FIELDS[key_type]
        mask = posts[field].astype(str).str.strip() == key_value
        # Avoid matching string 'nan'.
        mask = mask & posts[field].notna()
        return posts[mask].copy()

    # Unknown key type: return empty group rather than failing the whole run.
    return posts.iloc[0:0].copy()


# -----------------------------
# Similarity features
# -----------------------------

def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Computes cosine similarity safely."""
    if len(vectors) == 0:
        return np.empty((0, 0), dtype=np.float32)

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normed = vectors / norms
    return normed @ normed.T


def choose_posts_for_similarity(post_ids: Sequence[str], max_posts: int) -> List[str]:
    """
    For very large groups, pairwise similarity can be expensive.
    This deterministic sample keeps evenly spaced posts.
    """
    post_ids = list(post_ids)
    n = len(post_ids)

    if n <= max_posts:
        return post_ids

    indices = np.linspace(0, n - 1, max_posts).round().astype(int)
    return [post_ids[i] for i in indices]


def embedding_similarity_features(
    group_posts: pd.DataFrame,
    embedding_map: Dict[str, np.ndarray],
    max_posts_for_similarity: int = 80,
) -> Dict[str, float]:
    """
    Computes group-level semantic similarity using the provided embeddings.
    We use pairwise cosine similarity excluding the diagonal.
    """
    sorted_posts = group_posts.sort_values("created_at")
    post_ids = sorted_posts["post_id"].astype(str).tolist()
    sampled_ids = choose_posts_for_similarity(post_ids, max_posts_for_similarity)

    vectors = []
    for post_id in sampled_ids:
        vec = embedding_map.get(post_id)
        if vec is not None:
            vectors.append(vec)

    if len(vectors) < 2:
        return {
            "avg_cosine_similarity": np.nan,
            "max_cosine_similarity": np.nan,
            "share_pairs_above_080": np.nan,
            "similarity_posts_used": len(vectors),
        }

    vectors_arr = np.vstack(vectors).astype(np.float32)
    sim = cosine_similarity_matrix(vectors_arr)

    # Use upper triangle excluding diagonal.
    upper = sim[np.triu_indices_from(sim, k=1)]

    return {
        "avg_cosine_similarity": float(np.mean(upper)),
        "max_cosine_similarity": float(np.max(upper)),
        "share_pairs_above_080": float(np.mean(upper >= 0.80)),
        "similarity_posts_used": int(len(vectors)),
    }


# -----------------------------
# Rule-based labels
# -----------------------------

def phrase_content_similarity(avg_similarity: Optional[float], share_above_080: Optional[float]) -> str:
    if avg_similarity is None or pd.isna(avg_similarity):
        return "embedding similarity unavailable"

    if avg_similarity >= 0.85 or (
        share_above_080 is not None
        and not pd.isna(share_above_080)
        and share_above_080 >= 0.60
    ):
        return "near-duplicate or translated wording"
    if avg_similarity >= 0.70:
        return "high semantic similarity"
    if avg_similarity >= 0.50:
        return "same topic, mixed wording"
    return "low similarity / broad discussion"


def phrase_timing(time_span_minutes: Optional[float]) -> str:
    if time_span_minutes is None or pd.isna(time_span_minutes):
        return "timing unavailable"

    if time_span_minutes <= 10:
        return "within minutes"
    if time_span_minutes <= 60:
        return "within one hour"
    if time_span_minutes <= 24 * 60:
        return "within same day"
    if time_span_minutes <= 7 * 24 * 60:
        return "spread over days"
    if time_span_minutes <= 30 * 24 * 60:
        return "spread over weeks"
    return "spread over months"


def phrase_target_specificity(key_type: str, account_count: int, post_count: int) -> str:
    key_type = str(key_type).strip()

    if key_type == "url":
        return "specific URL"
    if key_type == "quoted_post_id":
        return "specific quoted post"
    if key_type == "reply_to_post_id":
        return "same reply target"
    if key_type == "thread_id":
        return "same thread"
    if key_type == "hashtag":
        return "broad hashtag"
    if key_type == "mention":
        if account_count >= 50 or post_count >= 75:
            return "broad mentioned account"
        return "shared mentioned account"
    return "shared target"


def target_weight(key_type: str, account_count: int, post_count: int) -> float:
    """
    Higher means the shared target is more specific.
    Hashtags and large mentions are weaker because they often produce crowds.
    """
    key_type = str(key_type).strip()

    if key_type == "url":
        return 1.00
    if key_type == "quoted_post_id":
        return 0.95
    if key_type == "reply_to_post_id":
        return 0.90
    if key_type == "thread_id":
        return 0.75
    if key_type == "mention":
        return 0.45 if (account_count >= 50 or post_count >= 75) else 0.65
    if key_type == "hashtag":
        return 0.30
    return 0.50


def time_burst_score(time_span_minutes: Optional[float]) -> float:
    """
    Converts time span into 0-1 burst score.
    Shorter span -> higher score.
    """
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


def account_diversity_score(post_count: int, account_count: int) -> float:
    """
    Rewards groups with multiple accounts, not one account posting repeatedly.
    """
    if post_count <= 0:
        return 0.0
    if account_count < 3:
        return 0.0

    diversity = account_count / max(post_count, 1)
    size_bonus = min(account_count / 10.0, 1.0)
    return float(0.5 * min(diversity, 1.0) + 0.5 * size_bonus)


def similarity_score(avg_similarity: Optional[float]) -> float:
    if avg_similarity is None or pd.isna(avg_similarity):
        return 0.0

    # Map rough cosine range to 0-1. Values below 0.35 are weak.
    return float(np.clip((avg_similarity - 0.35) / 0.55, 0, 1))


def crowd_penalty(
    key_type: str,
    post_count: int,
    account_count: int,
    time_span_minutes: Optional[float],
    avg_similarity: Optional[float],
) -> float:
    """
    Penalises broad, large, long-running, low-similarity groups.
    This addresses the assignment's trap: hashtags/pile-ons can look coordinated.
    """
    penalty = 0.0
    key_type = str(key_type).strip()

    days = None
    if time_span_minutes is not None and not pd.isna(time_span_minutes):
        days = time_span_minutes / (24 * 60)

    if key_type == "hashtag":
        penalty += 0.25
    if key_type == "mention" and (account_count >= 50 or post_count >= 75):
        penalty += 0.20
    if days is not None and days > 30:
        penalty += 0.20
    if post_count >= 100 and (
        avg_similarity is None or pd.isna(avg_similarity) or avg_similarity < 0.65
    ):
        penalty += 0.20
    if account_count < 3:
        penalty += 0.50

    return float(min(penalty, 0.75))


def coordination_score(
    key_type: str,
    post_count: int,
    account_count: int,
    time_span_minutes: Optional[float],
    avg_similarity: Optional[float],
) -> float:
    tw = target_weight(key_type, account_count, post_count)
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


def suggest_manual_assessment(
    key_type: str,
    post_count: int,
    account_count: int,
    time_span_minutes: Optional[float],
    avg_similarity: Optional[float],
    score: float,
) -> str:
    days = None
    if time_span_minutes is not None and not pd.isna(time_span_minutes):
        days = time_span_minutes / (24 * 60)

    if account_count < 3:
        return "not_useful"

    if (
        key_type == "hashtag"
        and days is not None
        and days > 7
        and (pd.isna(avg_similarity) or avg_similarity < 0.70)
    ):
        return "likely_crowd"

    if (
        key_type == "mention"
        and account_count >= 50
        and days is not None
        and days > 7
        and (pd.isna(avg_similarity) or avg_similarity < 0.70)
    ):
        return "likely_crowd"

    if score >= 0.68:
        return "possible_coordination"

    if score <= 0.35:
        return "likely_crowd"

    return "unclear"


def make_reason(
    assessment: str,
    key_type: str,
    content_phrase: str,
    timing_phrase: str,
    target_phrase: str,
    post_count: int,
    account_count: int,
) -> str:
    if assessment == "not_useful":
        return "Not useful for this task because it does not show enough multi-account behaviour."

    if assessment == "likely_crowd":
        return (
            f"{target_phrase.capitalize()} with {post_count} posts and {account_count} accounts, "
            f"{timing_phrase}, and {content_phrase}; this looks more like crowd/topic behaviour than strong coordination."
        )

    if assessment == "possible_coordination":
        return (
            f"{account_count} accounts share a {target_phrase} with {content_phrase} and timing {timing_phrase}, "
            "so this is worth reviewing as a possible coordinated group."
        )

    return (
        f"The group has a {target_phrase} and timing {timing_phrase}, but the content is {content_phrase}; "
        "manual inspection is needed before treating it as coordinated."
    )


# -----------------------------
# Main processing
# -----------------------------

def process_review_rows(
    posts: pd.DataFrame,
    review: pd.DataFrame,
    embedding_map: Dict[str, np.ndarray],
    max_posts_for_similarity: int,
) -> pd.DataFrame:
    output = review.copy()
    rows = []

    for _, row in output.iterrows():
        key_type = str(row.get("key_type", "")).strip()
        key_value = normalise_key_value(row.get("key_value", ""))

        group_posts = get_candidate_posts(posts, key_type, key_value)
        group_posts = group_posts.sort_values("created_at")

        if len(group_posts):
            post_count = int(group_posts["post_id"].nunique())
            account_count = int(group_posts["account_id"].nunique())
        else:
            post_count = int(row.get("post_count", 0) or 0)
            account_count = int(row.get("account_count", 0) or 0)

        if len(group_posts) > 0:
            first_time = group_posts["created_at"].min()
            last_time = group_posts["created_at"].max()
            time_span_minutes = (last_time - first_time).total_seconds() / 60
        else:
            first_time = row.get("first_time", "")
            last_time = row.get("last_time", "")
            time_span_minutes = pd.to_numeric(row.get("time_span_minutes", np.nan), errors="coerce")

        sim_features = embedding_similarity_features(
            group_posts,
            embedding_map,
            max_posts_for_similarity=max_posts_for_similarity,
        )

        avg_sim = sim_features["avg_cosine_similarity"]
        share_080 = sim_features["share_pairs_above_080"]

        content_phrase = phrase_content_similarity(avg_sim, share_080)
        timing = phrase_timing(time_span_minutes)
        target = phrase_target_specificity(key_type, account_count, post_count)
        score = coordination_score(key_type, post_count, account_count, time_span_minutes, avg_sim)
        assessment = suggest_manual_assessment(key_type, post_count, account_count, time_span_minutes, avg_sim, score)
        reason = make_reason(assessment, key_type, content_phrase, timing, target, post_count, account_count)

        rows.append({
            "post_count": post_count,
            "account_count": account_count,
            "first_time": str(first_time),
            "last_time": str(last_time),
            "time_span_minutes": time_span_minutes,
            "avg_cosine_similarity": avg_sim,
            "max_cosine_similarity": sim_features["max_cosine_similarity"],
            "share_pairs_above_080": share_080,
            "similarity_posts_used": sim_features["similarity_posts_used"],
            "content_similarity": content_phrase,
            "timing_pattern": timing,
            "target_specificity": target,
            "coordination_score": score,
            "suggested_manual_assessment": assessment,
            "suggested_why_this_matters": reason,
        })

    df = pd.DataFrame(rows)
    combined = pd.concat([output.reset_index(drop=True), df], axis=1)
    return combined


def fill_empty_manual_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optional convenience: fills columns only when blank.
    It never overwrites existing manual notes.
    """
    mapping = {
        "manual_assessment": "suggested_manual_assessment",
        "content_similarity": "content_similarity",
        "timing_pattern": "timing_pattern",
        "target_specificity": "target_specificity",
        "why_this_matters": "suggested_why_this_matters",
    }

    out = df.copy()

    for manual_col, col in mapping.items():
        if manual_col not in out.columns:
            out[manual_col] = ""
        if col not in out.columns:
            continue

        is_blank = out[manual_col].isna() | (out[manual_col].astype(str).str.strip() == "")
        out.loc[is_blank, manual_col] = out.loc[is_blank, col]

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "eval"])
    parser.add_argument("--project-root", default=".", help="Project root folder, usually current directory.")
    parser.add_argument("--max-posts-for-similarity", type=int, default=80)
    parser.add_argument(
        "--fill-empty",
        action="store_true",
        help="Fill columns only where blank, using auto suggestions.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    data_dir = project_root / "data" / args.split
    outputs_dir = project_root / "outputs" / args.split
    outputs_dir.mkdir(parents=True, exist_ok=True)

    posts = load_posts(data_dir)
    review = load_review_table(outputs_dir)
    embedding_map = load_embeddings(data_dir)

    print(f"Loaded posts: {len(posts)}")
    print(f"Loaded review rows: {len(review)}")
    print(f"Loaded embeddings: {len(embedding_map)}")

    result = process_review_rows(
        posts=posts,
        review=review,
        embedding_map=embedding_map,
        max_posts_for_similarity=args.max_posts_for_similarity,
    )

    if args.fill_empty:
        result = fill_empty_manual_columns(result)

    out_path = outputs_dir / "review_notes_auto.csv"
    result.to_csv(out_path, index=False)

    # A compact sorted view helps quickly inspect strongest suggested candidates.
    compact_cols = [
        "key_type", "key_value",
        "post_count", "account_count", "time_span_minutes",
        "avg_cosine_similarity", "content_similarity", "timing_pattern",
        "target_specificity", "coordination_score",
        "suggested_manual_assessment", "suggested_why_this_matters",
    ]
    compact_cols = [c for c in compact_cols if c in result.columns]

    compact = result[compact_cols].sort_values("coordination_score", ascending=False)
    compact_path = outputs_dir / "review_ranked_candidates.csv"
    compact.to_csv(compact_path, index=False)

    print("Saved:")
    print(out_path)
    print(compact_path)


if __name__ == "__main__":
    main()