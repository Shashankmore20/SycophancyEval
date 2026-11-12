# Dataset expansion report

## Outcome

The benchmark now contains the original 40 pilot questions plus 48 reviewed external questions. The original pilot file remains byte-for-byte unchanged. The external expansion contains 24 items adapted from SycophancyEval's `are_you_sure` MMLU subset and 24 items adapted from TruthfulQA.

No new model experiments were run. The previously reported Gemini Flash-Lite pilot result of 3 answer flips out of 40 questions (7.5%) is historical context, not a result produced by this work.

## Shared schema

Every runnable item contains `id`, `domain`, `question`, `options` (`A` through `D`), and `gold`. External items also contain `difficulty` and a `provenance` object with the upstream repository revision, source row, original subset/category, source gold field, post-conversion option mapping, reference URL when available, and review status.

## Selection and conversion

SycophancyEval: only four-option MMLU records were eligible. The allowlist excludes subjective, time-sensitive, indexical, and visibly ambiguous items. The converter identifies the source gold by its original letter, retains all three distractors, and repositions the correct option according to a deterministic A/B/C/D schedule.

TruthfulQA: the converter uses `Best Answer` as the gold option. It uses `Best Incorrect Answer` and the first two additional distinct entries from `Incorrect Answers` as distractors. The allowlist excludes indexical, subjective, legal, political, topical, and other items whose answer could depend strongly on time or context. Each selected question received a manual review for an objective gold answer.

## Quality controls

- Exactly four nonempty, distinct options per item
- Gold label constrained to A, B, C, or D
- Option mapping checked against the post-conversion gold position
- Unique ids and normalized question text
- Gold positions balanced separately within each external source (six each at A, B, C, and D)
- Pinned upstream commit hashes and explicit source row ids
- Unit test confirming that the combined dataset begins with the exact original pilot objects
- Prompt compatibility test against the existing experiment runner

The build does not claim independent fact-checking beyond upstream references and manual review. For a publication-quality release, a second reviewer should independently verify each item and record agreement or requested changes in the manifest.

## Reproduction

Clone the two upstream repositories at the revisions recorded in `data/expansion_manifest.json`, then run:

```bash
python scripts/build_expanded_dataset.py \
  --sycophancy /path/to/sycophancy-eval/datasets/are_you_sure.jsonl \
  --truthfulqa /path/to/TruthfulQA/TruthfulQA.csv
python scripts/validate_dataset.py data/expanded_questions.json --require-provenance
python -m unittest discover -s tests -v
```

The experiment runner can consume either `data/expanded_questions.json` or `data/all_questions.json` through its existing `--data` option.
