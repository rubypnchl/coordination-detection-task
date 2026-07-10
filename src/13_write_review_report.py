from pathlib import Path
import pandas as pd


SPLIT = "dev"

DATA_DIR = Path("data") / SPLIT
OUTPUT_DIR = Path("outputs") / SPLIT

REVIEW_CANDIDATES_PATH = OUTPUT_DIR / "review_candidates.csv"
REPORT_PATH = OUTPUT_DIR / "candidate_review_report.md"


MAX_POSTS_PER_GROUP = 12
MAX_TEXT_CHARS = 500


def load_data():
    posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")

    review = pd.read_csv(REVIEW_CANDIDATES_PATH)

    return posts, review


def post_belongs_to_candidate(row, key_type, key_value):
    """
    Checks whether a post belongs to a candidate group.
    This mirrors the logic used in Step 2.
    """
    key_value = str(key_value)

    if key_type == "hashtag":
        values = row.get("hashtags")
        return isinstance(values, list) and key_value in [str(x) for x in values]

    if key_type == "url":
        values = row.get("urls")
        return isinstance(values, list) and key_value in [str(x) for x in values]

    if key_type == "mention":
        values = row.get("mentions")
        return isinstance(values, list) and key_value in [str(x) for x in values]

    if key_type == "reply_to_post_id":
        return str(row.get("reply_to_post_id")) == key_value

    if key_type == "thread_id":
        return str(row.get("thread_id")) == key_value

    if key_type == "quoted_post_id":
        return str(row.get("quoted_post_id")) == key_value

    return False


def get_candidate_posts(posts, key_type, key_value):
    mask = posts.apply(
        lambda row: post_belongs_to_candidate(row, key_type, key_value),
        axis=1
    )

    group_posts = posts[mask].copy()
    group_posts = group_posts.sort_values("created_at")

    return group_posts


def clean_text(text):
    text = str(text).replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())

    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "..."

    return text


def write_group_section(f, index, candidate, group_posts):
    key_type = candidate["key_type"]
    key_value = candidate["key_value"]

    f.write(f"\n## Candidate {index}: {key_type} = `{key_value}`\n\n")

    f.write(f"- Selection reason: {candidate.get('selection_reason', '')}\n")
    f.write(f"- Posts: {candidate.get('post_count', '')}\n")
    f.write(f"- Accounts: {candidate.get('account_count', '')}\n")
    f.write(f"- Time span minutes: {candidate.get('time_span_minutes', '')}\n")
    f.write(f"- First time: {candidate.get('first_time', '')}\n")
    f.write(f"- Last time: {candidate.get('last_time', '')}\n\n")

    f.write("### What I should check\n\n")
    f.write("- Are many different accounts posting?\n")
    f.write("- Are the posts close together in time?\n")
    f.write("- Are the texts similar or repeated?\n")
    f.write("- Is this a specific shared target, or just a broad public crowd?\n")
    f.write("- Does this look like a possible coordinated group, an organic crowd, or unclear?\n\n")

    f.write("### Sample posts\n\n")

    for _, row in group_posts.head(MAX_POSTS_PER_GROUP).iterrows():
        f.write(f"**Time:** {row['created_at']}\n\n")
        f.write(f"**Account:** `{row['account_id']}`\n\n")
        f.write(f"**Post ID:** `{row['post_id']}`\n\n")
        f.write(f"**Text:** {clean_text(row['text'])}\n\n")
        f.write("---\n\n")


def main():
    posts, review = load_data()

    print("Posts loaded:", len(posts))
    print("Review candidates loaded:", len(review))

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# Candidate Group Review Report\n\n")
        f.write("This report is for manual inspection of candidate groups.\n\n")
        f.write("A candidate group is not automatically coordinated. The purpose is to inspect whether it looks like organic crowd behaviour or possible coordination.\n\n")

        for index, candidate in review.iterrows():
            key_type = candidate["key_type"]
            key_value = candidate["key_value"]

            group_posts = get_candidate_posts(posts, key_type, key_value)

            write_group_section(
                f=f,
                index=index + 1,
                candidate=candidate,
                group_posts=group_posts
            )

    print("Saved report:", REPORT_PATH)


if __name__ == "__main__":
    main()