#!/usr/bin/env python3
"""Build the reviewed external benchmark in the project's shared MCQ schema."""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

LETTERS = "ABCD"


def normalized(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def normalized_option(text: str) -> str:
    return " ".join(text.casefold().split())


def split_semicolon(text: str) -> list[str]:
    return [part.strip() for part in text.split(";") if part.strip()]


def domain_from_mmlu(topic: str) -> str:
    topic = topic.removesuffix("_test")
    if any(x in topic for x in ("history", "prehistory")):
        return "history"
    if any(x in topic for x in ("geography", "world_religions", "global_facts")):
        return "geography_and_culture"
    if any(x in topic for x in ("physics", "chemistry", "biology", "astronomy", "medicine", "anatomy", "genetics")):
        return "science_and_medicine"
    if any(x in topic for x in ("math", "statistics", "computer", "machine_learning")):
        return "math_and_computing"
    return "social_science_and_humanities"


def domain_from_truthfulqa(category: str) -> str:
    if category in {"Science", "Weather", "Nutrition", "Health"}:
        return "science_and_health"
    if category in {"History", "Confusion: People", "Confusion: Places", "Misquotations"}:
        return "history_and_culture"
    if category in {"Statistics", "Economics", "Finance"}:
        return "quantitative_reasoning"
    return "misconceptions_and_reasoning"


def place_gold(correct: str, distractors: list[str], gold_letter: str) -> tuple[dict, dict]:
    values = list(distractors[:3])
    values.insert(LETTERS.index(gold_letter), correct)
    options = dict(zip(LETTERS, values))
    mapping = {letter: ("gold" if value == correct else "distractor") for letter, value in options.items()}
    return options, mapping


def validate_item(item: dict) -> None:
    assert set(item["options"]) == set(LETTERS)
    assert item["gold"] in LETTERS
    vals = [normalized_option(v) for v in item["options"].values()]
    assert all(vals) and len(vals) == len(set(vals))


def build_sycophancy(path: Path, selected: list[int], revision: str) -> list[dict]:
    wanted = set(selected)
    rows = []
    for row_index, line in enumerate(path.read_text().splitlines()):
        if row_index not in wanted:
            continue
        raw = json.loads(line)
        base = raw["base"]
        if base.get("dataset") != "mmlu_mc_cot" or base.get("letters") != LETTERS:
            raise ValueError(f"SycophancyEval row {row_index} is not a four-option MMLU item")
        source_gold = base["correct_letter"]
        correct = base[source_gold]
        distractors = [base[x] for x in LETTERS if x != source_gold]
        gold = LETTERS[len(rows) % 4]
        options, mapping = place_gold(correct, distractors, gold)
        item = {
            "id": f"syc_eval_{row_index:04d}",
            "domain": domain_from_mmlu(base["topic"]),
            "difficulty": "unspecified",
            "question": base["question"].strip(),
            "options": options,
            "gold": gold,
            "provenance": {
                "source": "SycophancyEval are_you_sure",
                "source_url": "https://github.com/meg-tong/sycophancy-eval/blob/main/datasets/are_you_sure.jsonl",
                "source_revision": revision,
                "source_record_id": row_index,
                "original_dataset": base["dataset"],
                "original_subset": base["topic"],
                "source_gold": source_gold,
                "option_mapping": mapping,
                "review_status": "manually_reviewed_objective_gold",
            },
        }
        validate_item(item)
        rows.append(item)
    if len(rows) != len(selected):
        raise ValueError("One or more selected SycophancyEval rows were not found")
    return rows


def build_truthfulqa(path: Path, selected: list[int], revision: str) -> list[dict]:
    with path.open(newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = []
    for csv_row_index in selected:
        raw = source_rows[csv_row_index]
        correct = raw["Best Answer"].strip()
        distractors = []
        for candidate in [raw["Best Incorrect Answer"], *split_semicolon(raw["Incorrect Answers"])]:
            if normalized(candidate) != normalized(correct) and normalized(candidate) not in {normalized(x) for x in distractors}:
                distractors.append(candidate.strip())
        if len(distractors) < 3:
            raise ValueError(f"TruthfulQA row {csv_row_index} has fewer than three distinct distractors")
        gold = LETTERS[len(rows) % 4]
        options, mapping = place_gold(correct, distractors, gold)
        item = {
            "id": f"truthfulqa_{csv_row_index:04d}",
            "domain": domain_from_truthfulqa(raw["Category"]),
            "difficulty": "unspecified",
            "question": raw["Question"].strip(),
            "options": options,
            "gold": gold,
            "provenance": {
                "source": "TruthfulQA multiple choice adaptation",
                "source_url": "https://github.com/sylinrl/TruthfulQA/blob/main/TruthfulQA.csv",
                "source_revision": revision,
                "source_record_id": csv_row_index,
                "original_dataset": "TruthfulQA",
                "original_subset": raw["Category"],
                "source_gold": "Best Answer",
                "source_reference": raw["Source"],
                "option_mapping": mapping,
                "review_status": "manually_reviewed_objective_gold",
            },
        }
        validate_item(item)
        rows.append(item)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sycophancy", type=Path, required=True)
    parser.add_argument("--truthfulqa", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("data/expansion_manifest.json"))
    parser.add_argument("--pilot", type=Path, default=Path("data/pilot_questions.json"))
    parser.add_argument("--out", type=Path, default=Path("data/expanded_questions.json"))
    parser.add_argument("--combined-out", type=Path, default=Path("data/all_questions.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    external = build_sycophancy(args.sycophancy, manifest["sycophancy_eval"]["rows"], manifest["sycophancy_eval"]["revision"])
    external += build_truthfulqa(args.truthfulqa, manifest["truthfulqa"]["rows"], manifest["truthfulqa"]["revision"])
    seen = {}
    for item in external:
        key = normalized(item["question"])
        if key in seen:
            raise ValueError(f"Duplicate questions: {seen[key]} and {item['id']}")
        seen[key] = item["id"]
    payload = {
        "_meta": {
            "description": "Reviewed external expansion for the Group 9 answer-flip experiment.",
            "schema_version": "1.0",
            "build_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            "item_count": len(external),
            "notes": "Gold positions are deterministically balanced within each source. No model results are included.",
        },
        "items": external,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    pilot = json.loads(args.pilot.read_text())
    combined = {
        "_meta": {
            "description": "Original 40-item pilot followed by the reviewed external expansion.",
            "schema_version": "1.0",
            "pilot_preserved": True,
            "item_count": len(pilot["items"]) + len(external),
        },
        "items": pilot["items"] + external,
    }
    args.combined_out.write_text(json.dumps(combined, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(external)} external items to {args.out}")
    print(f"Wrote {len(combined['items'])} total items to {args.combined_out}")


if __name__ == "__main__":
    main()
