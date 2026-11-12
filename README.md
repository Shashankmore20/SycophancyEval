# SycophancyEval

Group 9's controlled answer-flip experiment. The repository preserves the original 40-question pilot and adds a reviewed, reproducible external expansion.

## Datasets

- `data/pilot_questions.json`: original 40-item pilot, unchanged
- `data/expanded_questions.json`: 48 reviewed external items
- `data/all_questions.json`: pilot followed by the external items
- `data/expansion_manifest.json`: pinned source revisions and manual review allowlist

See `docs/DATASET_REPORT.md` for schema, provenance, filtering decisions, limitations, and reproduction instructions.

## Validate

```bash
python scripts/validate_dataset.py data/expanded_questions.json --require-provenance
python -m unittest discover -s tests -v
```

## Run

Start with a zero-cost dry run. This selects four questions with broad source,
domain, and gold-position coverage, prints their prompts, and makes no API calls:

```bash
python scripts/run_pipeline.py --data data/all_questions.json \
  --ladder data/pushback_ladder.json --smoke-test 4 --dry-run
```

For the smallest useful live smoke test, run two questions. The hard budget below
prevents the process from making more than 12 provider calls, including retries:

```bash
python scripts/run_pipeline.py --provider gemini --model MODEL_NAME \
  --data data/all_questions.json --ladder data/pushback_ladder.json \
  --smoke-test 2 --max-api-calls 12 --out results/smoke_2.jsonl
```

Each question uses one baseline call. A baseline-correct question can use four
pushback calls, plus one fresh consistency call if it flips, for a worst case of
six calls per question. The runner prints the selected question ids and call
ceiling before it starts. A full-dataset run now requires `--confirm-full-run`.

The first Ctrl+C now requests a safe stop after the current question. The runner
saves that question before exiting. Re-run the same command with `--resume` to
skip saved question ids and continue. A second Ctrl+C forces an immediate stop.
Gemini requests time out after 30 seconds by default, and SDK-internal retries
are disabled so every retry is visible to the runner's hard call budget.

After the smoke test, the pipeline accepts any dataset file through `--data`:

```bash
python scripts/run_pipeline.py --provider gemini --model MODEL_NAME \
  --data data/expanded_questions.json --ladder data/pushback_ladder.json \
  --out results/example_run.jsonl --confirm-full-run
```

This repository does not include newly generated model results for the expanded data.
