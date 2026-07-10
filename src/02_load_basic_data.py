from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts_path = DATA_DIR / "posts.jsonl"
accounts_path = DATA_DIR / "accounts.jsonl"

posts = pd.read_json(posts_path, lines=True)
accounts = pd.read_json(accounts_path, lines=True)

print("Posts shape:", posts.shape)
print("Accounts shape:", accounts.shape)

print("\nPost columns:")
print(posts.columns.tolist())

print("\nAccount columns:")
print(accounts.columns.tolist())

print("\nFirst 3 posts:")
print(posts.head(3))