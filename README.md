# REDLINE

**Two AI agents read the same contract clause with opposite interests. Where they disagree, that's your risk.**

Most contract tools score clauses for danger. REDLINE scores them for *disagreement*.

The idea came from reading commercial terms in a sales job and noticing that the clauses causing arguments were rarely the scary-looking ones. They were the clauses where both sides had read the same words and walked away with a different understanding of the deal. That's what this looks for.

---

## Status

Working, in active development.

**Working now**

- Parses plain-text contracts into structured clauses with cross-references
- Reads each clause twice, once as the Client and once as the Supplier, using identical prompts
- Scores divergence between the two readings and ranks clauses
- LangGraph orchestration with a working cycle: when a flagged clause depends on a clause the model hasn't seen, the graph fetches it and re-judges
- Concurrent API calls with a semaphore cap. 50s down to 21.3s
- Test suite for the scoring logic, runs with no API key
- Evaluation harness scoring the system against CUAD's attorney-labelled clauses

**Not yet**

- Obligation graph
- Persistence and cross-contract reporting
- Web interface, Docker, deployment

---

## What it found

Sample supply agreement. 8 clauses, 21 seconds, one resolution round.

### Clause 12.3, Indemnity. Divergence 1.00, the maximum.

> **Client, severity 1.00:** *"Client must indemnify Supplier even for the Supplier's own negligence, creating unlimited liability for the Client including for harm the Supplier causes."*
>
> **Supplier, severity 0.00:** *"This clause requires the Client to indemnify the Supplier even when claims arise partly from the Supplier's own negligence, which is highly favorable protection for the Supplier."*

Same words. One side says don't sign it, the other says it's fine. Both descriptions are accurate. A risk scorer would call this "indemnity clause, medium risk" and move on.

### Clause 14.2, Disputed Invoices. Divergence 0.70, and it points the other way.

Client 0.00, Supplier 0.70. Here the Supplier is the exposed party, because the clause lets the Client suspend payment indefinitely on a good-faith dispute with no deadline. The system reads both sides, not just the buyer's.

### Clause 3.2, Late Payment. Divergence 0.40.

Both agents worked out that 2% per month compounding is about 26.8% a year, then disagreed about whether that's punitive or just commercial.

---

## Why it needs a graph and not a chain

On the very first run, before I'd written any graph code, both agents said this about clause 9.1 without being asked:

> *"...though clause 7.4 (which I cannot see) may impose conditions that could change this assessment."*

Contracts are written as lists but they don't work like lists. Clause 3.1 says pay within 30 days. Clause 14.2 suspends that if the invoice is disputed. Judge 3.1 on its own and you get the wrong answer.

So the system has to spot the missing reference, go and get it, and judge again. That's a cycle, which is why the orchestration is LangGraph rather than a linear chain.

**The same clause after the cycle ran:**

> *"The Supplier can unilaterally terminate without cause on only 14 days notice, giving the Client virtually no protection against sudden service disruption, **while the liability cap in clause 7.4 means the Client cannot recover damages beyond three months of fees even if termination causes substantial harm.**"*

It didn't just read 7.4. It worked out how the two clauses stack. Free termination plus a capped remedy is worse than either clause looks alone, and nothing reviewing clauses one at a time would catch it.

The divergence score stayed at 0.90. The number didn't move, the reasoning got grounded.

**How the loop stops.** Two ways, on purpose. A `resolved` list means each clause goes through resolution once. `MAX_ROUNDS` and LangGraph's `recursion_limit=25` are the backstop in case the first one has a hole.

---

## Performance

| | Before | After |
|---|---|---|
| 8 clauses, ~20 API calls | 50s | **21.3s** |

`asyncio.gather` behind an `asyncio.Semaphore(5)`. The cap matters: unbounded gather on a 200-clause contract fires 400 requests at once, trips rate limits, then fires every retry simultaneously. That's a thundering herd you've built yourself.

Still sequential inside the resolution node, which is roughly 13 of those 21 seconds. Next thing to fix.

---

## How it works

```
contract.txt
     |
  parser.py     splits text into clauses, pulls out cross-references
     |
  graph.py      LangGraph: parse -> read -> check <-> resolve -> report
     |                                       \___ cycle ___/
   llm.py       each clause read twice, opposed prompts, concurrent
     |
  core.py       divergence scoring, ranking, reference counting
     |
  ranked risk report
```

One job per module. `parser.py` never calls a model, `llm.py` never does maths, `core.py` never touches the network. That last one is why the tests run without an API key.

**On prompt symmetry:** the two system prompts are word for word identical except for the party named. If one were longer or more leading, the divergence score would be measuring the prompts rather than the parties, and the whole idea falls over.

---

## Evaluation

A demo you picked yourself is an anecdote, so I built a harness to score the system against **CUAD**, the Contract Understanding Atticus Dataset: 13,155 clauses across 41 categories, labelled by supervising attorneys.

`evaluate.py`, `score_eval.py` and `analyse_eval.py` do the work:

- Stratified sampling, equal clauses per category, so a 2,560-row category can't drown a 36-row one
- Fixed seed, so the sample regenerates identically and a change in score means the system changed and not the questions
- Length filtering, because CUAD spans include metadata fragments like party names and those would make the test trivially easy
- Confusion matrix and threshold sweep, precision/recall/F1 at 19 operating points against the majority-class baseline

Framing follows [ContractEval](https://arxiv.org/abs/2508.03080) (2025), the first benchmark for clause-level legal risk identification, which also builds on CUAD.

**Where it's at.** The v1 prompts name "Client" and "Supplier". Real contracts use their own defined terms, `Licensor`, `Distributor`, `Rogers`, so on CUAD clauses neither agent has a side to take and the divergence scores compress. Next version extracts the party names from each clause and fills the two symmetric prompts with them, then re-runs against the same seeded eval set. One variable changed, everything else held.

I only know that because the harness exists. That's the argument for building evaluation before quoting a number.

Worth noting: [ACORD](https://arxiv.org/abs/2501.06582) (ACL 2025), also expert-annotated, reports a **21% disagreement rate between its own legal annotators**. Independent evidence that experts read the same clause differently about one time in five, which is the premise this whole thing rests on.

---

## Run it

```bash
git clone https://github.com/AaryanSehgal/redline-agent
cd redline-agent

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
cp .env.example .env            # add your Anthropic API key

python -m redline.graph         # review the sample contract
python -m pytest -v             # tests, no API key needed
```

---

## Limitations

- **Plain text only.** No PDF or DOCX. Real contracts turn up as PDFs.
- **One numbering format.** Clauses have to be `N.N` at the start of a line. `Section 3.1`, `ARTICLE III` and `(a)/(b)` sub-clauses aren't handled.
- **Headings must be inline** with the clause body, ending at the first full stop.
- **Cross-reference resolution is depth-1.** If 9.1 points at 7.4 and 7.4 points at 12.3, only 7.4 gets pulled in. The `resolved` guard that makes the cycle terminate is also what caps its depth. Fix is a transitive closure with a cycle guard, which the sample contract needs anyway since 3.1 and 14.2 reference each other.
- **Output moves between runs.** Clause 3.2 was flagged on one run and not another. Severity scores are model judgements, not measurements. Production use would need a fixed seed, repeated sampling, or confidence bands.
- **No headline accuracy figure yet.** Harness is live, prompt iteration in progress, see above.
- **Not legal advice.** It surfaces clauses worth a human's attention. It doesn't replace one.

---

## Next

1. Party-neutral prompts, re-scored against the saved eval set
2. Obligation graph: who owes what, to whom, by when, conditional on what
3. Cost routing, so a fine-tuned classifier handles routine clauses and the model pair only sees contested ones
4. Transitive cross-reference closure
5. Streamlit interface, Docker, deployment

---

Built by Aaryan Sehgal. BSc Artificial Intelligence, moving into AI engineering. Sydney.
