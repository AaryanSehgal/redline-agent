"""Analyse REDLINE's CUAD evaluation results."""

import json
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS_PATH = Path("data/eval_results.json")


def per_category(rows):
    by = defaultdict(list)
    for r in rows:
        by[(r["expected_contested"], r["label"])].append(r["divergence"])

    print("PER-CATEGORY MEAN DIVERGENCE")
    print("-" * 62)
    for (contested, label), vals in sorted(
        by.items(), key=lambda kv: -statistics.mean(kv[1])
    ):
        tag = "ASYM " if contested else "ADMIN"
        print(f"  {statistics.mean(vals):.3f}  n={len(vals):2d}  [{tag}]  {label}")

    pos = [r["divergence"] for r in rows if r["expected_contested"]]
    neg = [r["divergence"] for r in rows if not r["expected_contested"]]
    print()
    print(f"  asymmetric      n={len(pos):3d}  mean={statistics.mean(pos):.3f}")
    print(f"  administrative  n={len(neg):3d}  mean={statistics.mean(neg):.3f}")


def confusion(rows, threshold):
    tp = sum(1 for r in rows if r["divergence"] >= threshold and r["expected_contested"])
    fp = sum(1 for r in rows if r["divergence"] >= threshold and not r["expected_contested"])
    fn = sum(1 for r in rows if r["divergence"] < threshold and r["expected_contested"])
    tn = sum(1 for r in rows if r["divergence"] < threshold and not r["expected_contested"])
    return tp, fp, fn, tn


def metrics(tp, fp, fn, tn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    return precision, recall, f1, accuracy


def sweep(rows):
    print("\nTHRESHOLD SWEEP")
    print("-" * 70)
    print(f"{'thresh':>6} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'prec':>7} {'recall':>7} {'F1':>6} {'acc':>6}")
    best_t, best_f1 = 0.0, -1.0
    for i in range(1, 20):
        t = i / 20
        tp, fp, fn, tn = confusion(rows, t)
        p, r, f1, acc = metrics(tp, fp, fn, tn)
        print(f"{t:6.2f} {tp:4d} {fp:4d} {fn:4d} {tn:4d} {p:7.2f} {r:7.2f} {f1:6.2f} {acc:6.2f}")
        if f1 > best_f1:
            best_t, best_f1 = t, f1
    print(f"\nbest F1 {best_f1:.2f} at threshold {best_t:.2f}")


if __name__ == "__main__":
    rows = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    print(f"{len(rows)} scored clauses\n")

    per_category(rows)
    sweep(rows)

    baseline = sum(1 for r in rows if r["expected_contested"]) / len(rows)
    print(f"baseline, flag everything: accuracy {baseline:.2f}, recall 1.00")