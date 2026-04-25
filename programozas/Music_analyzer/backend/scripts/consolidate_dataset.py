import csv
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.services.genre_taxonomy import genre_family_for, normalize_genre_label

INPUT_CSV = os.path.join(project_root, "dataset.csv")
OUTPUT_CSV = os.path.join(project_root, "cleaned_dataset.csv")

NON_GENRE_LABELS = {
    "anime",
    "brazil",
    "british",
    "children",
    "comedy",
    "disney",
    "french",
    "german",
    "happy",
    "indian",
    "iranian",
    "j-idol",
    "kids",
    "malay",
    "party",
    "sad",
    "sleep",
    "study",
    "summer",
    "turkish",
    "world-music",
}

WEAK_GENRE_LABELS = {
    "alternative",
    "dance",
    "electronic",
    "indie",
    "pop",
    "rock",
}

def _normalize(value: Optional[str]) -> Optional[str]:
    normalized = normalize_genre_label(value)
    return normalized or None

def _is_non_genre(label: str) -> bool:
    return label in NON_GENRE_LABELS

def _is_weak_genre(label: str) -> bool:
    return label in WEAK_GENRE_LABELS

def _specificity_score(label: str) -> int:
    score = 0
    if "-" in label:
        score += 3
    if any(token in label for token in ("techno", "house", "trance", "hardstyle", "metal", "punk", "jazz")):
        score += 3
    if label not in WEAK_GENRE_LABELS:
        score += 2
    if label not in NON_GENRE_LABELS:
        score += 2
    return score

def _pick_consolidated_genre(labels: Iterable[str]) -> Tuple[Optional[str], str]:
    counter = Counter(label for label in labels if label)
    if not counter:
        return None, "missing"

    filtered = Counter({label: count for label, count in counter.items() if not _is_non_genre(label)})
    if not filtered:
        return None, "non_genre_only"

    ranked = sorted(
        filtered.items(),
        key=lambda item: (
            item[1],
            0 if _is_weak_genre(item[0]) else 1,
            _specificity_score(item[0]),
            len(item[0]),
        ),
        reverse=True,
    )
    best_label, best_count = ranked[0]

    if len(ranked) == 1:
        return best_label, "high"

    second_label, second_count = ranked[1]
    if best_count >= second_count + 2:
        return best_label, "high"

    best_family = genre_family_for(best_label)
    second_family = genre_family_for(second_label)
    if best_family and best_family == second_family:
        return best_label, "medium"

    return best_label, "low"

def _choose_canonical_row(rows: List[Dict[str, str]]) -> Dict[str, str]:
    def sort_key(row: Dict[str, str]) -> Tuple[int, int, int]:
        popularity = 0
        try:
            popularity = int(float(row.get("popularity") or 0))
        except (TypeError, ValueError):
            popularity = 0
        release_date = row.get("track_album_release_date") or ""
        explicit = 1 if str(row.get("explicit") or "").lower() == "true" else 0
        return (popularity, len(release_date), explicit)

    return max(rows, key=sort_key)

def consolidate_dataset(input_csv: str = INPUT_CSV, output_csv: str = OUTPUT_CSV) -> Dict[str, int]:
    grouped_rows: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    missing_track_id_rows = 0

    with open(input_csv, "r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            track_id = (row.get("track_id") or "").strip()
            if not track_id:
                missing_track_id_rows += 1
                continue
            grouped_rows[track_id].append(row)

    extra_columns = ["raw_genres", "genre_confidence", "genre_variant_count", "genre_family"]
    output_fieldnames = fieldnames + [col for col in extra_columns if col not in fieldnames]

    written_rows = 0
    duplicate_groups = 0
    low_confidence_rows = 0

    with open(output_csv, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
        writer.writeheader()

        for track_id, rows in grouped_rows.items():
            if len(rows) > 1:
                duplicate_groups += 1

            canonical = dict(_choose_canonical_row(rows))
            raw_labels = []
            for row in rows:
                label = _normalize(row.get("track_genre"))
                if label:
                    raw_labels.append(label)

            consolidated_genre, confidence = _pick_consolidated_genre(raw_labels)
            if confidence == "low":
                low_confidence_rows += 1

            canonical["track_genre"] = consolidated_genre or ""
            canonical["genre_family"] = genre_family_for(consolidated_genre) or ""
            canonical["raw_genres"] = "|".join(sorted(set(raw_labels)))
            canonical["genre_confidence"] = confidence
            canonical["genre_variant_count"] = str(len(set(raw_labels)))
            writer.writerow(canonical)
            written_rows += 1

    return {
        "input_groups": len(grouped_rows),
        "written_rows": written_rows,
        "duplicate_groups": duplicate_groups,
        "low_confidence_rows": low_confidence_rows,
        "missing_track_id_rows": missing_track_id_rows,
    }

if __name__ == "__main__":
    stats = consolidate_dataset()
    print("Consolidation finished.")
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"Output: {OUTPUT_CSV}")
