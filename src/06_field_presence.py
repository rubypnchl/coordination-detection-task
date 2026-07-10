from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)

list_fields = ["hashtags", "urls", "mentions"]
id_fields = ["reply_to_post_id", "thread_id", "quoted_post_id"]

print("Field presence:")

for field in list_fields:
    count = posts[field].apply(lambda x: isinstance(x, list) and len(x) > 0).sum()
    print(f"{field}: {count} posts")

for field in id_fields:
    count = posts[field].notna().sum()
    print(f"{field}: {count} posts")