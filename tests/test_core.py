"""Tests for the scoring primitives.

These run with no API key -- core.py never touches the network, which is
exactly why the scoring logic lives in its own module.
"""

from redline.core import (
    clauses_in_category,
    divergence_score,
    most_divergent,
    reference_counts,
)


def test_divergence_is_zero_when_both_sides_agree():
    reading = {"clause_id": "c1", "our_severity": 0.5, "their_severity": 0.5}
    assert divergence_score(reading) == 0.0


def test_divergence_is_symmetric():
    a = {"clause_id": "c1", "our_severity": 0.9, "their_severity": 0.2}
    b = {"clause_id": "c1", "our_severity": 0.2, "their_severity": 0.9}
    assert divergence_score(a) == divergence_score(b)


def test_most_divergent_ranks_highest_first():
    readings = [
        {"clause_id": "low", "our_severity": 0.5, "their_severity": 0.5},
        {"clause_id": "high", "our_severity": 1.0, "their_severity": 0.0},
        {"clause_id": "mid", "our_severity": 0.8, "their_severity": 0.4},
    ]
    assert most_divergent(readings, 0.3) == ["high", "mid"]


def test_reference_counts_counts_repeats():
    clauses = [
        {"number": "3.1", "refs": ["14.2"]},
        {"number": "9.1", "refs": ["14.2", "7.4"]},
        {"number": "12.3", "refs": ["7.4"]},
    ]
    assert reference_counts(clauses) == {"14.2": 2, "7.4": 2}


def test_reference_counts_ignores_clauses_with_no_refs():
    assert reference_counts([{"number": "14.5", "refs": []}]) == {}


def test_clauses_in_category_requires_exact_match():
    clauses = [
        {"number": "9.1", "heading": "Termination", "category": "termination", "refs": []},
    ]
    assert clauses_in_category(clauses, "term", 0) == []
    assert len(clauses_in_category(clauses, "termination", 0)) == 1