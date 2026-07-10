from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/dev")

posts = pd.read_json(DATA_DIR / "posts.jsonl", lines=True)
embeddings = pd.read_parquet(DATA_DIR / "embeddings.parquet")

print("Posts:", posts.shape)
print("Embeddings:", embeddings.shape)

print("\nEmbedding columns:")
print(embeddings.columns.tolist()[:10])

post_ids = set(posts["post_id"])
embedding_post_ids = set(embeddings["post_id"])

missing_embeddings = post_ids - embedding_post_ids
extra_embeddings = embedding_post_ids - post_ids

print("\nPosts missing embeddings:", len(missing_embeddings))
print("Embeddings without matching post:", len(extra_embeddings))