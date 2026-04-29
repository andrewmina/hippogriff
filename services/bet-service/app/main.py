"""
Hippogriff — Bet Service
========================
Handles bet placement, validation, and persistence. Connects to Postgres
(DBM demo) and calls odds-engine + wallet-service. ASM-eligible endpoint.

Datadog coverage:
  - APM with distributed tracing (calls odds-engine + wallet-service)
  - DBM (Postgres query-level metrics)
  - Custom metrics: bets.placed, bets.rejected, bets.value
  - ASM (Application Security — enabled for this service)
  - Structured JSON logs with trace correlation
  - Error Tracking
"""

import os
import json
import time
import uuid
import logging
import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import asyncpg
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datadog import initialize, statsd
from ddtrace import tracer, patch_all
from ddtrace.contrib.asgi import TraceMiddleware

patch_all()

initialize(
    statsd_host=os.getenv("DD_AGENT_HOST", "datadog-agent.datadog.svc.cluster.local"),
    statsd_port=int(os.getenv("DD_DOGSTATSD_PORT", "8125")),
)

# ── Structured logging ─────────────────────────────────────────────────────
class JSONFormatter(logging.Formatter):
    def format(self, record):
        span = tracer.current_span()
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "bet-service",
            "env": os.getenv("DD_ENV", "dev"),
            "version": os.getenv("DD_VERSION", "1.0.0"),
        }
        if span:
            log_entry["dd.trace_id"] = str(span.trace_id)
            log_entry["dd.span_id"] = str(span.span_id)
        if record.exc_info:
            log_entry["error.stack"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("bet-service")

# ── Config ─────────────────────────────────────────────────────────────────
ODDS_ENGINE_URL    = os.getenv("ODDS_ENGINE_URL", "http://odds-engine.hippogriff.svc.cluster.local:8000")
WALLET_SERVICE_URL = os.getenv("WALLET_SERVICE_URL", "http://wallet-service.hippogriff.svc.cluster.local:8000")
FRAUD_SERVICE_URL  = os.getenv("FRAUD_SERVICE_URL", "http://fraud-detector.hippogriff.svc.cluster.local:8000")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://hippogriff:hippogriff@postgres.hippogriff.svc.cluster.local:5432/hippogriff"
)

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hippogriff Bet Service", version="1.0.0")
app.add_middleware(TraceMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Database pool created")
        await _migrate()
    except Exception as e:
        logger.warning(f"Database not available at startup: {e} — running without DB")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

async def _migrate():
    """Create tables if they don't exist."""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                bet_id      UUID PRIMARY KEY,
                user_id     UUID NOT NULL,
                event_id    TEXT NOT NULL,
                selection   TEXT NOT NULL,
                stake       NUMERIC(12, 2) NOT NULL,
                odds        NUMERIC(8, 3) NOT NULL,
                potential_payout NUMERIC(12, 2) NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                settled_at  TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS bets_user_idx ON bets(user_id);
            CREATE INDEX IF NOT EXISTS bets_event_idx ON bets(event_id);
            CREATE INDEX IF NOT EXISTS bets_status_idx ON bets(status);
        """)
        logger.info("Database migration complete")

# ── Models ─────────────────────────────────────────────────────────────────
class PlaceBetRequest(BaseModel):
    user_id: str
    event_id: str
    selection: str        # "home_win" | "draw" | "away_win" | "over" | "under"
    stake: float

    @field_validator("stake")
    @classmethod
    def stake_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Stake must be positive")
        if v > 100000:
            raise ValueError("Stake exceeds maximum")
        return round(v, 2)

    @field_validator("selection")
    @classmethod
    def valid_selection(cls, v):
        valid = {"home_win", "draw", "away_win", "over", "under"}
        if v not in valid:
            raise ValueError(f"Selection must be one of {valid}")
        return v

class BetResponse(BaseModel):
    bet_id: str
    user_id: str
    event_id: str
    selection: str
    stake: float
    odds: float
    potential_payout: float
    status: str
    created_at: str

# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_odds(event_id: str, selection: str) -> float:
    """Fetch current odds from odds-engine with trace propagation."""
    with tracer.trace("bet.get_odds", resource=event_id):
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {}
            tracer.inject(tracer.current_span().context, Format.HTTP_HEADERS, headers)
            r = await client.get(f"{ODDS_ENGINE_URL}/odds/{event_id}", headers=headers)
            r.raise_for_status()
            data = r.json()

        mapping = {
            "home_win": data["home_win"],
            "away_win": data["away_win"],
            "over":  data["over_under"],
            "under": data["over_under"],
            "draw":  data.get("draw", 0),
        }
        return mapping.get(selection, 2.0)

async def _check_fraud(user_id: str, stake: float, event_id: str) -> bool:
    """Call fraud-detector. Returns True if bet is clean."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.post(f"{FRAUD_SERVICE_URL}/check", json={
                "user_id": user_id,
                "amount": stake,
                "event_id": event_id,
                "action": "bet_placement",
            })
            return r.json().get("approved", True)
    except Exception as e:
        logger.warning(f"Fraud check failed, allowing bet: {e}")
        return True

# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "bet-service"}

@app.get("/ready")
async def ready():
    return {"status": "ready", "db": "connected" if db_pool else "unavailable"}

@app.post("/bets", response_model=BetResponse)
async def place_bet(request: PlaceBetRequest):
    """
    Place a bet. Full distributed trace: bet-service → odds-engine → fraud-detector.
    Writes to Postgres (DBM will show query-level insights).
    """
    bet_id = str(uuid.uuid4())
    tags = [f"event:{request.event_id}", f"selection:{request.selection}"]

    with tracer.trace("bet.place", resource="place_bet") as span:
        span.set_tag("user.id", request.user_id)
        span.set_tag("bet.event_id", request.event_id)
        span.set_tag("bet.selection", request.selection)
        span.set_tag("bet.stake", request.stake)

        # Fraud check
        approved = await _check_fraud(request.user_id, request.stake, request.event_id)
        if not approved:
            statsd.increment("hippogriff.bets.rejected", tags=tags + ["reason:fraud"])
            logger.warning("Bet rejected by fraud detector", extra={
                "user_id": request.user_id,
                "event_id": request.event_id,
                "stake": request.stake,
            })
            raise HTTPException(status_code=403, detail="Bet rejected: suspicious activity detected")

        # Get current odds
        try:
            odds = await _get_odds(request.event_id, request.selection)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Event {request.event_id} not found")
            raise HTTPException(status_code=502, detail="Odds service unavailable")
        except Exception as e:
            logger.error(f"Failed to fetch odds: {e}")
            # Use fallback odds for demo resilience
            odds = 2.0

        potential_payout = round(request.stake * odds, 2)
        now = datetime.now(timezone.utc)

        # Persist to Postgres
        if db_pool:
            with tracer.trace("bet.db.insert", resource="INSERT bets"):
                async with db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO bets
                          (bet_id, user_id, event_id, selection, stake, odds, potential_payout, status, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8)
                    """, bet_id, request.user_id, request.event_id,
                        request.selection, request.stake, odds, potential_payout, now)

        # Metrics
        statsd.increment("hippogriff.bets.placed", tags=tags)
        statsd.histogram("hippogriff.bets.stake", request.stake, tags=tags)
        statsd.histogram("hippogriff.bets.potential_payout", potential_payout, tags=tags)

        logger.info("Bet placed", extra={
            "bet_id": bet_id,
            "user_id": request.user_id,
            "event_id": request.event_id,
            "stake": request.stake,
            "odds": odds,
            "potential_payout": potential_payout,
        })

        return BetResponse(
            bet_id=bet_id,
            user_id=request.user_id,
            event_id=request.event_id,
            selection=request.selection,
            stake=request.stake,
            odds=odds,
            potential_payout=potential_payout,
            status="pending",
            created_at=now.isoformat(),
        )

@app.get("/bets/{bet_id}")
async def get_bet(bet_id: str):
    """Fetch a single bet by ID."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database unavailable")

    with tracer.trace("bet.db.select", resource="SELECT bets"):
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM bets WHERE bet_id = $1", bet_id)

    if not row:
        raise HTTPException(status_code=404, detail="Bet not found")
    return dict(row)

@app.get("/bets/user/{user_id}")
async def get_user_bets(user_id: str, limit: int = 20):
    """Fetch recent bets for a user — used by web-app."""
    if not db_pool:
        return {"bets": [], "note": "Database unavailable"}

    with tracer.trace("bet.db.select_user", resource="SELECT bets by user"):
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM bets WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit
            )
    statsd.histogram("hippogriff.bets.user_history_size", len(rows), tags=[f"user:{user_id}"])
    return {"bets": [dict(r) for r in rows], "count": len(rows)}

@app.get("/stats")
async def get_stats():
    """Aggregate bet stats — feeds executive dashboard."""
    if not db_pool:
        return {"note": "Database unavailable"}

    with tracer.trace("bet.db.stats", resource="SELECT bets stats"):
        async with db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM bets")
            volume = await conn.fetchval("SELECT COALESCE(SUM(stake), 0) FROM bets")
            pending = await conn.fetchval("SELECT COUNT(*) FROM bets WHERE status = 'pending'")

    statsd.gauge("hippogriff.bets.total", total or 0)
    statsd.gauge("hippogriff.bets.volume", float(volume or 0))
    return {"total_bets": total, "total_volume": float(volume or 0), "pending_bets": pending}

@app.get("/chaos/error")
def chaos_error():
    raise ValueError("Chaos: intentional bet-service exception for Error Tracking demo")

if __name__ == "__main__":
    # Note: ddtrace-run wraps this at container startup via Dockerfile CMD
    from ddtrace.propagation.http import HTTPPropagator as Format
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
