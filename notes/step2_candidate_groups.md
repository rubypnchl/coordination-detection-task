# Step 2: Candidate group generation

In this step I created candidate groups from shared co-activity keys.

The keys I used were:
- hashtags
- URLs
- mentions
- reply_to_post_id
- thread_id
- quoted_post_id

I treated these only as candidate-generation signals, not as proof of coordination. This is important because a popular hashtag or a viral thread can create a large group of posts without any coordinated behaviour.

I filtered candidate groups to keep only groups with at least 3 posts and 3 distinct accounts. This keeps the focus on multi-account behaviour.

For each candidate group I saved:
- key type
- key value
- number of posts
- number of accounts
- time span
- sample post IDs
- all post IDs

My next step is to inspect these groups and compute stronger features such as content similarity, time burstiness, target specificity, and crowd penalties.