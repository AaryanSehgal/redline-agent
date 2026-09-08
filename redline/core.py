"""Core scoring primitives for REDLINE.

Pure functions over clause and reading dictionaries.
No API calls, no I/O -- everything here is deterministic and testable.
"""




def clauses_in_category(clauses, category, min_refs):
    """Return clauses in `category` with at least `min_refs` cross-references.

    Sorted by clause number. Returns whole clause dicts.
    """

    matched_clause = []
    for clause in clauses:
        if clause["category"] == category:
            if len(clause["refs"]) >= min_refs:
                matched_clause.append(clause)
    matched_clause.sort(key=lambda c: c["number"])
    return matched_clause

def divergence_score(reading):
    """How far apart the two sides read one clause. 0.0 = agreement, 1.0 = total."""
    score = abs(reading["our_severity"] - reading["their_severity"])
    return score


def most_divergent(readings, threshold):
    """Clause ids scoring at or above `threshold`, most divergent first."""
    risk_list = []
    for reading in readings: 
        score = divergence_score(reading)
        if score >= threshold:
            risk_list.append(reading)
    risk_list.sort(key=divergence_score, reverse=True)
    return [risk["clause_id"] for risk in risk_list]


def reference_counts(clauses):
    """Count how many times each clause number is referenced.

    High counts mark load-bearing clauses -- in-degree in the obligation graph.
    """
    ref_count = {}
    for clause in clauses:
        for ref in clause["refs"]:
            ref_count[ref] = ref_count.get(ref, 0) + 1
    return ref_count
