from pathlib import Path

DATA_DIR = Path("data/dev")

required_files = [
    "posts.jsonl",
    "accounts.jsonl",
    "embeddings.parquet",
]

print("Checking data folder:", DATA_DIR.resolve())

for file_name in required_files:
    file_path = DATA_DIR / file_name

    if file_path.exists():
        print(f"FOUND: {file_path}")
    else:
        print(f"MISSING: {file_path}")