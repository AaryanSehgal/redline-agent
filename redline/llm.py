"""LLM calls for REDLINE.

One clause in, one reading out. No scoring here -- that's core.py.
"""

import json
import os
import time
import asyncio

from anthropic import AsyncAnthropic
from anthropic import Anthropic
from dotenv import load_dotenv

from redline.prompts import OUR_SIDE, THEIR_SIDE

load_dotenv()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
async_client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

MODEL = "claude-sonnet-4-5"
MAX_RETRIES = 3

async def _call_model_async(clause_text, system_prompt):
    """Async twin of _call_model. Same retry logic, non-blocking waits."""
    for attempt in range(MAX_RETRIES):
        try:
            return await async_client.messages.create(
                model=MODEL,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": clause_text}],
            )
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"call failed ({e}), retrying in {2 ** attempt}s")
            await asyncio.sleep(2 ** attempt)


async def read_clause_async(clause_text, system_prompt):
    """One clause, one side. Awaitable."""
    response = await _call_model_async(clause_text, system_prompt)

    if response.stop_reason == "max_tokens":
        raise ValueError("response was cut off -- raise max_tokens")

    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)


async def read_both_sides_async(clause):
    """Both sides of one clause, concurrently."""
    ours, theirs = await asyncio.gather(
        read_clause_async(clause["text"], OUR_SIDE),
        read_clause_async(clause["text"], THEIR_SIDE),
    )
    return {
        "clause_id": clause["id"],
        "our_severity": ours["severity"],
        "their_severity": theirs["severity"],
        "our_reason": ours["reason"],
        "their_reason": theirs["reason"],
        "our_quote": ours["quote"],
        "their_quote": theirs["quote"],
    }


async def read_all_async(clauses, max_concurrent=5):
    """Every clause, both sides, at most `max_concurrent` clauses at a time."""
    sem = asyncio.Semaphore(max_concurrent)

    async def guarded(clause):
        async with sem:                              # take a ticket (wait if none)
            return await read_both_sides_async(clause)
        # ticket returned automatically on exit

    return await asyncio.gather(*(guarded(c) for c in clauses))

def _call_model(clause_text, system_prompt):
    """Call the API, retrying with exponential backoff on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            return client.messages.create(
                model=MODEL,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": clause_text}],
            )
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt          # 1s, then 2s, then 4s
            print(f"call failed ({e}), retrying in {wait}s")
            time.sleep(wait)


def read_clause(clause_text, system_prompt):
    """Send one clause under one side's prompt. Return a reading dict."""
    response = _call_model(clause_text, system_prompt)

    if response.stop_reason == "max_tokens":
        raise ValueError("response was cut off -- raise max_tokens")

    raw = response.content[0].text.strip()
    raw = raw.removeprefix("```json").removesuffix("```").strip()
    return json.loads(raw)


def read_both_sides(clause):
    """Read one clause from both sides. Returns the Stage 3 reading dict."""
    ours = read_clause(clause["text"], OUR_SIDE)
    theirs = read_clause(clause["text"], THEIR_SIDE)

    return {
        "clause_id": clause["id"],
        "our_severity": ours["severity"],
        "their_severity": theirs["severity"],
        "our_reason": ours["reason"],
        "their_reason": theirs["reason"],
        "our_quote": ours["quote"],
        "their_quote": theirs["quote"],
    }


if __name__ == "__main__":
    clause = {
        "id": "cl3",
        "text": "The Supplier may terminate this agreement on 14 days notice without cause.",
    }
    reading = read_both_sides(clause)
    print(json.dumps(reading, indent=2))