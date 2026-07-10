from pathlib import Path
import json
import pandas as pd


DATA_DIR = Path("data/dev")
OUTPUT_DIR = Path("outputs/dev")

MIN_POSTS = 3
MIN_ACCOUNTS = 3


def make_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_posts():
    posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")
    return posts


def add_list_field_candidates(posts, field_name, key_type, rows):
    """
    Handles fields that contain lists, such as:
    - hashtags
    - urls
    - mentions

    One post can contribute to multiple candidate keys.
    """
    useful_columns = ["post_id", "account_id", "created_at", "text", field_name]

    for _, row in posts[useful_columns].iterrows():
        values = row[field_name]

        if not isinstance(values, list):
            continue

        for value in values:
            if value is None:
                continue

            value = str(value).strip()

            if value == "":
                continue

            rows.append({
                "key_type": key_type,
                "key_value": value,
                "post_id": row["post_id"],
                "account_id": row["account_id"],
                "created_at": row["created_at"],
                "text": row["text"],
            })


def add_single_field_candidates(posts, field_name, key_type, rows):
    """
    Handles fields that contain one value, such as:
    - reply_to_post_id
    - thread_id
    - quoted_post_id
    """
    useful_columns = ["post_id", "account_id", "created_at", "text", field_name]

    subset = posts[useful_columns].dropna(subset=[field_name])

    for _, row in subset.iterrows():
        value = str(row[field_name]).strip()

        if value == "":
            continue

        rows.append({
            "key_type": key_type,
            "key_value": value,
            "post_id": row["post_id"],
            "account_id": row["account_id"],
            "created_at": row["created_at"],
            "text": row["text"],
        })


def build_candidate_events(posts):
    """
    Converts posts into rows of:
    post X belongs to candidate key Y.
    """
    rows = []

    add_list_field_candidates(posts, "hashtags", "hashtag", rows)
    add_list_field_candidates(posts, "urls", "url", rows)
    add_list_field_candidates(posts, "mentions", "mention", rows)

    add_single_field_candidates(posts, "reply_to_post_id", "reply_to_post_id", rows)
    add_single_field_candidates(posts, "thread_id", "thread_id", rows)
    add_single_field_candidates(posts, "quoted_post_id", "quoted_post_id", rows)

    return pd.DataFrame(rows)


def summarise_candidate_groups(candidate_events):
    """
    Creates one summary row per candidate group.
    """
    summary_rows = []

    grouped = candidate_events.groupby(["key_type", "key_value"])

    for (key_type, key_value), group in grouped:
        post_ids = group["post_id"].drop_duplicates().tolist()
        account_ids = group["account_id"].drop_duplicates().tolist()

        post_count = len(post_ids)
        account_count = len(account_ids)

        if post_count < MIN_POSTS:
            continue

        if account_count < MIN_ACCOUNTS:
            continue

        start_time = group["created_at"].min()
        end_time = group["created_at"].max()

        if pd.isna(start_time) or pd.isna(end_time):
            time_span_minutes = None
        else:
            time_span_minutes = (end_time - start_time).total_seconds() / 60

        summary_rows.append({
            "key_type": key_type,
            "key_value": key_value,
            "post_count": post_count,
            "account_count": account_count,
            "time_span_minutes": time_span_minutes,
            "posts_per_account": post_count / account_count,
            "first_time": str(start_time),
            "last_time": str(end_time),
            "sample_post_ids": post_ids[:10],
            "all_post_ids": post_ids,
        })

    summary = pd.DataFrame(summary_rows)

    if len(summary) == 0:
        return summary

    summary = summary.sort_values(
        by=["account_count", "post_count"],
        ascending=False
    )

    return summary


def save_outputs(candidate_events, candidate_summary):
    candidate_events.to_csv(OUTPUT_DIR / "candidate_events.csv", index=False)

    csv_summary = candidate_summary.copy()

    if len(csv_summary) > 0:
        csv_summary["sample_post_ids"] = csv_summary["sample_post_ids"].apply(
            lambda x: " | ".join(x)
        )
        csv_summary = csv_summary.drop(columns=["all_post_ids"])

    csv_summary.to_csv(OUTPUT_DIR / "candidate_groups_summary.csv", index=False)

    with open(OUTPUT_DIR / "candidate_groups_full.jsonl", "w", encoding="utf-8") as f:
        for _, row in candidate_summary.iterrows():
            record = row.to_dict()
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    make_output_dir()

    posts = load_posts()

    print("Loaded posts:", len(posts))

    candidate_events = build_candidate_events(posts)
    print("Candidate event rows:", len(candidate_events))

    candidate_summary = summarise_candidate_groups(candidate_events)
    print("Candidate groups after filtering:", len(candidate_summary))

    save_outputs(candidate_events, candidate_summary)

    print("\nSaved:")
    print(OUTPUT_DIR / "candidate_events.csv")
    print(OUTPUT_DIR / "candidate_groups_summary.csv")
    print(OUTPUT_DIR / "candidate_groups_full.jsonl")


if __name__ == "__main__":
    main()