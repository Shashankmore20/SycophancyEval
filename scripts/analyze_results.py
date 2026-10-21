"""
Preliminary analysis.

Reads one or more .jsonl files produced by run_pipeline.py and produces:
  1. A flip-rate bar chart (per model, per domain).
  2. A flip-point histogram (which pushback level caused the flip).
  3. A phrase-frequency chart (which sycophancy phrases show up most before a flip).
  4. A plain-text dump of a few example "flip" conversations for the slide deck.

"""
import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_records(run_files):
    records = []
    for fp in run_files:
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def flip_rate_chart(records, outdir: Path):
    by_model = defaultdict(lambda: {"eligible": 0, "flipped": 0})
    for r in records:
        if r["baseline_correct"]:
            by_model[r["model"]]["eligible"] += 1
            if r["flip_level"] is not None:
                by_model[r["model"]]["flipped"] += 1

    models = list(by_model.keys())
    rates = [100 * by_model[m]["flipped"] / by_model[m]["eligible"] if by_model[m]["eligible"] else 0
              for m in models]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(models, rates, color="#2F6F6B")
    ax.set_ylabel("Flip rate (%)")
    ax.set_title("Flip rate under graduated pushback\n(of questions answered correctly at baseline)")
    ax.set_ylim(0, 100)
    for b, m in zip(bars, models):
        n = by_model[m]["eligible"]
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2,
                 f"n={n}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(outdir / "flip_rate.png", dpi=150)
    plt.close(fig)
    return by_model


def flip_point_chart(records, outdir: Path):
    levels = [r["flip_level"] for r in records if r["flip_level"] is not None]
    if not levels:
        print("No flips recorded -- writing an all-zero flip-point chart (not skipping).")
        counts = Counter()
    else:
        counts = Counter(levels)
    xs = [1, 2, 3, 4]
    ys = [counts.get(x, 0) for x in xs]
    labels = ["mild doubt", "firm disagreement", "authority claim", "false consensus"]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, ys, color="#6D5135")
    ax.set_ylabel("Number of questions")
    ax.set_ylim(bottom=0)  # counts can't be negative
    ax.set_title("At which pushback step did the model flip?")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(outdir / "flip_point.png", dpi=150)
    plt.close(fig)


def phrase_chart(records, outdir: Path):
    phrase_counter = Counter()
    for r in records:
        for step_name, phrases in r.get("phrases_by_step", {}).items():
            phrase_counter.update(phrases)
    out_path = outdir / "phrase_frequency.png"
    if not phrase_counter:
        if out_path.exists():
            out_path.unlink()
        print("No tracked phrases found -- removed any stale phrase chart, wrote nothing.")
        return

    top = phrase_counter.most_common(10)
    labels, counts = zip(*top)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(labels, counts, color="#B0795F")
    ax.set_xlabel("Occurrences across all transcripts")
    ax.set_title("Most common phrases accompanying a flip")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def consistency_summary(records):
    verdicts = Counter(
        r["consistency_check"]["verdict"]
        for r in records if r.get("consistency_check")
    )
    return verdicts


def dump_examples(records, outdir: Path, n=3):
    flips = [r for r in records if r["flip_level"] is not None]
    out_lines = []
    if not flips:
        out_lines.append(
            f"No flips were recorded across {len(records)} question(s) in this run -- "
            "the model held its original answer through every pushback step on every "
            "question. There are no example flip transcripts to show; consider showing "
            "a resistance example instead (a transcript where the model held firm under "
            "the harshest pushback level) if you want a transcript on the slide."
        )
    for r in flips[:n]:
        out_lines.append(f"=== {r['id']} ({r['model']}) ===")
        out_lines.append(f"Gold answer: {r['gold']}  |  Flipped to: {r['flip_answer']} at pushback level {r['flip_level']}")
        for turn in r["transcript"]:
            out_lines.append(f"[{turn['speaker']}] {turn['text']}")
        if r.get("consistency_check"):
            out_lines.append(f"Consistency re-ask verdict: {r['consistency_check']['verdict']}")
        out_lines.append("")
    (outdir / "example_transcripts.txt").write_text("\n".join(out_lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="glob pattern(s) for .jsonl run files")
    ap.add_argument("--outdir", default="../results/charts")
    args = ap.parse_args()

    run_files = []
    for pattern in args.runs:
        run_files.extend(glob.glob(pattern))
    if not run_files:
        raise SystemExit(f"No files matched: {args.runs}")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    records = load_records(run_files)
    print(f"Loaded {len(records)} question-records from {len(run_files)} run file(s).")

    by_model = flip_rate_chart(records, outdir)
    flip_point_chart(records, outdir)
    phrase_chart(records, outdir)
    dump_examples(records, outdir)

    print("\n--- Summary ---")
    for model, d in by_model.items():
        print(f"{model}: {d['flipped']}/{d['eligible']} flipped "
              f"({100*d['flipped']/d['eligible'] if d['eligible'] else 0:.1f}%)")
    print("Consistency re-ask verdicts:", dict(consistency_summary(records)))
    print(f"\nCharts written to {outdir}/")


if __name__ == "__main__":
    main()