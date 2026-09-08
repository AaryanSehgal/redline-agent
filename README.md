# REDLINE

**Two AI agents read the same contract clause with opposite interests. Where they disagree, that's your risk.**

Most contract-review tools score clauses for risk. REDLINE scores clauses for **disagreement** — because the clauses that cause disputes aren't the obviously dangerous ones, they're the ones where two competent readers walk away with different pictures of the deal.

---

## Status: in progress

This is being built in the open. What works today is genuinely working, and what doesn't is listed below rather than hidden.

**Working now**

- Parses a plain-text contract into structured clauses with cross-references
- Reads every clause twice — once as the Client, once as the Supplier — using structurally identical prompts
- Scores divergence between the two readings and ranks clauses by it
- Identifies "load-bearing" clauses (the ones other clauses depend on)
- Retries failed API calls with exponential backoff

**Not built yet**

- LangGraph orchestration and the cross-reference resolution loop
- Persistence (SQLite) and cross-contract reporting
- Evaluation against CUAD's attorney-labelled clauses
- The full obligation graph
- Web interface, Docker, deployment
- Automated tests

---

## What it found on a real run

Sample supply agreement, 8 clauses, reviewed in 50 seconds.

**Clause 12.3 — Indemnity. Divergence 1.00 (maximum).**

> **Client's reading — severity 1.00:** *"This indemnity clause requires the Client to defend and hold harmless the Supplier even when the Supplier is negligent, creating unlimited liability for the Client including for losses caused by the Supplier's own failures."*
>
> **Supplier's reading — severity 0.00:** *"This clause protects the Supplier by requiring the Client to indemnify and defend the Supplier against claims arising from the Client's use of deliverables, even when partially caused by the Supplier's own negligence."*

Same words. One side says "do not sign", the other says "no danger at all". A conventional risk scorer would label this "indemnity clause, medium risk" and move on.

**Clause 14.2 — Disputed Invoices. Divergence 0.70, and it points the other way.** Client 0.00, Supplier 0.70 — the Supplier is the exposed party here. REDLINE isn't a client advocate; it reads both sides.

---

## Why this needs a graph, not a chain

On the first run, both agents said this about clause 9.1, unprompted:

> *"...though clause 7.4 (which I cannot see) may impose conditions that could change this assessment."*

Contracts are written as lists but they don't work as lists. Clause 3.1 says pay in 30 days — but 14.2 suspends that obligation if the invoice is disputed. Read 3.1 alone and you get the wrong answer.

So the system has to notice a missing cross-reference, go fetch it, and re-judge with it in hand. That's a **cycle**, which is why the orchestration layer is LangGraph rather than a linear chain. The models asked for it in the output above before a single line of graph code was written.

---

## How it works

```
contract.txt
     │
     ▼
  parser.py      splits text into clauses, extracts cross-references
     │
     ▼
   llm.py        each clause read twice, opposed system prompts
     │
     ▼
  core.py        divergence scoring, ranking, reference counting
     │
     ▼
  ranked risk report
```

Each module does exactly one transformation. `parser.py` never calls a model. `llm.py` never does arithmetic. `core.py` never touches the network — which means the scoring logic runs and can be tested with no API key at all.

### Design note: prompt symmetry

The two system prompts are word-for-word identical except for the party named. This is deliberate. If one prompt were longer or more leading than the other, the divergence score would be measuring *prompt asymmetry* rather than genuine disagreement between the parties, and the entire premise would collapse.

---

## Run it

```bash
git clone https://github.com/<your-username>/redline-agent
cd redline-agent

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

cp .env.example .env            # then add your Anthropic API key

python run.py
```

---

## Known limitations

Written plainly, because a tool that hides its failure modes is worse than one that names them.

- **Plain text only.** No PDF or DOCX. Real contracts arrive as PDFs.
- **One numbering format.** Clauses must be `N.N` at the start of a line. `Section 3.1`, `ARTICLE III`, and `(a)/(b)` sub-clauses are not handled.
- **Headings must be inline** with the clause body, ending at the first full stop.
- **No cross-reference resolution.** Each clause is judged alone, which the models themselves flag as a problem (see above). This is the next thing being built.
- **Not evaluated.** There is no accuracy number yet. Until it is scored against CUAD's attorney labels, "it found a real indemnity problem" is an anecdote, not evidence.
- **Sequential API calls.** 8 clauses take ~50 seconds. Concurrency would cut this substantially.
- **Not legal advice.** This is a review assistant that surfaces clauses worth a human's attention. It does not replace one.

---

## Roadmap

1. LangGraph orchestration with the cross-reference resolution cycle
2. SQLite persistence and cross-contract queries
3. Evaluation against CUAD — precision and recall against attorney labels
4. Obligation graph: who owes what, to whom, by when, conditional on what
5. Cost routing: a fine-tuned classifier handles routine clauses, the model pair handles only contested ones
6. Web interface and deployment

---

## Built by

Aaryan Sehgal — BSc Artificial Intelligence, transitioning into AI engineering.
Sydney, Australia.
