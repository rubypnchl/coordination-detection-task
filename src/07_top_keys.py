from pathlib import Path
from collections import Counter
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)


def count_list_values(series):
    counter = Counter()

    for values in series:
        if isinstance(values, list):
            counter.update(values)

    return counter


def print_top(counter, title, n=15):
    print(f"\nTop {title}")
    print("-" * 40)

    for value, count in counter.most_common(n):
        print(count, value)


hashtag_counts = count_list_values(posts["hashtags"])
url_counts = count_list_values(posts["urls"])
mention_counts = count_list_values(posts["mentions"])

reply_counts = posts["reply_to_post_id"].dropna().value_counts()
thread_counts = posts["thread_id"].dropna().value_counts()
quote_counts = posts["quoted_post_id"].dropna().value_counts()

print_top(hashtag_counts, "hashtags")
print_top(url_counts, "URLs")
print_top(mention_counts, "mentions")

print("\nTop reply targets")
print("-" * 40)
print(reply_counts.head(15))

print("\nTop threads")
print("-" * 40)
print(thread_counts.head(15))

print("\nTop quoted posts")
print("-" * 40)
print(quote_counts.head(15))