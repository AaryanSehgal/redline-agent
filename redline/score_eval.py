"""Score the CUAD eval set with REDLINE's two-agent reader.

Separate from building the set, and separate from analysing it -- so an
expensive API pass happens once and can be re-analysed for free.
"""

import asyncio
import json
import time
from pathlib import Path

from redline.core import divergence_score
from redline.llm import read_both_sides_async

EVAL_PATH = Path("data/eval_set.json")
RESULTS_PATH = Path("data/eval_results.json")
MAX_CONCURRENT = 5


async def score_one(entry, sem):
    """Score one clause. Returns None on failure instead of killing the run."""
    async with sem:
        try:
            reading = await read_both_sides_async(entry)
        except Exception as e:
            print(f"  FAILED {entry['id']}: {e}")
            return None

    return {
        "id": entry["id"],
        "label": entry["label"],
        "expected_contested": entry["expected_contested"],
        "our_severity": reading["our_severity"],
        "their_severity": reading["their_severity"],
        "divergence": divergence_score(reading),
        "our_reason": reading["our_reason"],
        "their_reason": reading["their_reason"],
    }


async def score_all(eval_set):
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    results = await asyncio.gather(*(score_one(e, sem) for e in eval_set))
    return [r for r in results if r is not None]


if __name__ == "__main__":
    eval_set = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    print(f"scoring {len(eval_set)} clauses, {len(eval_set) * 2} API calls...")

    started = time.time()
    results = asyncio.run(score_all(eval_set))
    elapsed = time.time() - started

    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n{len(results)}/{len(eval_set)} scored in {elapsed:.1f}s -> {RESULTS_PATH}")