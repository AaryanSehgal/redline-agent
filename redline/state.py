"""The state that flows between graph nodes."""

from typing import TypedDict


class ReviewState(TypedDict):
    contract_text: str    # input
    clauses: list         # after parsing
    readings: list        # after both sides read each clause
    unresolved: list      # ids flagged this round, still missing cross-references
    resolved: list        # ids already sent through resolve -- stops the loop repeating
    rounds: int           # loop counter -- backstop
    report: dict          # final output