from pathlib import Path
import pandas as pd


SPLIT = "dev"

OUTPUT_DIR = Path("outputs") / SPLIT

INPUT_PATH = OUTPUT_DIR / "candidate_groups_full.jsonl"
REVIEW_OUTPUT_PATH = OUTPUT_DIR / "review_candidates.csv"


def load_candidate_groups():
    groups = pd.read_json(INPUT_PATH, lines=True)

    # Make sure numeric columns are numeric.
    numeric_cols = ["post_count", "account_count", "time_span_minutes", "posts_per_account"]

    for col in numeric_cols:
        if col in groups.columns:
            groups[col] = pd.to_numeric(groups[col], errors="coerce")

    return groups


def pick_largest_groups(groups, n=25):
    """
    These are useful because large groups often reveal organic crowd behaviour.
    We review them to understand what false positives look like.
    """
    selected = groups.sort_values(
        by=["account_count", "post_count"],
        ascending=False
    ).head(n).copy()

    selected["selection_reason"] = "largest_candidate_groups"

    return selected


def pick_tight_time_groups(groups, n=25):
    """
    Groups that happen in short time windows may be more interesting.
    But they can still be organic, so they need inspection.
    """
    usable = groups.dropna(subset=["time_span_minutes"]).copy()

    # Avoid selecting groups with zero or tiny account counts.
    usable = usable[usable["account_count"] >= 3]

    selected = usable.sort_values(
        by=["time_span_minutes", "account_count"],
        ascending=[True, False]
    ).head(n).copy()

    selected["selection_reason"] = "tight_time_window_groups"

    return selected


def pick_specific_target_groups(groups, n=30):
    """
    Some key types are more specific than broad hashtags.
    Same URL, reply target, quoted post, or thread can be more useful for candidate discovery.
    """
    specific_key_types = [
        "url",
        "reply_to_post_id",
        "quoted_post_id",
        "thread_id",
    ]

    usable = groups[groups["key_type"].isin(specific_key_types)].copy()

    selected = usable.sort_values(
        by=["account_count", "post_count"],
        ascending=False
    ).head(n).copy()

    selected["selection_reason"] = "specific_shared_target_groups"

    return selected


def pick_hashtag_crowd_examples(groups, n=15):
    """
    Hashtags are important to inspect because they can create organic crowds.
    This helps us learn what not to over-rank later.
    """
    usable = groups[groups["key_type"] == "hashtag"].copy()

    selected = usable.sort_values(
        by=["account_count", "post_count"],
        ascending=False
    ).head(n).copy()

    selected["selection_reason"] = "hashtag_crowd_examples"

    return selected


def combine_review_set(parts):
    review = pd.concat(parts, ignore_index=True)

    # Remove duplicates where the same key was selected for multiple reasons.
    review = review.drop_duplicates(subset=["key_type", "key_value"]).copy()

    review = review.sort_values(
        by=["selection_reason", "account_count", "post_count"],
        ascending=[True, False, False]
    )

    # Add empty columns Ruby can fill manually after reading the report.
    review["manual_assessment"] = ""
    review["why_it_looks_like_crowd_or_coordination"] = ""
    review["content_similarity_notes"] = ""
    review["timing_notes"] = ""
    review["target_specificity_notes"] = ""

    # Keep columns in a readable order.
    preferred_columns = [
        "selection_reason",
        "key_type",
        "key_value",
        "post_count",
        "account_count",
        "time_span_minutes",
        "posts_per_account",
        "first_time",
        "last_time",
        "sample_post_ids",
        "manual_assessment",
        "why_it_looks_like_crowd_or_coordination",
        "content_similarity_notes",
        "timing_notes",
        "target_specificity_notes",
    ]

    existing_columns = [col for col in preferred_columns if col in review.columns]

    return review[existing_columns]


def main():
    groups = load_candidate_groups()

    print("Loaded candidate groups:", len(groups))

    largest = pick_largest_groups(groups)
    tight = pick_tight_time_groups(groups)
    specific = pick_specific_target_groups(groups)
    hashtags = pick_hashtag_crowd_examples(groups)

    review = combine_review_set([largest, tight, specific, hashtags])

    review.to_csv(REVIEW_OUTPUT_PATH, index=False)

    print("Review candidates:", len(review))
    print("Saved:", REVIEW_OUTPUT_PATH)


if __name__ == "__main__":
    main()