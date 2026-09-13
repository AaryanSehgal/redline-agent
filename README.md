# REDLINE

**Two AI agents read the same contract clause with opposite interests. Where they disagree, that's your risk.**

Most contract-review tools score clauses for risk. REDLINE scores clauses for **disagreement** — because the clauses that cause disputes aren't the obviously dangerous ones, they're the ones where two competent readers walk away with different pictures of the deal.

---

## Status: in progress

Built in the open. What works is genuinely working; what doesn't is listed rather than hidden.

**Working now**

- Parses plain-text contracts into structured clauses with cross-references
- Reads every clause twice — as the Client and as the Supplier — using structurally identical prompts
- Scores divergence between the two readings and ranks clauses by it
- **LangGraph orchestration with a cross-reference resolution cycle** — when a flagged clause depends on a clause the model never saw, the graph loops back, attaches it, and re-judges
- **Concurrent API calls with bounded concurrency** — 50s → 21s, capped by a semaphore
- Identifies load-bearing clauses (those other clauses depend on)
- Retries failed calls with exponential backoff
- **Evaluation harness against CUAD** — 13,155 attorney-labelled clauses, stratified sampling, fixed seed, confusion matrix and threshold sweep

**Not built yet**

- Persistence and cross-contract reporting
- The full obligation graph
- Automated tests
- Web interface, Docker, deployment

---

## What it found

Sample supply agreement, 8 clauses, 21 seconds, one resolution round.

### Clause 12.3 — Indemnity. Divergence 1.00, the maximum.

> **Client — severity 1.00:** *"Client must indemnify Supplier even for the Supplier's own negligence, creating unlimited liability for the Client including for harm the Supplier causes."*
>
> **Supplier — severity 0.00:** *"This clause requires the Client to indemnify the Supplier even when claims arise partly from the Supplier's own negligence, which is highly favorable protection for the Supplier."*

Same words. One side says *do not sign*, the other says *no danger at all*. Both descriptions are accurate. A conventional risk scorer labels this "indemnity clause, medium risk" and moves on.

### Clause 14.2 — Disputed Invoices. Divergence 0.70, pointing the other way.

Client 0.00, Supplier 0.70. Here the **Supplier** is the exposed party — the clause lets the Client suspend payment indefinitely on a good-faith dispute with no resolution deadline. REDLINE is not a client advocate; it reads both sides.

### Clause 3.2 — Late Payment. Divergence 0.40.

Both agents independently converted "2% per month, compounding" into an effective annual rate of ~26.8%, then disagreed about whether that is punitive or merely commercial.

---

## Why this needs a graph, not a chain

On the first run — before any graph code existed — both agents said this about clause 9.1, unprompted:

> *"...though clause 7.4 (which I cannot see) may impose conditions that could change this assessment."*

Contracts are written as lists but they don't work as lists. Clause 3.1 says pay within 30 days — clause 14.2 suspends that obligation if the invoice is disputed. Judge 3.1 alone and you get the wrong answer.

So the system has to notice the missing cross-reference, fetch it, and re-judge. That is a **cycle**, which is why the orchestration layer is LangGraph rather than a linear chain.

### The same clause, after the cycle

> *"The Supplier can unilaterally terminate without cause on only 14 days notice, giving the Client virtually no protection against sudden service disruption, **while the liability cap in clause 7.4 means the Client cannot recover damages beyond three months of fees even if termination causes substantial harm.**"*

It didn't just read 7.4 — it reasoned about how the two clauses **compound**. Free termination plus a capped remedy is a materially worse position than either clause suggests alone, and that is invisible to any system reviewing clauses one at a time.

**The divergence score stayed at 0.90.** Resolution didn't change the number, it changed the quality of the reasoning — the Client's alarm was correct all along, and is now grounded in a specific figure instead of a hedge.

### How the cycle terminates

Two independent stops, deliberately:

1. **Logical** — a `resolved` list in the graph state. A clause passes through resolution once and is then skipped.
2. **Structural** — `MAX_ROUNDS` in the router, plus LangGraph's `recursion_limit=25`.

The second exists in case the first has a hole.

---

## Performance

| | Before | After |
|---|---|---|
| 8 clauses, 16-20 API calls | ~50s | **21.3s** |

Concurrency uses `asyncio.gather` behind an `asyncio.Semaphore` capped at 5 concurrent clauses. Unbounded `gather` over a 200-clause contract would fire 400 simultaneous requests, trip rate limits, and trigger every retry at once — a self-inflicted thundering herd.

**Known remaining bottleneck:** the resolution node still calls the synchronous reader, so re-reads run sequentially. Roughly 13 of the 21 seconds. Converting it should land the run near 12s.

---

## How it works

```
contract.txt
     │
     ▼
  parser.py     splits text into clauses, extracts cross-references
     │
     ▼
  graph.py      LangGraph: parse → read → check ⇄ resolve → report
     │              │                        └── cycle ──┘
     ▼              ▼
   llm.py       each clause read twice, opposed prompts, concurrent
     │
     ▼
  core.py       divergence scoring, ranking, reference counting
     │
     ▼
  ranked risk report
```

Each module does one transformation. `parser.py` never calls a model. `llm.py` never does arithmetic. `core.py` never touches the network — so the scoring logic runs and can be tested with no API key at all.

### Design note: prompt symmetry

The two system prompts are word-for-word identical except for the party named. If one were longer or more leading than the other, the divergence score would measure *prompt asymmetry* rather than genuine disagreement between the parties, and the premise would collapse.

---

## Run it

```bash
git clone https://github.com/AaryanSehgal/redline-agent
cd redline-agent

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

cp .env.example .env            # then add your Anthropic API key

python -m redline.graph
```

---

## Evaluation

A demo you chose yourself is an anecdote. So REDLINE is scored against **CUAD** — the Contract Understanding Atticus Dataset, 13,155 clauses across 41 categories, labelled by supervising attorneys.

The harness (`evaluate.py`, `score_eval.py`, `analyse_eval.py`) does the full job:

- **Stratified sampling** — equal clauses per category, so a 2,560-row category can't drown a 36-row one
- **Fixed seed** — same sample every run, so a change in score means a change in the system and not in the questions
- **Length filtering** — CUAD spans include metadata fragments like party names; those are excluded so the test isn't trivially easy
- **Confusion matrix and threshold sweep** — precision, recall and F1 at 19 operating points, against the majority-class baseline

Following the framing in [ContractEval](https://arxiv.org/abs/2508.03080) (2025), the first benchmark for clause-level legal risk identification, which also builds on CUAD.

**Current finding.** The v1 prompts name "Client" and "Supplier". Real contracts use their own defined terms — `Licensor`, `Distributor`, `Rogers` — so on CUAD clauses neither agent has a side to take and divergence compresses toward zero. The next iteration extracts the party names from each clause and instantiates the two symmetric prompts with them, then re-runs against the identical saved eval set. One variable changed, everything else held.

That finding only exists because the harness does. It's the reason to build evaluation before claiming a number.

Worth noting: [ACORD](https://arxiv.org/abs/2501.06582) (ACL 2025), also expert-annotated, reports a **21% disagreement rate between its own legal annotators** — independent evidence that experts read the same clause differently one time in five. That is the premise REDLINE is built on.

---

## Known limitations

Stated plainly, because a tool that hides its failure modes is worse than one that names them.

- **No headline accuracy number yet.** The harness is live; prompt iteration is in progress (above).
- **Output varies between runs.** Clause 3.2 was flagged on one run and not another. Severity scores are model judgements, not measurements, and they move. Any production use needs either a fixed seed, multiple samples, or a confidence band.
- **Plain text only.** No PDF or DOCX. Real contracts arrive as PDFs.
- **One numbering format.** Clauses must be `N.N` at the start of a line. `Section 3.1`, `ARTICLE III`, and `(a)/(b)` sub-clauses are not handled.
- **Headings must be inline** with the body, ending at the first full stop.
- **Cross-reference resolution is depth-1.** If clause 9.1 references 7.4, and 7.4 references 12.3, only 7.4 is pulled in. The `resolved` guard that makes the cycle terminate is also what caps its depth — a deliberate trade of completeness for a termination guarantee. The fix is a transitive closure with a cycle guard, which the sample contract needs anyway: 3.1 and 14.2 reference each other.
- **No tests.**
- **Not legal advice.** This surfaces clauses worth a human's attention. It does not replace one.

---

## Roadmap

1. Party-neutral prompts, re-scored against the saved eval set
2. Obligation graph: who owes what, to whom, by when, conditional on what
3. Cost routing: a fine-tuned classifier handles routine clauses, the model pair handles only contested ones
4. Transitive cross-reference closure with a cycle guard
5. Tests, Streamlit interface, Docker, deployment

---

## Built by

Aaryan Sehgal — BSc Artificial Intelligence, transitioning into AI engineering.
Sydney, Australia.
