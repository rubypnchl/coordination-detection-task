from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)

posts["created_at"] = pd.to_datetime(posts["created_at"], errors="coerce")

start_time = posts["created_at"].min()
end_time = posts["created_at"].max()
duration = end_time - start_time

print("Start time:", start_time)
print("End time:", end_time)
print("Duration:", duration)