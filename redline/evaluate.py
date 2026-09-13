"""Build the CUAD evaluation set for REDLINE."""

import json
import random
from collections import Counter
from pathlib import Path

from datasets import load_dataset

SEED = 42
MIN_CHARS = 150
MAX_CHARS = 2000
PER_CATEGORY = 8

ASYMMETRIC = [
    "Uncapped Liability",
    "Cap On Liability",
    "Termination For Convenience",
    "Non-Compete",
    "Exclusivity",
    "Ip Ownership Assignment",
    "Change Of Control",
    "Minimum Commitment",
]

ADMINISTRATIVE = [
    "Governing Law",
    "Renewal Term",
    "Notice Period To Terminate Renewal",
    "Expiration Date",
]

OUT_PATH = Path("data/eval_set.json")


def build_eval_set():
    rows = load_dataset(
        "dvgodoy/CUAD_v1_Contract_Understanding_clause_classification"
    )["train"]

    by_label = {}
    for row in rows:
        text = row["clause"].strip()
        if not (MIN_CHARS <= len(text) <= MAX_CHARS):
            continue
        by_label.setdefault(row["label"], []).append(text)

    rng = random.Random(SEED)
    eval_set = []

    for label in ASYMMETRIC + ADMINISTRATIVE:
        pool = by_label.get(label, [])
        if len(pool) < PER_CATEGORY:
            print(f"WARNING only {len(pool)} usable clauses for {label}")

        for i, text in enumerate(rng.sample(pool, min(PER_CATEGORY, len(pool)))):
            eval_set.append({
                "id": f"{label.replace(' ', '_')}_{i}",
                "text": text,
                "label": label,
                "expected_contested": label in ASYMMETRIC,
            })

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(eval_set, indent=2), encoding="utf-8")
    return eval_set


if __name__ == "__main__":
    eval_set = build_eval_set()
    print(f"\n{len(eval_set)} clauses -> {OUT_PATH}")
    print(Counter(e["expected_contested"] for e in eval_set))
    print("\nfirst entry:")
    print(json.dumps(eval_set[0], indent=2)[:700])