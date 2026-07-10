from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)
accounts = pd.read_json(DATA_DIR / "accounts.jsonl", lines=True)

num_posts = len(posts)
num_accounts_file = len(accounts)
num_unique_posting_accounts = posts["account_id"].nunique()

print("Number of posts:", num_posts)
print("Number of accounts in accounts file:", num_accounts_file)
print("Number of unique posting accounts:", num_unique_posting_accounts)