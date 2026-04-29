"""
Hippogriff — Odds Engine
========================
Core service that calculates and updates real-time betting odds for sports
events. Publishes odds changes to Kafka. Heavy compute — good Profiler demo.

Datadog coverage:
  - APM (auto-instrumented via ddtrace)
  - Custom DogStatsD metrics: odds.calculated, odds.drift, market.suspended
  - Continuous Profiler (DD_PROFILING_ENABLED=true)
  - Structured JSON logs with trace correlation
  - Error Tracking (intentional chaos endpoint)
"""

import os
import json
import time
import random
import logging
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datadog import initialize, statsd
from ddtrace import tracer, patch_all
from ddtrace.contrib.asgi import TraceMiddleware

# ── Datadog instrumentation ────────────────────────────────────────────────
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
            "service": "odds-engine",
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
logger = logging.getLogger("odds-engine")

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Hippogriff Odds Engine",
    description="Real-time sports betting odds calculation",
    version="1.0.0",
)
app.add_middleware(TraceMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ─────────────────────────────────────────────────────────────────
class Event(BaseModel):
    event_id: str
    sport: str
    home_team: str
    away_team: str
    start_time: str

class OddsResponse(BaseModel):
    event_id: str
    home_win: float
    draw: Optional[float]
    away_win: float
    over_under: float
    timestamp: str
    market_status: str

class OddsUpdate(BaseModel):
    event_id: str
    trigger: str  # "score_change" | "volume_shift" | "manual"

# ── In-memory event store (replace with Redis in Phase 4) ─────────────────
EVENTS: dict[str, dict] = {}
SPORTS = ["football", "basketball", "baseball", "hockey", "soccer"]
TEAMS = {
    "football": [("Eagles", "Chiefs"), ("Cowboys", "49ers"), ("Bills", "Ravens")],
    "soccer":   [("Arsenal", "Chelsea"), ("Real Madrid", "Barcelona"), ("PSG", "Bayern")],
    "basketball": [("Lakers", "Celtics"), ("Warriors", "Bucks"), ("Heat", "Nuggets")],
    "baseball": [("Yankees", "Red Sox"), ("Dodgers", "Astros")],
    "hockey":   [("Bruins", "Maple Leafs"), ("Penguins", "Capitals")],
}

def _calculate_odds(event_id: str, sport: str) -> OddsResponse:
    """
    Core odds calculation. In a real system this would be a Monte Carlo
    simulation or ML model. Here we use seeded randomness so odds drift
    realistically over time — good for APM flame graph demos.
    """
    with tracer.trace("odds.calculate", service="odds-engine", resource=sport):
        # Simulate compute work — makes profiler traces interesting
        seed = hash(event_id + str(int(time.time() / 60)))
        rng = random.Random(seed)

        base = rng.uniform(1.5, 3.5)
        noise = rng.gauss(0, 0.1)
        home_win = round(max(1.1, base + noise), 2)
        away_win = round(max(1.1, (1 / (1 - 1/home_win - 0.05)) + noise), 2)
        draw = round(rng.uniform(2.8, 4.5), 2) if sport in ("soccer", "football") else None
        over_under = round(rng.uniform(1.7, 2.2), 2)

        market_status = "suspended" if rng.random() < 0.03 else "open"

        # Emit DogStatsD metrics
        tags = [f"sport:{sport}", f"event:{event_id}", f"market:{market_status}"]
        statsd.increment("hippogriff.odds.calculated", tags=tags)
        statsd.gauge("hippogriff.odds.home_win", home_win, tags=tags)
        statsd.gauge("hippogriff.odds.away_win", away_win, tags=tags)
        statsd.histogram("hippogriff.odds.spread", abs(home_win - away_win), tags=tags)

        if market_status == "suspended":
            statsd.increment("hippogriff.market.suspended", tags=tags)
            logger.warning("Market suspended", extra={"event_id": event_id, "sport": sport})

        return OddsResponse(
            event_id=event_id,
            home_win=home_win,
            draw=draw,
            away_win=away_win,
            over_under=over_under,
            timestamp=datetime.now(timezone.utc).isoformat(),
            market_status=market_status,
        )

# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "odds-engine"}

@app.get("/ready")
def ready():
    return {"status": "ready"}

@app.get("/events")
def list_events():
    """List all active betting events."""
    statsd.increment("hippogriff.api.request", tags=["endpoint:list_events"])
    return {"events": list(EVENTS.values()), "count": len(EVENTS)}

@app.post("/events")
def create_event(event: Event):
    """Register a new sporting event for betting."""
    EVENTS[event.event_id] = event.model_dump()
    logger.info("Event created", extra={"event_id": event.event_id, "sport": event.sport})
    statsd.increment("hippogriff.events.created", tags=[f"sport:{event.sport}"])
    return {"status": "created", "event_id": event.event_id}

@app.get("/odds/{event_id}", response_model=OddsResponse)
def get_odds(event_id: str):
    """Get current odds for a specific event."""
    with tracer.trace("odds.get", resource=event_id):
        if event_id not in EVENTS:
            statsd.increment("hippogriff.odds.miss", tags=[f"event:{event_id}"])
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        sport = EVENTS[event_id]["sport"]
        start = time.perf_counter()
        odds = _calculate_odds(event_id, sport)
        duration_ms = (time.perf_counter() - start) * 1000

        statsd.histogram("hippogriff.odds.calculation_ms", duration_ms, tags=[f"sport:{sport}"])
        logger.info("Odds fetched", extra={"event_id": event_id, "duration_ms": duration_ms})
        return odds

@app.post("/odds/recalculate")
def recalculate_odds(update: OddsUpdate, background_tasks: BackgroundTasks):
    """
    Trigger an odds recalculation — called by scoring-service on score changes.
    Runs async to avoid blocking the caller.
    """
    if update.event_id not in EVENTS:
        raise HTTPException(status_code=404, detail="Event not found")

    statsd.increment(
        "hippogriff.odds.recalculation_triggered",
        tags=[f"event:{update.event_id}", f"trigger:{update.trigger}"]
    )
    logger.info("Odds recalculation triggered", extra={
        "event_id": update.event_id,
        "trigger": update.trigger,
    })
    background_tasks.add_task(_calculate_odds, update.event_id, EVENTS[update.event_id]["sport"])
    return {"status": "recalculation_scheduled", "event_id": update.event_id}

@app.get("/odds/bulk/{sport}")
def get_bulk_odds(sport: str):
    """Get odds for all events in a sport — used by the web frontend."""
    events = [e for e in EVENTS.values() if e["sport"] == sport]
    results = []
    for event in events:
        try:
            odds = _calculate_odds(event["event_id"], sport)
            results.append(odds.model_dump())
        except Exception as e:
            logger.error("Bulk odds calculation failed", extra={"event_id": event["event_id"], "error": str(e)})
            statsd.increment("hippogriff.odds.error", tags=[f"sport:{sport}"])

    statsd.histogram("hippogriff.odds.bulk_size", len(results), tags=[f"sport:{sport}"])
    return {"sport": sport, "odds": results, "count": len(results)}

@app.post("/seed")
def seed_events():
    """Populate demo events — call once after deploy to get data flowing."""
    created = []
    for sport, matchups in TEAMS.items():
        for home, away in matchups:
            event_id = f"{sport}_{home.lower()}_{away.lower()}_{int(time.time())}"
            event = Event(
                event_id=event_id,
                sport=sport,
                home_team=home,
                away_team=away,
                start_time=datetime.now(timezone.utc).isoformat(),
            )
            EVENTS[event_id] = event.model_dump()
            created.append(event_id)

    logger.info("Events seeded", extra={"count": len(created)})
    statsd.gauge("hippogriff.events.total", len(EVENTS))
    return {"seeded": len(created), "event_ids": created}

# ── Chaos endpoints (intentional errors for Error Tracking demo) ───────────

@app.get("/chaos/error")
def chaos_error():
    """Intentionally raise an unhandled exception — triggers Error Tracking."""
    raise RuntimeError("Chaos: intentional odds engine failure for demo purposes")

@app.get("/chaos/slow")
def chaos_slow():
    """Simulate a slow query — APM latency demo."""
    time.sleep(random.uniform(2, 5))
    return {"status": "slow_response_completed"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)
