# Step 1: Data understanding

I started by checking that the expected files were present: posts.jsonl, accounts.jsonl, and embeddings.parquet.

Then I loaded posts and accounts with pandas and inspected the number of rows, columns, time range, language distribution, and field presence.

The fields that seem most useful for coordination detection are:
- urls
- mentions
- reply_to_post_id
- thread_id
- quoted_post_id
- hashtags

However, I should not treat a shared hashtag or popular thread as coordination by itself. These can also represent ordinary crowd behaviour around viral events.

The embeddings will be useful for semantic similarity, but I should use them as one signal, not as the whole method.