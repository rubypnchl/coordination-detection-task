# Step 6: Eval output generation

After checking the dev ranking, I applied the same scoring pipeline to the eval split.

I did not tune the scoring rules on eval. I only checked that the output file was valid and that the top-ranked groups were not dominated by broad hashtag or large mention crowds.

The final output is results.json, containing one entry per identified group with post_ids, is_coordinated, and coordination_score.

The score is used as a ranking signal, so I kept the output ordered from strongest to weakest candidate.