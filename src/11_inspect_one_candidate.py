from pathlib import Path
import sys
import pandas as pd


DATA_DIR = Path("data/dev")


def load_posts():
    posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)
    posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")
    return posts


def post_has_value(row, key_type, key_value):
    if key_type == "hashtag":
        return isinstance(row["hashtags"], list) and key_value in [str(x) for x in row["hashtags"]]

    if key_type == "url":
        return isinstance(row["urls"], list) and key_value in [str(x) for x in row["urls"]]

    if key_type == "mention":
        return isinstance(row["mentions"], list) and key_value in [str(x) for x in row["mentions"]]

    if key_type == "reply_to_post_id":
        return str(row["reply_to_post_id"]) == key_value

    if key_type == "thread_id":
        return str(row["thread_id"]) == key_value

    if key_type == "quoted_post_id":
        return str(row["quoted_post_id"]) == key_value

    return False


def inspect_candidate(key_type, key_value):
    posts = load_posts()

    mask = posts.apply(lambda row: post_has_value(row, key_type, key_value), axis=1)
    group = posts[mask].copy()

    if len(group) == 0:
        print("No posts found for this candidate.")
        return

    group = group.sort_values("created_at")

    print("\nCandidate")
    print("-" * 60)
    print("Key type:", key_type)
    print("Key value:", key_value)
    print("Posts:", len(group))
    print("Accounts:", group["account_id"].nunique())
    print("Start:", group["created_at"].min())
    print("End:", group["created_at"].max())

    print("\nSample posts")
    print("-" * 60)

    for _, row in group.head(25).iterrows():
        print("time:", row["created_at"])
        print("account:", row["account_id"])
        print("post_id:", row["post_id"])
        print("text:", str(row["text"])[:300].replace("\n", " "))
        print("-" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("python src\\11_inspect_one_candidate.py <key_type> <key_value>")
        print("\nExample:")
        print("python src\\11_inspect_one_candidate.py hashtag gaza")
        sys.exit(1)

    key_type = sys.argv[1]
    key_value = sys.argv[2]

    inspect_candidate(key_type, key_value)