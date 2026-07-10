"""
17_validate_results.py

Purpose:
    Validate the structure of results.json before submission.

This is not official evaluation because we do not have hidden labels.
It only checks that the output file follows the expected schema and is
reasonable to submit.

Checks:
    - results.json exists
    - top-level object has "clusters"
    - each cluster has:
        post_ids
        is_coordinated
        coordination_score
    - post_ids is a non-empty list of strings
    - is_coordinated is boolean
    - coordination_score is numeric
    - scores are sorted from high to low
    - duplicate clusters are warned about
    - duplicate post_ids across clusters are reported

Run from project root:
    python src/17_validate_results.py --results results.json

Or validate eval output directly:
    python src/17_validate_results.py --results outputs/eval/results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Could not find results file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_cluster(cluster: Dict[str, Any], index: int) -> List[str]:
    errors = []

    required_keys = ["post_ids", "is_coordinated", "coordination_score"]

    for key in required_keys:
        if key not in cluster:
            errors.append(f"Cluster {index}: missing key '{key}'")

    if "post_ids" in cluster:
        post_ids = cluster["post_ids"]

        if not isinstance(post_ids, list):
            errors.append(f"Cluster {index}: post_ids must be a list")
        elif len(post_ids) == 0:
            errors.append(f"Cluster {index}: post_ids list is empty")
        else:
            for pid in post_ids:
                if not isinstance(pid, str):
                    errors.append(
                        f"Cluster {index}: every post_id must be a string; got {type(pid)}"
                    )
                    break

    if "is_coordinated" in cluster:
        if not isinstance(cluster["is_coordinated"], bool):
            errors.append(f"Cluster {index}: is_coordinated must be boolean")

    if "coordination_score" in cluster:
        score = cluster["coordination_score"]

        if not is_number(score):
            errors.append(f"Cluster {index}: coordination_score must be numeric")
        elif score < 0 or score > 1:
            errors.append(
                f"Cluster {index}: coordination_score should be between 0 and 1; got {score}"
            )

    return errors


def check_sorted_scores(clusters: List[Dict[str, Any]]) -> List[str]:
    warnings = []

    scores = [
        cluster.get("coordination_score")
        for cluster in clusters
        if is_number(cluster.get("coordination_score"))
    ]

    if len(scores) != len(clusters):
        return warnings

    for i in range(1, len(scores)):
        if scores[i] > scores[i - 1]:
            warnings.append(
                "Scores are not sorted in descending order. "
                f"Cluster {i} has score {scores[i]}, previous score was {scores[i - 1]}."
            )
            break

    return warnings


def check_duplicate_clusters(clusters: List[Dict[str, Any]]) -> List[str]:
    warnings = []
    seen = {}

    for i, cluster in enumerate(clusters):
        post_ids = cluster.get("post_ids", [])

        if not isinstance(post_ids, list):
            continue

        key = tuple(sorted(post_ids))

        if key in seen:
            warnings.append(
                f"Duplicate cluster found: cluster {i} duplicates cluster {seen[key]}"
            )
        else:
            seen[key] = i

    return warnings


def check_duplicate_post_ids_across_clusters(
    clusters: List[Dict[str, Any]]
) -> Tuple[List[str], int]:
    """
    Duplicate post IDs across different clusters are not always invalid.
    A post can appear in multiple candidate groups during development.

    But for final results, too much overlap can suggest duplicate output.
    So this reports it as a warning, not an error.
    """
    warnings = []
    post_to_clusters = {}

    for i, cluster in enumerate(clusters):
        post_ids = cluster.get("post_ids", [])

        if not isinstance(post_ids, list):
            continue

        for post_id in post_ids:
            post_to_clusters.setdefault(post_id, []).append(i)

    duplicated_posts = {
        post_id: cluster_indices
        for post_id, cluster_indices in post_to_clusters.items()
        if len(cluster_indices) > 1
    }

    if duplicated_posts:
        warnings.append(
            f"{len(duplicated_posts)} post_ids appear in more than one cluster. "
            "This is not necessarily invalid, but high overlap may reduce output quality."
        )

        sample_items = list(duplicated_posts.items())[:5]

        for post_id, cluster_indices in sample_items:
            warnings.append(
                f"Post {post_id} appears in clusters {cluster_indices[:10]}"
            )

    return warnings, len(duplicated_posts)


def validate_results(data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []

    if not isinstance(data, dict):
        errors.append("Top-level JSON must be an object/dictionary")
        return errors, warnings

    if "clusters" not in data:
        errors.append("Top-level JSON must contain key 'clusters'")
        return errors, warnings

    clusters = data["clusters"]

    if not isinstance(clusters, list):
        errors.append("'clusters' must be a list")
        return errors, warnings

    if len(clusters) == 0:
        warnings.append("clusters list is empty")

    for i, cluster in enumerate(clusters):
        if not isinstance(cluster, dict):
            errors.append(f"Cluster {i}: each cluster must be an object/dictionary")
            continue

        errors.extend(validate_cluster(cluster, i))

    warnings.extend(check_sorted_scores(clusters))
    warnings.extend(check_duplicate_clusters(clusters))

    duplicate_warnings, _ = check_duplicate_post_ids_across_clusters(clusters)
    warnings.extend(duplicate_warnings)

    return errors, warnings


def print_summary(data: Dict[str, Any]) -> None:
    clusters = data.get("clusters", [])

    if not isinstance(clusters, list):
        return

    scores = [
        cluster.get("coordination_score")
        for cluster in clusters
        if is_number(cluster.get("coordination_score"))
    ]

    coordinated_count = sum(
        1 for cluster in clusters
        if cluster.get("is_coordinated") is True
    )

    total_posts = sum(
        len(cluster.get("post_ids", []))
        for cluster in clusters
        if isinstance(cluster.get("post_ids"), list)
    )

    unique_posts = set()

    for cluster in clusters:
        post_ids = cluster.get("post_ids", [])

        if isinstance(post_ids, list):
            unique_posts.update(post_ids)

    print("\nSummary")
    print("-" * 50)
    print("Number of clusters:", len(clusters))
    print("Clusters marked coordinated:", coordinated_count)
    print("Total post references:", total_posts)
    print("Unique post IDs used:", len(unique_posts))

    if scores:
        print("Highest score:", max(scores))
        print("Lowest score:", min(scores))
        print("Average score:", sum(scores) / len(scores))

    if clusters:
        print("\nFirst cluster:")
        print(json.dumps(clusters[0], indent=2, ensure_ascii=False)[:1000])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        default="results.json",
        help="Path to results.json file",
    )

    args = parser.parse_args()

    results_path = Path(args.results)
    data = load_json(results_path)

    errors, warnings = validate_results(data)

    print(f"Validated file: {results_path}")

    if errors:
        print("\nERRORS")
        print("-" * 50)

        for error in errors:
            print("ERROR:", error)

    if warnings:
        print("\nWARNINGS")
        print("-" * 50)

        for warning in warnings:
            print("WARNING:", warning)

    if not errors:
        print("\nValidation passed: results.json structure is valid.")

    print_summary(data)

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()