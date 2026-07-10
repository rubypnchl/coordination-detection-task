# Coordinated Account Group Detection

This project identifies groups of social-media accounts that appear to be acting together in a single-platform conversation snapshot. The goal is not to detect bots, fake accounts, account authenticity, or whether the content is true. The task is only to identify groups of accounts whose posting behaviour looks coordinated, and to rank those groups by strength of evidence.

The final output is `results.json` for the `eval` split.

---

## Development environment

I developed and tested the project locally using:

```text
Windows
Visual Studio Code
Python
PowerShell
```

Docker support is included for reproducibility. The Docker image is not meant to imply that the whole project was developed inside Docker. It provides a clean Python environment so the final scoring pipeline can be run consistently with the provided `data/` folder mounted into the container.

---

## 1. Problem framing

The main challenge is that coordination can look similar to normal crowd behaviour. A viral hashtag, a breaking-news pile-on, or many users replying to the same public post may create large groups of posts that are not necessarily coordinated.

I therefore treated the task as **unsupervised coordination discovery**, not ordinary text clustering.

My operational definition was:

> A group is more likely to be coordinated when multiple distinct accounts act on the same specific target or message within a compressed time window, with semantically similar content, and where the pattern is stronger than broad organic crowd behaviour.

This means I did not treat a shared hashtag, shared mention, or semantic similarity as sufficient evidence by itself. I looked for multiple signals together:

- multiple accounts;
- shared target or co-activity key;
- semantic/content similarity;
- compressed timing;
- target specificity;
- penalties for broad crowd-like groups.

The key principle was:

> Topic similarity is not the same as coordination.

---

## 2. Data used

Each split contains:

```text
posts.jsonl
accounts.jsonl
embeddings.parquet
```

The main fields used from `posts.jsonl` were:

- `post_id`
- `account_id`
- `created_at`
- `text`
- `hashtags`
- `urls`
- `mentions`
- `reply_to_post_id`
- `thread_id`
- `quoted_post_id`

The account file was loaded during data inspection, but I did not rely heavily on profile metadata in the final scoring. I prioritised behavioural evidence because the task is about accounts acting together, not whether accounts look authentic.

The provided sentence embeddings were used for semantic similarity. Since the vectors are not unit-normalised, I used cosine similarity.

---

## 3. Project structure

```text
ruby_coordination_task/
  data/
    dev/
      posts.jsonl
      accounts.jsonl
      embeddings.parquet
    eval/
      posts.jsonl
      accounts.jsonl
      embeddings.parquet

  src/
    01_check_files.py
    02_load_basic_data.py
    03_basic_counts.py
    04_time_range.py
    05_language_distribution.py
    06_field_presence.py
    07_top_keys.py
    08_check_embeddings.py
    09_build_candidate_groups.py
    10_view_candidate_groups.py
    11_inspect_one_candidate.py
    12_prepare_review_candidates.py
    13_write_review_report.py
    14_create_manual_review_notes.py
    15_auto_review_features.py
    16_score_candidates_and_results.py

  outputs/
    dev/
    eval/

  notes/

  Dockerfile
  requirements.txt
  README.md
  prompts.txt
  results.json
```

The early numbered scripts are intentionally simple. I used them to understand the data and build confidence before consolidating the logic into the final scoring script.

---

## 4. Installation and local run

Install dependencies:

```bash
pip install -r requirements.txt
```

Required packages:

```text
pandas
numpy
pyarrow
```

Run the final scoring pipeline on the development split:

```bash
python src/16_score_candidates_and_results.py --split dev --min-score 0.50 --max-results 150
```

Run the final scoring pipeline on the evaluation split:

```bash
python src/16_score_candidates_and_results.py --split eval --min-score 0.50 --max-results 150
```

This writes:

```text
outputs/eval/scored_candidate_groups.csv
outputs/eval/results.json
```

For submission, copy the eval result to the project root:

```bash
cp outputs/eval/results.json results.json
```

On Windows PowerShell:

```powershell
copy outputs\eval\results.json results.json
```

V### Validate the final results file

After generating the eval output, I validated the structure of `results.json` using a small validation script:

```bash
python src/17_validate_results.py --results results.json

---

## 5. Docker run

Docker is included for reproducible execution in a clean Python environment.

Build the Docker image:

```bash
docker build -t coordination-task .
```

Run on the evaluation split using mounted data and outputs folders.

Windows PowerShell:

```powershell
docker run --rm -v "${PWD}\data:/app/data" -v "${PWD}\outputs:/app/outputs" coordination-task --split eval --min-score 0.50 --max-results 150
```

macOS/Linux:

```bash
docker run --rm \
  -v "$PWD/data:/app/data" \
  -v "$PWD/outputs:/app/outputs" \
  coordination-task --split eval --min-score 0.50 --max-results 150
```

This writes:

```text
outputs/eval/results.json
outputs/eval/scored_candidate_groups.csv
```

Then copy the eval result to the root project folder for submission:

```powershell
copy outputs\eval\results.json results.json
```

or on macOS/Linux:

```bash
cp outputs/eval/results.json results.json
```

---

## 6. Dockerfile

The project root should contain this `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY README.md .
COPY prompts.txt .

# Data is mounted at runtime:
#   /app/data
# Outputs are mounted at runtime:
#   /app/outputs

ENTRYPOINT ["python", "src/16_score_candidates_and_results.py"]
```

The data is mounted rather than copied into the image. This keeps the Docker image smaller and avoids packaging the provided dataset inside the container.

---

## 7. Pipeline overview

### Step 1: Data inspection

I first inspected the dataset before attempting detection. I checked:

- number of posts and accounts;
- time range;
- language distribution;
- how often hashtags, URLs, mentions, replies, threads, and quotes appear;
- top co-activity keys;
- whether embeddings were available for posts.

This helped me understand which fields were useful for candidate generation and which fields were likely to create false positives.

### Step 2: Candidate group generation

I generated candidate groups from shared co-activity keys:

- same hashtag;
- same URL;
- same mention;
- same reply target;
- same thread;
- same quoted post.

A candidate group was not treated as coordinated. It only meant that the posts shared some observable behaviour and were worth scoring or inspecting.

I filtered out very small groups by requiring at least 3 posts and 3 distinct accounts.

### Step 3: Manual inspection

Because there are no labels, I inspected candidate groups from the dev split. I looked at examples from different types of candidates:

- large hashtag groups;
- large mention groups;
- URL-sharing groups;
- tight reply/quote/thread groups;
- repeated multilingual content patterns.

The manual review confirmed that broad hashtags and large mention groups were often noisy. Some looked like ordinary topic discussion spread over weeks or months. More specific targets, such as URLs and reply targets, became more interesting when combined with semantic similarity and short timing.

### Step 4: Automated review evidence

To save time, I automated the evidence columns used during manual review:

- content similarity;
- timing pattern;
- target specificity;
- suggested manual assessment;
- suggested explanation.

This was done in:

```text
src/15_auto_review_features.py
```

The key point is that the script suggests evidence; it does not replace manual judgement.

### Step 5: Final scoring

The final scoring script is:

```text
src/16_score_candidates_and_results.py
```

It generates candidate groups, computes features, ranks them, removes high-overlap duplicate clusters, and writes `results.json`.

---

## 8. Features used

For each candidate group, I computed the following signals.

### Account diversity

Coordination should involve multiple accounts. Groups with many posts but only one or two accounts were not useful for this task.

Example intuition:

```text
20 posts from 18 accounts > 20 posts from 2 accounts
```

### Time burstiness

Groups that occur in a short time window receive higher timing scores.

Example intuition:

```text
10 accounts posting within 10 minutes is stronger than 10 accounts posting across 3 months.
```

### Semantic similarity

I used the provided embeddings and computed pairwise cosine similarity between posts in a candidate group.

The final scoring uses:

- average cosine similarity;
- maximum cosine similarity;
- share of post pairs above 0.80 similarity.

High similarity can indicate repeated wording, translated headlines, or semantically aligned amplification.

### Target specificity

Not all shared keys are equally strong.

I weighted targets approximately as:

```text
URL              high
quoted post      high
reply target     high
thread           medium
mention          medium/low depending on size
hashtag          low
```

The reason is that a hashtag is often a broad public topic, while a specific URL, quoted post, or reply target is a narrower shared object.

### Crowd penalty

I added penalties for patterns that looked like organic crowds during manual review:

- broad hashtags;
- very large mention groups;
- long-running groups over many weeks;
- large low-similarity groups;
- groups dominated by one account.

This was important because simple hashtag grouping or semantic clustering tends to find topics and crowds rather than coordinated behaviour.

---

## 9. Scoring function

The final score is an interpretable weighted combination:

```text
coordination_score =
    0.30 * semantic_similarity_score
  + 0.25 * time_burst_score
  + 0.25 * target_specificity_score
  + 0.20 * account_diversity_score
  - crowd_penalty
```

The score is clipped to `[0, 1]`.

A group is marked as coordinated when its score is above the selected threshold, but the exact score is more important than the binary flag because the evaluator uses ranking.

I used:

```text
min_score = 0.50
max_results = 150
```

This kept a reasonable number of candidates while avoiding obvious low-quality groups.

---

## 10. Calibration without labels

There were no labels, so I calibrated through inspection on the dev split.

My process was:

1. Generate broad candidate groups.
2. Inspect top groups from different candidate types.
3. Identify patterns that looked like organic crowds.
4. Identify patterns that looked more like coordinated amplification.
5. Convert those observations into scoring features and penalties.
6. Run the scoring pipeline on dev.
7. Check whether the top-ranked groups were mostly specific, multi-account, high-similarity, time-compressed candidates rather than broad hashtags.
8. Apply the same method to eval without fitting to eval-specific examples.

The dev sanity check showed that the top-ranked groups were mostly specific URL-sharing groups with multiple accounts, high semantic similarity, and compressed timing. Broad hashtags such as large ZFE/ULEZ-style topic groups were no longer dominating the ranking.

On eval, I only performed a light sanity check to make sure the output was valid and not dominated by obvious broad crowd groups. I did not tune the method to eval-specific examples.

---

## 11. Decision log

### Decision 1: Do not use hashtag grouping as the solution

The first candidate groups based on hashtags were large and easy to find, but many were broad topic discussions spread over a long time. I kept hashtags as candidate-generation keys, but assigned them low target-specificity weight and added a crowd penalty.

### Decision 2: Do not use embedding clustering alone

Embedding similarity is useful, especially because the embeddings are cross-lingual. However, semantic similarity alone can find people discussing the same topic. I therefore used embeddings only as one feature combined with time, target specificity, and account diversity.

### Decision 3: Prefer specific shared targets

Manual inspection suggested that URLs, reply targets, quoted posts, and threads were more useful than broad hashtags when combined with similar content and compressed timing. I therefore gave these keys higher target-specificity scores.

### Decision 4: Penalise long-running broad groups

Some groups had many accounts but were spread over weeks or months. These looked more like topic communities or public discussion. I added a penalty for long time spans, especially for hashtags and large mentions.

### Decision 5: Remove or down-rank single-account repetition

Some repeated content came from one account posting multiple times. That may be spam-like, but the task is about groups of accounts acting together. These groups were filtered or heavily down-ranked.

### Decision 6: Use AI for scaffolding, not final judgement

I used AI assistance to help write and revise Python scripts, generate review questions, and check whether my reasoning was too simplistic. I rejected simple suggestions such as pure embedding clustering or hashtag grouping because they did not address the crowd-vs-coordination distinction.

---

## 12. Complexity

Let:

```text
N = number of posts
K = number of candidate groups
m = number of posts in a candidate group
D = embedding dimension
```

### Loading data

Loading posts and embeddings is approximately:

```text
O(ND)
```

because embeddings are loaded for each post.

### Candidate generation

Candidate generation is approximately linear in the number of posts and keys per post:

```text
O(N * average_number_of_keys_per_post)
```

This includes hashtags, URLs, mentions, replies, threads, and quotes.

### Similarity calculation

The expensive step is pairwise similarity inside candidate groups:

```text
O(m^2 * D)
```

For this dataset size, this is manageable. To avoid very large groups becoming expensive, I sample at most a fixed number of posts per group for similarity estimation.

### Duplicate removal

The overlap check between selected clusters is approximately:

```text
O(K^2)
```

in the worst case, but it is applied after filtering and scoring, so `K` is much smaller than the total number of possible groups.

---

## 13. What would break at 10-100x scale

At 10-100x scale, the first bottlenecks would be:

1. pairwise embedding similarity in large candidate groups;
2. large hashtag or mention groups;
3. overlap checking between many candidate clusters;
4. memory usage for loading all embeddings at once.

I would change the pipeline as follows:

- use approximate nearest-neighbour search for embedding similarity;
- process data in time windows rather than all at once;
- cap or split very large hashtag/mention groups earlier;
- use sparse representations for co-activity graphs;
- store embeddings in a memory-mapped or vector-index format;
- parallelise scoring across candidate groups;
- use MinHash/LSH for near-duplicate text detection before expensive embedding comparisons.

---

## 14. Limitations

This is an unsupervised method and should be treated as a ranking pipeline, not a definitive classifier.

Main limitations:

- Some real coordinated groups may use varied wording and therefore receive lower similarity scores.
- Some organic news-sharing behaviour around a specific URL may look coordinated, especially if many users post in a short time.
- Hashtag and mention groups can contain sub-campaigns that are hidden inside larger crowds; my current pipeline may under-rank these unless they also appear through a more specific key.
- The method does not infer account authenticity, bot status, or truthfulness of content.
- The method uses only this snapshot and does not use longer-term account history.

---

## 15. Output

The final output is:

```text
results.json
```

Schema:

```json
{
  "clusters": [
    {
      "post_ids": ["...", "..."],
      "is_coordinated": true,
      "coordination_score": 0.87
    }
  ]
}
```

`coordination_score` is used to rank candidates from strongest to weakest.

---

## 16. Statistical null model
Because no ground-truth labels were available, I added a matched randomisation null model to check whether high-scoring candidate groups were stronger than expected from ordinary crowd-like behaviour.

For each tested candidate group, I generated random groups with the same key type and the same number of posts. I then computed the same coordination score for each random group and compared the observed score against this null distribution.

The empirical p-value was calculated as:


p = (1 + number of null scores >= observed score) / (1 + number of null samples)

The null model is a matched randomisation sanity check rather than a full causal test. It matches key type and group size, but does not fully control for all context such as language, URL domain, or event-specific news cycles.

---

## 17. Summary

The core idea of this solution is:

> Do not confuse topic similarity with coordination.

I therefore used a multi-signal approach: shared target, multiple accounts, semantic similarity, compressed timing, and crowd penalties. The method is intentionally interpretable because there are no labels and the main risk is false positives from organic crowds.
