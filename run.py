"""Run REDLINE end to end on one contract."""

import time

from redline.core import divergence_score, most_divergent, reference_counts
from redline.llm import read_both_sides
from redline.parser import parse

THRESHOLD = 0.3


def main(path):
    with open(path, encoding="utf-8") as f:
        clauses = parse(f.read())
    print(f"parsed {len(clauses)} clauses\n")

    readings = []
    started = time.time()
    for clause in clauses:
        print(f"  reading {clause['number']} {clause['heading']}...")
        readings.append(read_both_sides(clause))
    elapsed = time.time() - started

    clause_by_id = {c["id"]: c for c in clauses}
    reading_by_id = {r["clause_id"]: r for r in readings}

    flagged = most_divergent(readings, THRESHOLD)

    print(f"\nreviewed {len(clauses)} clauses in {elapsed:.1f}s")
    print(f"{len(flagged)} flagged above divergence {THRESHOLD}\n")

    for cid in flagged:
        clause = clause_by_id[cid]
        r = reading_by_id[cid]
        print(f"{clause['number']}  {clause['heading']}   divergence {divergence_score(r):.2f}")
        print(f"   client   {r['our_severity']:.2f}  {r['our_reason']}")
        print(f"   supplier {r['their_severity']:.2f}  {r['their_reason']}")
        print()

    print("LOAD-BEARING CLAUSES (referenced by others):")
    print(reference_counts(clauses))


if __name__ == "__main__":
    main("data/sample_contract.txt")