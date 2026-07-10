from pathlib import Path
import pandas as pd


SPLIT = "dev"

OUTPUT_DIR = Path("outputs") / SPLIT

REVIEW_CANDIDATES_PATH = OUTPUT_DIR / "review_candidates.csv"
MANUAL_NOTES_PATH = OUTPUT_DIR / "manual_review_notes.csv"


def main():
    review = pd.read_csv(REVIEW_CANDIDATES_PATH)

    notes = review[[
        "selection_reason",
        "key_type",
        "key_value",
        "post_count",
        "account_count",
        "time_span_minutes",
        "first_time",
        "last_time",
    ]].copy()

    notes["manual_assessment"] = ""
    notes["content_similarity"] = ""
    notes["timing_pattern"] = ""
    notes["target_specificity"] = ""
    notes["why_this_matters"] = ""

    notes.to_csv(MANUAL_NOTES_PATH, index=False)

    print("Saved manual review notes file:")
    print(MANUAL_NOTES_PATH)


if __name__ == "__main__":
    main()