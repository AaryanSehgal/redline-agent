"""LangGraph orchestration for REDLINE."""

from langgraph.graph import END, START, StateGraph

from redline.core import divergence_score, most_divergent, reference_counts
from redline.llm import read_both_sides
from redline.parser import parse
from redline.state import ReviewState

THRESHOLD = 0.3
MAX_ROUNDS = 2


def parse_node(state: ReviewState) -> dict:
    """Text in, clauses out."""
    clauses = parse(state["contract_text"])
    return {"clauses": clauses, "rounds": 0, "resolved": [], "unresolved": []}


def read_node(state: ReviewState) -> dict:
    """Read every clause from both sides."""
    readings = [read_both_sides(c) for c in state["clauses"]]
    return {"readings": readings}


def check_node(state: ReviewState) -> dict:
    """Flagged clauses that reference something the model never saw."""
    flagged = most_divergent(state["readings"], THRESHOLD)
    clause_by_id = {c["id"]: c for c in state["clauses"]}

    unresolved = []
    for cid in flagged:
        if cid in state["resolved"]:
            continue                          # already handled, don't loop on it
        if clause_by_id[cid]["refs"]:
            unresolved.append(cid)

    return {"unresolved": unresolved}


def resolve_node(state: ReviewState) -> dict:
    """Re-read unresolved clauses with their referenced clauses attached."""
    clause_by_id = {c["id"]: c for c in state["clauses"]}
    clause_by_number = {c["number"]: c for c in state["clauses"]}
    reading_by_id = {r["clause_id"]: r for r in state["readings"]}

    for cid in state["unresolved"]:
        clause = clause_by_id[cid]

        parts = [clause["text"]]
        for ref in clause["refs"]:
            referenced = clause_by_number.get(ref)
            if referenced:
                parts.append(
                    f"\n\nReferenced clause {ref} ({referenced['heading']}): "
                    f"{referenced['text']}"
                )

        combined = "".join(parts)
        reading_by_id[cid] = read_both_sides({"id": cid, "text": combined})

    return {
        "readings": list(reading_by_id.values()),
        "rounds": state["rounds"] + 1,
        "resolved": state["resolved"] + state["unresolved"],
    }


def report_node(state: ReviewState) -> dict:
    """Assemble the final report."""
    clause_by_id = {c["id"]: c for c in state["clauses"]}
    reading_by_id = {r["clause_id"]: r for r in state["readings"]}
    flagged = most_divergent(state["readings"], THRESHOLD)

    items = []
    for cid in flagged:
        clause = clause_by_id[cid]
        r = reading_by_id[cid]
        items.append({
            "number": clause["number"],
            "heading": clause["heading"],
            "divergence": round(divergence_score(r), 2),
            "client_severity": r["our_severity"],
            "supplier_severity": r["their_severity"],
            "client_reason": r["our_reason"],
            "supplier_reason": r["their_reason"],
            "refs": clause["refs"],
            "cross_refs_resolved": cid in state["resolved"],
        })

    return {"report": {
        "clauses_reviewed": len(state["clauses"]),
        "rounds": state["rounds"],
        "flagged": items,
        "load_bearing": reference_counts(state["clauses"]),
    }}


def route_after_check(state: ReviewState) -> str:
    """Loop back to resolve, or finish."""
    if state["rounds"] >= MAX_ROUNDS:
        return "report"
    if state["unresolved"]:
        return "resolve"
    return "report"


# ---- wiring: given ----
def build_graph():
    g = StateGraph(ReviewState)

    g.add_node("parse", parse_node)
    g.add_node("read", read_node)
    g.add_node("check", check_node)
    g.add_node("resolve", resolve_node)
    g.add_node("report", report_node)

    g.add_edge(START, "parse")
    g.add_edge("parse", "read")
    g.add_edge("read", "check")

    g.add_conditional_edges(
        "check",
        route_after_check,
        {"resolve": "resolve", "report": "report"},
    )

    g.add_edge("resolve", "check")      # <-- THE CYCLE
    g.add_edge("report", END)

    return g.compile()


if __name__ == "__main__":
    with open("data/sample_contract.txt", encoding="utf-8") as f:
        text = f.read()

    graph = build_graph()
    final = graph.invoke(
        {"contract_text": text, "rounds": 0},
        config={"recursion_limit": 25},
    )
    print(final["report"])