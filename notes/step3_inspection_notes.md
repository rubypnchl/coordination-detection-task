# Step 3: Candidate inspection

After generating candidate groups, I created a review set for manual inspection.

I selected different types of groups:
- largest groups, to understand likely organic crowd behaviour
- tight time-window groups, because timing may be useful for coordination
- URL, reply, quote, and thread groups, because these are more specific shared targets
- large hashtag groups, because hashtags can easily create false positives

I did not treat candidate groups as coordinated at this stage.

The purpose was to inspect examples and understand what signals separate possible coordination from ordinary crowd behaviour.

Initial things I checked:
- number of distinct accounts
- time span
- whether the texts look repeated or semantically similar
- whether the shared key is broad or specific
- whether the group looks like a viral crowd or a smaller coordinated action

The main lesson from this step is that candidate generation alone is not enough. A group can share a hashtag, URL, or thread without being coordinated. The next step should add features for timing, semantic similarity, target specificity, and crowd penalty.