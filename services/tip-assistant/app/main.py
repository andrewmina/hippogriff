"""
Hippogriff — Tip Assistant
===========================
AI-powered betting tip generator using Anthropic Claude.
Wired with Datadog LLM Observability (ddtrace.llmobs) to capture:
  - Input/output tokens
  - Prompt templates
  - Model latency
  - LLM spans in the APM trace

Datadog coverage:
  - LLM Observability (full span capture)
  - APM (distributed trace context)
  - Custom metrics: tips.generated, tips.tokens_used, tips.latency_ms
"""

import os
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import anthropic
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datadog import initialize, statsd
from ddtrace import tracer, patch_all
from ddtrace.contrib.asgi import TraceMiddleware
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import llm, task

patch_all()

initialize(
    statsd_host=os.getenv("DD_AGENT_HOST", "datadog-agent.datadog.svc.cluster.local"),
    statsd_port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
)

# Enable LLM Observability
LLMObs.enable(
    ml_app="hippogriff-tip-assistant",
    integrations_enabled=True,
)

# ── Logging ────────────────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record):
        span = tracer.current_span()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "tip-assistant",
            "env": os.getenv("DD_ENV", "dev"),
        }
        if span:
            entry["dd.trace_id"] = str(span.trace_id)
            entry["dd.span_id"] = str(span.span_id)
        return json.dumps(entry)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("tip-assistant")

# ── Anthropic client ───────────────────────────────────────────────────────
anthropic_client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hippogriff Tip Assistant", version="1.0.0")
app.add_middleware(TraceMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SYSTEM_PROMPT = """You are Hippogriff's AI betting tip assistant. You provide concise,
data-driven insights to help users understand sporting events and betting markets.

Guidelines:
- Be factual and balanced — always remind users to bet responsibly
- Keep responses to 2-3 sentences max
- Reference specific odds or stats when available
- Never guarantee outcomes — sports are unpredictable
- End each tip with a responsible gambling reminder
"""

# ── Models ─────────────────────────────────────────────────────────────────
class TipRequest(BaseModel):
    event_id: str
    home_team: str
    away_team: str
    sport: str
    home_odds: float
    away_odds: float
    draw_odds: Optional[float] = None
    user_id: Optional[str] = None
    question: Optional[str] = None

class TipResponse(BaseModel):
    event_id: str
    tip: str
    model: str
    tokens_used: int
    latency_ms: float
    generated_at: str

# ── Core LLM call with LLM Observability ──────────────────────────────────

@llm(model_name="claude-sonnet-4-20250514", model_provider="anthropic", name="generate_tip")
def _call_claude(prompt: str, event_context: dict) -> tuple[str, int]:
    """
    Wrapped with @llm decorator so Datadog captures the full LLM span:
    input messages, output, token counts, model name, latency.
    """
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    tip_text = response.content[0].text
    tokens = response.usage.input_tokens + response.usage.output_tokens
    return tip_text, tokens

# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tip-assistant"}

@app.get("/ready")
def ready():
    return {"status": "ready", "llm": "anthropic"}

@app.post("/tips", response_model=TipResponse)
async def generate_tip(request: TipRequest):
    """
    Generate an AI betting tip for an event.
    Full LLM Observability trace captured by ddtrace.
    """
    tags = [f"sport:{request.sport}", f"event:{request.event_id}"]

    with tracer.trace("tip.generate", resource="generate_tip") as span:
        span.set_tag("sport", request.sport)
        span.set_tag("event_id", request.event_id)
        if request.user_id:
            span.set_tag("user.id", request.user_id)

        # Build prompt
        draw_str = f"Draw: {request.draw_odds}" if request.draw_odds else ""
        question = request.question or f"What should I know about this {request.sport} match?"

        prompt = f"""Event: {request.home_team} vs {request.away_team} ({request.sport})
Current odds — {request.home_team}: {request.home_odds} | {request.away_team}: {request.away_odds} {draw_str}

User question: {question}

Provide a concise betting insight."""

        start = time.perf_counter()
        try:
            tip_text, tokens = _call_claude(prompt, {
                "event_id": request.event_id,
                "sport": request.sport,
                "home_team": request.home_team,
                "away_team": request.away_team,
            })
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            statsd.increment("hippogriff.tips.error", tags=tags + ["error:api"])
            raise HTTPException(status_code=502, detail="AI service temporarily unavailable")

        latency_ms = (time.perf_counter() - start) * 1000

        # Metrics
        statsd.increment("hippogriff.tips.generated", tags=tags)
        statsd.histogram("hippogriff.tips.latency_ms", latency_ms, tags=tags)
        statsd.histogram("hippogriff.tips.tokens_used", tokens, tags=tags)

        logger.info("Tip generated", extra={
            "event_id": request.event_id,
            "tokens": tokens,
            "latency_ms": latency_ms,
            "sport": request.sport,
        })

        return TipResponse(
            event_id=request.event_id,
            tip=tip_text,
            model="claude-sonnet-4-20250514",
            tokens_used=tokens,
            latency_ms=round(latency_ms, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

@app.post("/tips/batch")
async def generate_batch_tips(requests: list[TipRequest]):
    """Generate tips for multiple events — used by load generator."""
    results = []
    for req in requests[:5]:  # Cap at 5 to control API costs
        try:
            tip = await generate_tip(req)
            results.append(tip.model_dump())
        except Exception as e:
            results.append({"event_id": req.event_id, "error": str(e)})
    return {"tips": results, "count": len(results)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
