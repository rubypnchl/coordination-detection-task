from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)

language_counts = posts["language"].fillna("unknown").value_counts()

print(language_counts.head(20))