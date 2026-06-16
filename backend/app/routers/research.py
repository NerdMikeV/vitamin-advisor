"""GET /research/{entity} — latest-research summary via Claude + web_search.

Guardrails: the model summarizes published research with citations. It never
writes interaction assertions into the database, and the prompt forbids
treatment/cure claims and medication directives.
"""
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException

from ..db import connect

# Load ANTHROPIC_API_KEY from the repo-root .env regardless of the server's
# working directory. Does not override an already-exported variable.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

router = APIRouter()

DSHEA_DISCLAIMER = ("These statements have not been evaluated by the Food and Drug "
                    "Administration. This product is not intended to diagnose, treat, "
                    "cure, or prevent any disease.")

SYSTEM_PROMPT = """You summarize recent published research on dietary supplements for a consumer app.

Rules (non-negotiable):
- Use web_search to find recent (last ~2 years) research from reputable sources (NIH, peer-reviewed journals, NCCIH).
- Respond with EXACTLY two sentences summarizing the most relevant recent findings, followed by a "Sources:" line listing 1-3 source names with URLs.
- Start directly with the first sentence. Do NOT write any preamble, lead-in, or meta-commentary (no "Here's the summary", "I found", "Based on my research", etc.).
- Describe evidence neutrally ("a 2025 trial found...", "evidence remains mixed"). Never claim a supplement treats, cures, or prevents any disease.
- Never advise starting, stopping, or changing any medication or supplement.
- If you cannot find solid sources, say so plainly rather than inventing findings."""


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/research/{entity_id}")
def research(entity_id: str, conn=Depends(get_conn)):
    row = conn.execute("SELECT canonical_name FROM entity WHERE entity_id = ?",
                       (entity_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown entity: {entity_id}")
    name = row["canonical_name"]

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=[{"role": "user",
                       "content": f"What does the latest research say about {name} as a dietary supplement?"}],
        )
        # Text blocks before the model's last search are interleaved narration
        # ("I'll search for..."); the composed answer is the text after it.
        blocks = response.content
        last_search = max((i for i, b in enumerate(blocks)
                           if b.type in ("server_tool_use", "web_search_tool_result")),
                          default=-1)
        answer_blocks = [b.text for b in blocks[last_search + 1:]
                         if b.type == "text" and b.text.strip()]
        summary = "\n".join(answer_blocks).strip()
        if not summary:  # no tool use, or all text preceded it — fall back to all text
            summary = "\n".join(b.text for b in blocks if b.type == "text" and b.text.strip()).strip()
        # web_search wraps cited spans in <cite index="...">...</cite> markup — keep the
        # text, drop the tags (the Sources line carries the human-readable citations).
        summary = re.sub(r"</?cite[^>]*>", "", summary).strip()
        if not summary:
            raise HTTPException(status_code=502, detail="Research summary unavailable.")
        return {"entity_id": entity_id, "canonical_name": name,
                "summary": summary, "disclaimer": DSHEA_DISCLAIMER}
    except HTTPException:
        raise
    except Exception as e:
        # Graceful failure (missing API key, network, rate limit): the demo
        # keeps working without the AI panel.
        return {"entity_id": entity_id, "canonical_name": name,
                "summary": None,
                "error": "Live research is temporarily unavailable. Please try again shortly.",
                "detail": type(e).__name__,
                "disclaimer": DSHEA_DISCLAIMER}
