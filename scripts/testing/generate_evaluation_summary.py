"""
Consolidated evaluation summary.

Reads every experiment's results.csv under data/experiments/, and
produces one aggregate summary — the "measured evaluation data" per
Section 57 point 12 of the project spec, and the raw material for
Section 35's before/after comparison graphs.

Generic by design: it doesn't hardcode per-experiment logic. Any
experiment folder with a results.csv gets summarized automatically,
so this keeps working unchanged as later phases add more experiments.

For each column in a results.csv, it infers a reasonable summary:
  - True/False columns  -> count of each + rate
  - numeric columns     -> count, mean, min, max
  - anything else       -> skipped (e.g. free-text error messages)

Usage:
    python3 scripts/testing/generate_evaluation_summary.py
"""

import csv
import json
import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "data" / "experiments"


def load_results_csv(csv_path: Path) -> list:
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def infer_column_type(values: list) -> str:
    non_empty = [v for v in values if v != ""]
    if not non_empty:
        return "empty"
    if all(v in ("True", "False") for v in non_empty):
        return "boolean"
    try:
        [float(v) for v in non_empty]
        return "numeric"
    except ValueError:
        return "text"


def summarize_column(name: str, values: list) -> dict:
    col_type = infer_column_type(values)
    non_empty = [v for v in values if v != ""]

    if col_type == "boolean":
        true_count = sum(1 for v in non_empty if v == "True")
        false_count = len(non_empty) - true_count
        return {
            "type": "boolean",
            "count": len(non_empty),
            "true_count": true_count,
            "false_count": false_count,
            "true_rate": round(true_count / len(non_empty), 3) if non_empty else None,
        }

    if col_type == "numeric":
        nums = [float(v) for v in non_empty]
        return {
            "type": "numeric",
            "count": len(nums),
            "mean": round(mean(nums), 3),
            "min": round(min(nums), 3),
            "max": round(max(nums), 3),
        }

    return {"type": col_type, "count": len(non_empty)}


def summarize_experiment(csv_path: Path) -> dict:
    rows = load_results_csv(csv_path)
    if not rows:
        return {"run_count": 0, "columns": {}}

    columns = {}
    for column_name in rows[0].keys():
        values = [row[column_name] for row in rows]
        summary = summarize_column(column_name, values)
        if summary["type"] not in ("text", "empty"):
            columns[column_name] = summary

    return {"run_count": len(rows), "columns": columns}


def print_summary(experiment_id: str, summary: dict) -> None:
    print(f"\n=== {experiment_id} ({summary['run_count']} run(s)) ===")
    if summary["run_count"] == 0:
        print("  (no data)")
        return
    for column_name, stats in summary["columns"].items():
        if stats["type"] == "boolean":
            print(f"  {column_name:28s} True: {stats['true_count']:3d}  "
                  f"False: {stats['false_count']:3d}  "
                  f"(true rate: {stats['true_rate']})")
        elif stats["type"] == "numeric":
            print(f"  {column_name:28s} mean={stats['mean']}  "
                  f"min={stats['min']}  max={stats['max']}  n={stats['count']}")


def main() -> None:
    if not EXPERIMENTS_DIR.exists():
        print(f"No experiments directory found at {EXPERIMENTS_DIR}")
        sys.exit(1)

    all_summaries = {}
    for experiment_dir in sorted(EXPERIMENTS_DIR.iterdir()):
        if not experiment_dir.is_dir():
            continue
        csv_path = experiment_dir / "results.csv"
        if not csv_path.exists():
            continue

        summary = summarize_experiment(csv_path)
        all_summaries[experiment_dir.name] = summary
        print_summary(experiment_dir.name, summary)

    if not all_summaries:
        print("No experiment results.csv files found yet. "
              "Run an experiment first, e.g.:")
        print("  python3 experiments/01-modbus-control/run_experiment.py 127.0.0.1 5020 6 1000")
        return

    output_path = EXPERIMENTS_DIR / "evaluation_summary.json"
    with open(output_path, "w") as f:
        json.dump(all_summaries, f, indent=2)
    print(f"\n[summary] Saved consolidated summary: {output_path}")


if __name__ == "__main__":
    main()