from pathlib import Path
import pandas as pd


OUTPUT_DIR = Path("outputs/dev")

summary_path = OUTPUT_DIR / "candidate_groups_summary.csv"

summary = pd.read_csv(summary_path)

print("Number of candidate groups:", len(summary))

print("\nCandidate groups by key type:")
print(summary["key_type"].value_counts())

print("\nTop 30 largest candidate groups:")
columns_to_show = [
    "key_type",
    "key_value",
    "post_count",
    "account_count",
    "time_span_minutes",
    "posts_per_account",
]

print(summary[columns_to_show].head(30).to_string(index=False))