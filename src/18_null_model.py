"""
18_null_model.py

Purpose:
    Add a statistical null-model check to the coordination detection task.

This script does NOT use hidden labels.
It compares each observed scored candidate against matched random groups.

Main idea:
    Observed group score should be unusually high compared with random groups
    of similar type and size.

Inputs:
    data/<split>/posts.jsonl
    data/<split>/embeddings.parquet
    outputs/<split>/scored_candidate_groups.csv

Outputs:
    outputs/<split>/scored_candidate_groups_with_null.csv
    outputs/<split>/null_model_summary.md

Run from project root:
    python src/18_null_model.py --split dev
    python src/18_null_model.py --split eval

Recommended:
    python src/18_null_model.py --split dev --num-null-samples 300
    python src/18_null_model.py --split eval --num-null-samples 300
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import tabulate


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


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------

def load_posts(data_dir: Path) -> pd.DataFrame:
    posts_path = data_dir / "posts.jsonl"

    if not posts_path.exists():
        raise FileNotFoundError(f"Missing posts file: {posts_path}")

    posts = pd.read_json(posts_path, lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")

    return posts


def load_embeddings(data_dir: Path) -> Dict[str, np.ndarray]:
    emb_path = data_dir / "embeddings.parquet"

    if not emb_path.exists():
        raise FileNotFoundError(f"Missing embeddings file: {emb_path}")

    emb = pd.read_parquet(emb_path)

    if "post_id" not in emb.columns:
        raise ValueError("embeddings.parquet must contain a post_id column")

    embedding_map: Dict[str, np.ndarray] = {}

    # Case 1: vector stored in one column
    vector_col = None
    for candidate in ["embedding", "vector", "embeddings"]:
        if candidate in emb.columns:
            vector_col = candidate
            break

    if vector_col is not None:
        for _, row in emb[["post_id", vector_col]].iterrows():
            embedding_map[str(row["post_id"])] = np.asarray(row[vector_col], dtype=np.float32)
        return embedding_map

    # Case 2: vector stored across many numeric columns
    numeric_cols = [
        c for c in emb.columns
        if c != "post_id" and pd.api.types.is_numeric_dtype(emb[c])
    ]

    if not numeric_cols:
        raise ValueError("Could not identify embedding columns")

    vectors = emb[numeric_cols].to_numpy(dtype=np.float32)
    post_ids = emb["post_id"].astype(str).to_numpy()

    for post_id, vec in zip(post_ids, vectors):
        embedding_map[post_id] = vec

    return embedding_map


def load_scored_candidates(outputs_dir: Path) -> pd.DataFrame:
    scored_path = outputs_dir / "scored_candidate_groups.csv"

    if not scored_path.exists():
        raise FileNotFoundError(
            f"Missing scored candidates: {scored_path}. "
            "Run src/16_score_candidates_and_results.py first."
        )

    scored = pd.read_csv(scored_path)

    required = ["key_type", "post_count", "account_count", "coordination_score"]

    for col in required:
        if col not in scored.columns:
            raise ValueError(f"scored_candidate_groups.csv missing column: {col}")

    return scored


# ---------------------------------------------------------------------
# Scoring logic copied in simple form from the coordination scoring idea
# ---------------------------------------------------------------------

def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    if len(vectors) == 0:
        return np.empty((0, 0), dtype=np.float32)

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0

    normed = vectors / norms
    return normed @ normed.T


def avg_embedding_similarity(
    post_ids: List[str],
    embedding_map: Dict[str, np.ndarray],
    max_posts: int = 80,
) -> float:
    if len(post_ids) > max_posts:
        indices = np.linspace(0, len(post_ids) - 1, max_posts).round().astype(int)
        post_ids = [post_ids[i] for i in indices]

    vectors = []

    for post_id in post_ids:
        vec = embedding_map.get(str(post_id))
        if vec is not None:
            vectors.append(vec)

    if len(vectors) < 2:
        return np.nan

    vectors = np.vstack(vectors).astype(np.float32)
    sim = cosine_similarity_matrix(vectors)
    upper = sim[np.triu_indices_from(sim, k=1)]

    return float(np.mean(upper))


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

    return float(np.clip((avg_similarity - 0.35) / 0.55, 0, 1))


def target_weight(key_type: str, account_count: int, post_count: int) -> float:
    key_type = str(key_type)

    if key_type == "url":
        return 1.00
    if key_type == "quoted_post_id":
        return 0.95
    if key_type == "reply_to_post_id":
        return 0.90
    if key_type == "thread_id":
        return 0.75
    if key_type == "mention":
        return 0.45 if account_count >= 50 or post_count >= 75 else 0.65
    if key_type == "hashtag":
        return 0.30

    return 0.50


def account_diversity_score(post_count: int, account_count: int) -> float:
    if post_count <= 0:
        return 0.0

    if account_count < 3:
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
    penalty = 0.0
    key_type = str(key_type)

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


def compute_group_score(
    group_posts: pd.DataFrame,
    key_type: str,
    embedding_map: Dict[str, np.ndarray],
) -> float:
    if len(group_posts) == 0:
        return 0.0

    post_count = int(group_posts["post_id"].nunique())
    account_count = int(group_posts["account_id"].nunique())

    sorted_group = group_posts.sort_values("created_at")

    first_time = sorted_group["created_at"].min()
    last_time = sorted_group["created_at"].max()

    if pd.isna(first_time) or pd.isna(last_time):
        time_span_minutes = np.nan
    else:
        time_span_minutes = (last_time - first_time).total_seconds() / 60

    post_ids = sorted_group["post_id"].astype(str).tolist()
    avg_sim = avg_embedding_similarity(post_ids, embedding_map)

    score = (
        0.30 * similarity_score(avg_sim)
        + 0.25 * time_burst_score(time_span_minutes)
        + 0.25 * target_weight(key_type, account_count, post_count)
        + 0.20 * account_diversity_score(post_count, account_count)
        - crowd_penalty(key_type, post_count, account_count, time_span_minutes, avg_sim)
    )

    return float(np.clip(score, 0.0, 1.0))


# ---------------------------------------------------------------------
# Null sampling
# ---------------------------------------------------------------------

def posts_with_key_type(posts: pd.DataFrame, key_type: str) -> pd.DataFrame:
    """
    Creates a pool of posts that are eligible for the same type of candidate.
    Example:
        key_type=url -> posts with at least one URL
        key_type=reply_to_post_id -> posts that reply to something
    """
    key_type = str(key_type)

    if key_type in LIST_FIELDS:
        field = LIST_FIELDS[key_type]
        return posts[
            posts[field].apply(lambda x: isinstance(x, list) and len(x) > 0)
        ].copy()

    if key_type in SINGLE_FIELDS:
        field = SINGLE_FIELDS[key_type]
        return posts[posts[field].notna()].copy()

    return posts.copy()


def sample_null_group(
    posts: pd.DataFrame,
    key_type: str,
    post_count: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Matched null:
        sample the same number of posts from the same key_type pool.

    This preserves rough key type and group size, but breaks the actual observed
    target grouping.
    """
    pool = posts_with_key_type(posts, key_type)

    if len(pool) < post_count:
        pool = posts

    sampled_indices = rng.choice(pool.index.to_numpy(), size=post_count, replace=False)
    return pool.loc[sampled_indices].copy()


def empirical_p_value(observed_score: float, null_scores: np.ndarray) -> float:
    """
    p = probability that a null/random group scores at least as high as observed.
    Add-one smoothing avoids p=0.
    """
    return float((1 + np.sum(null_scores >= observed_score)) / (1 + len(null_scores)))


def percentile_against_null(observed_score: float, null_scores: np.ndarray) -> float:
    """
    Percent of null scores lower than or equal to the observed score.
    Higher is better.
    """
    return float(np.mean(null_scores <= observed_score))


def run_null_for_candidate(
    observed_score: float,
    key_type: str,
    post_count: int,
    posts: pd.DataFrame,
    embedding_map: Dict[str, np.ndarray],
    num_null_samples: int,
    rng: np.random.Generator,
) -> dict:
    null_scores = []

    for _ in range(num_null_samples):
        null_group = sample_null_group(posts, key_type, post_count, rng)
        null_score = compute_group_score(null_group, key_type, embedding_map)
        null_scores.append(null_score)

    null_scores = np.asarray(null_scores, dtype=float)

    p_value = empirical_p_value(observed_score, null_scores)
    percentile = percentile_against_null(observed_score, null_scores)

    return {
        "null_mean_score": float(np.mean(null_scores)),
        "null_std_score": float(np.std(null_scores)),
        "null_95th_percentile": float(np.percentile(null_scores, 95)),
        "null_p_value": p_value,
        "null_percentile": percentile,
        "score_minus_null_mean": float(observed_score - np.mean(null_scores)),
        "final_score_with_null": float(np.clip(observed_score * (1 - p_value), 0.0, 1.0)),
    }


# ---------------------------------------------------------------------
# Main process
# ---------------------------------------------------------------------

def run_null_model(
    split: str,
    project_root: Path,
    num_null_samples: int,
    max_candidates: int,
    random_seed: int,
) -> pd.DataFrame:
    data_dir = project_root / "data" / split
    outputs_dir = project_root / "outputs" / split

    posts = load_posts(data_dir)
    embedding_map = load_embeddings(data_dir)
    scored = load_scored_candidates(outputs_dir)

    scored = scored.sort_values("coordination_score", ascending=False).copy()

    if max_candidates is not None and max_candidates > 0:
        scored_to_test = scored.head(max_candidates).copy()
        scored_remaining = scored.iloc[max_candidates:].copy()
    else:
        scored_to_test = scored.copy()
        scored_remaining = scored.iloc[0:0].copy()

    rng = np.random.default_rng(random_seed)

    null_rows = []

    print(f"Split: {split}")
    print(f"Candidates to test with null model: {len(scored_to_test)}")
    print(f"Null samples per candidate: {num_null_samples}")

    for i, row in scored_to_test.iterrows():
        key_type = str(row["key_type"])
        post_count = int(row["post_count"])
        observed_score = float(row["coordination_score"])

        null_stats = run_null_for_candidate(
            observed_score=observed_score,
            key_type=key_type,
            post_count=post_count,
            posts=posts,
            embedding_map=embedding_map,
            num_null_samples=num_null_samples,
            rng=rng,
        )

        null_rows.append(null_stats)

        if len(null_rows) % 10 == 0:
            print(f"Processed {len(null_rows)} candidates")

    null_df = pd.DataFrame(null_rows)

    tested_with_null = pd.concat(
        [scored_to_test.reset_index(drop=True), null_df.reset_index(drop=True)],
        axis=1
    )

    # For candidates not tested, keep null columns blank.
    if len(scored_remaining) > 0:
        for col in null_df.columns:
            scored_remaining[col] = np.nan

        combined = pd.concat([tested_with_null, scored_remaining], ignore_index=True)
    else:
        combined = tested_with_null

    combined = combined.sort_values(
        ["final_score_with_null", "coordination_score"],
        ascending=[False, False],
        na_position="last"
    )

    out_path = outputs_dir / "scored_candidate_groups_with_null.csv"
    combined.to_csv(out_path, index=False)

    summary_path = outputs_dir / "null_model_summary.md"
    write_summary(summary_path, combined, split, num_null_samples, max_candidates)

    print("Saved:")
    print(out_path)
    print(summary_path)

    return combined


def write_summary(
    path: Path,
    df: pd.DataFrame,
    split: str,
    num_null_samples: int,
    max_candidates: int,
) -> None:
    tested = df[df["null_p_value"].notna()].copy()

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Null model summary for {split}\n\n")

        f.write("This file summarises a matched randomisation null model.\n\n")

        f.write("For each tested candidate group, I generated random groups with the same key type and same post count. ")
        f.write("I then computed the same coordination score for each random group and compared the observed score against this null distribution.\n\n")

        f.write("Empirical p-value:\n\n")
        f.write("```text\n")
        f.write("p = (1 + number of null scores >= observed score) / (1 + number of null samples)\n")
        f.write("```\n\n")

        f.write(f"- Number of tested candidates: {len(tested)}\n")
        f.write(f"- Null samples per candidate: {num_null_samples}\n")
        f.write(f"- Max candidates requested: {max_candidates}\n\n")

        if len(tested) > 0:
            f.write("## Aggregate null results\n\n")
            f.write(f"- Mean null p-value: {tested['null_p_value'].mean():.4f}\n")
            f.write(f"- Median null p-value: {tested['null_p_value'].median():.4f}\n")
            f.write(f"- Candidates with p <= 0.05: {(tested['null_p_value'] <= 0.05).sum()}\n")
            f.write(f"- Candidates with p <= 0.10: {(tested['null_p_value'] <= 0.10).sum()}\n\n")

            f.write("## Top candidates by null-adjusted score\n\n")

            cols = [
                "key_type",
                "key_value",
                "post_count",
                "account_count",
                "coordination_score",
                "null_mean_score",
                "null_95th_percentile",
                "null_p_value",
                "final_score_with_null",
            ]

            cols = [c for c in cols if c in tested.columns]

            top = tested.sort_values("final_score_with_null", ascending=False).head(15)

            f.write(top[cols].to_markdown(index=False))
            f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--split", default="dev", choices=["dev", "eval"])
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--num-null-samples", type=int, default=300)
    parser.add_argument("--max-candidates", type=int, default=150)
    parser.add_argument("--random-seed", type=int, default=42)

    args = parser.parse_args()

    run_null_model(
        split=args.split,
        project_root=Path(args.project_root),
        num_null_samples=args.num_null_samples,
        max_candidates=args.max_candidates,
        random_seed=args.random_seed,
    )


if __name__ == "__main__":
    main()