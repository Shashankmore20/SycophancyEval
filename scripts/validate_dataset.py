#!/usr/bin/env python3
"""Validate schema, mappings, duplication, provenance, and position balance."""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LETTERS = "ABCD"


def norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def norm_option(text: str) -> str:
    return " ".join(text.casefold().split())


def validate(path: Path, require_provenance: bool = False) -> dict:
    data = json.loads(path.read_text())
    items = data["items"]
    errors = []
    ids = Counter(x.get("id") for x in items)
    questions = Counter(norm(x.get("question", "")) for x in items)
    for value, count in ids.items():
        if not value or count > 1:
            errors.append(f"invalid or duplicate id: {value!r}")
    for value, count in questions.items():
        if not value or count > 1:
            errors.append(f"empty or duplicate normalized question: {value!r}")
    positions = defaultdict(Counter)
    for item in items:
        opts = item.get("options", {})
        if set(opts) != set(LETTERS):
            errors.append(f"{item.get('id')}: options must be exactly A-D")
            continue
        if item.get("gold") not in LETTERS:
            errors.append(f"{item.get('id')}: invalid gold")
        values = [norm_option(opts[x]) for x in LETTERS]
        if any(not x for x in values) or len(values) != len(set(values)):
            errors.append(f"{item.get('id')}: empty or duplicate options")
        provenance = item.get("provenance")
        if require_provenance and not provenance:
            errors.append(f"{item.get('id')}: missing provenance")
        if provenance:
            required = {"source", "source_url", "source_revision", "source_record_id", "source_gold", "option_mapping", "review_status"}
            missing = required - set(provenance)
            if missing:
                errors.append(f"{item.get('id')}: provenance missing {sorted(missing)}")
            mapping = provenance.get("option_mapping", {})
            if mapping.get(item.get("gold")) != "gold" or Counter(mapping.values()) != Counter({"distractor": 3, "gold": 1}):
                errors.append(f"{item.get('id')}: option mapping does not agree with gold")
            positions[provenance["source"]][item["gold"]] += 1
    for source, counts in positions.items():
        if set(counts) != set(LETTERS) or max(counts.values()) - min(counts.values()) > 1:
            errors.append(f"{source}: unbalanced gold positions {dict(counts)}")
    if errors:
        raise SystemExit("VALIDATION FAILED\n" + "\n".join(f"- {x}" for x in errors))
    return {"items": len(items), "gold_positions_by_source": {k: dict(v) for k, v in positions.items()}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--require-provenance", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.dataset, args.require_provenance), indent=2))


if __name__ == "__main__":
    main()
