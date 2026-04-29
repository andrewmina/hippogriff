"""
Hippogriff — Load Generator
============================
Simulates realistic betting platform traffic:
  - Diurnal patterns (busy evenings, quiet nights)
  - Pre-game surge (30min before events)
  - Score-change odds recalculation bursts
  - Fraud attempt injection (5% of bets)
  - Tip assistant queries
  - Occasional chaos (high-stake bets, rapid fire)

Run: locust -f locustfile.py --host http://localhost:8001
     locust -f locustfile.py --headless -u 50 -r 5 --run-time 24h --host http://...
"""

import random
import uuid
import json
import math
import time
from datetime import datetime
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# ── Shared state ───────────────────────────────────────────────────────────
ACTIVE_EVENT_IDS: list[str] = []
USER_IDS = [str(uuid.uuid4()) for _ in range(200)]
SPORTS = ["football", "soccer", "basketball", "baseball", "hockey"]
SELECTIONS = ["home_win", "away_win", "draw", "over", "under"]

TEAMS = {
    "football":   [("Eagles", "Chiefs"), ("Cowboys", "49ers"), ("Bills", "Ravens")],
    "soccer":     [("Arsenal", "Chelsea"), ("Real Madrid", "Barcelona")],
    "basketball": [("Lakers", "Celtics"), ("Warriors", "Bucks")],
    "baseball":   [("Yankees", "Red Sox"), ("Dodgers", "Astros")],
    "hockey":     [("Bruins", "Maple Leafs"), ("Penguins", "Capitals")],
}


def _diurnal_weight() -> float:
    """Returns a multiplier 0.2–1.0 based on time of day (Eastern-ish)."""
    hour = datetime.utcnow().hour
    # Peak: 18:00–23:00 UTC (evening US), trough: 03:00–10:00 UTC
    if 18 <= hour <= 23:
        return 1.0
    elif 0 <= hour <= 2:
        return 0.6
    elif 3 <= hour <= 10:
        return 0.2
    else:
        return 0.5


# ── Users ──────────────────────────────────────────────────────────────────

class BettorUser(HttpUser):
    """
    Regular bettor. Places bets, checks odds, reads history.
    Most common user type — 70% of simulated load.
    """
    wait_time = between(1, 5)
    weight = 70

    def on_start(self):
        self.user_id = random.choice(USER_IDS)
        # Seed events on first user start
        if not ACTIVE_EVENT_IDS:
            self._seed_events()

    def _seed_events(self):
        with self.client.post("/seed", catch_response=True, name="seed_events") as r:
            if r.status_code == 200:
                data = r.json()
                ACTIVE_EVENT_IDS.extend(data.get("event_ids", []))

    @task(40)
    def view_odds(self):
        """Browse odds — most common action."""
        if not ACTIVE_EVENT_IDS:
            return
        event_id = random.choice(ACTIVE_EVENT_IDS)
        with self.client.get(f"/odds/{event_id}", name="get_odds", catch_response=True) as r:
            if r.status_code == 404:
                r.success()  # Event expired, not a real failure

    @task(20)
    def place_bet(self):
        """Place a standard bet."""
        if not ACTIVE_EVENT_IDS:
            return
        event_id = random.choice(ACTIVE_EVENT_IDS)
        stake = round(random.choice([5, 10, 20, 25, 50, 100]) * _diurnal_weight(), 2)
        selection = random.choice(SELECTIONS)

        payload = {
            "user_id": self.user_id,
            "event_id": event_id,
            "selection": selection,
            "stake": max(1.0, stake),
        }
        self.client.post(
            "http://bet-service:8000/bets",
            json=payload,
            name="place_bet",
            headers={"X-User-ID": self.user_id},
        )

    @task(15)
    def list_events(self):
        self.client.get("/events", name="list_events")

    @task(10)
    def browse_bulk_odds(self):
        sport = random.choice(SPORTS)
        self.client.get(f"/odds/bulk/{sport}", name="bulk_odds")

    @task(10)
    def view_my_bets(self):
        self.client.get(
            f"http://bet-service:8000/bets/user/{self.user_id}",
            name="user_bet_history",
        )

    @task(5)
    def get_ai_tip(self):
        """Ask the tip assistant for advice."""
        if not ACTIVE_EVENT_IDS:
            return
        sport = random.choice(SPORTS)
        teams = random.choice(TEAMS[sport])
        payload = {
            "event_id": random.choice(ACTIVE_EVENT_IDS),
            "home_team": teams[0],
            "away_team": teams[1],
            "sport": sport,
            "home_odds": round(random.uniform(1.5, 3.5), 2),
            "away_odds": round(random.uniform(1.5, 3.5), 2),
            "user_id": self.user_id,
            "question": random.choice([
                "Who do you think will win?",
                "Is this good value?",
                "What are the key matchup factors?",
                "Should I bet the over or under?",
            ]),
        }
        self.client.post(
            "http://tip-assistant:8000/tips",
            json=payload,
            name="get_ai_tip",
        )


class HighRollerUser(HttpUser):
    """
    High-stakes bettor. Places large bets frequently.
    Good for showing high-value transaction monitoring.
    """
    wait_time = between(3, 8)
    weight = 10

    def on_start(self):
        self.user_id = str(uuid.uuid4())  # Unique high-roller IDs

    @task(60)
    def place_large_bet(self):
        if not ACTIVE_EVENT_IDS:
            return
        stake = round(random.uniform(500, 5000), 2)
        payload = {
            "user_id": self.user_id,
            "event_id": random.choice(ACTIVE_EVENT_IDS),
            "selection": random.choice(SELECTIONS),
            "stake": stake,
        }
        self.client.post(
            "http://bet-service:8000/bets",
            json=payload,
            name="place_large_bet",
        )

    @task(40)
    def view_odds(self):
        if not ACTIVE_EVENT_IDS:
            return
        self.client.get(f"/odds/{random.choice(ACTIVE_EVENT_IDS)}", name="get_odds_roller")


class FraudUser(HttpUser):
    """
    Simulates fraud patterns — rapid-fire bets from same user,
    unusual selections, suspiciously round stakes.
    Triggers fraud-detector alerts and ASM rules.
    """
    wait_time = between(0.1, 0.5)  # Very fast
    weight = 5

    def on_start(self):
        # Fraud users reuse a small pool of IDs (pattern detection)
        self.user_id = f"fraud-user-{random.randint(1, 3)}"

    @task(80)
    def rapid_bet(self):
        if not ACTIVE_EVENT_IDS:
            return
        payload = {
            "user_id": self.user_id,
            "event_id": random.choice(ACTIVE_EVENT_IDS),
            "selection": "home_win",  # Always same selection — suspicious
            "stake": 100.0,           # Always round number — suspicious
        }
        self.client.post(
            "http://bet-service:8000/bets",
            json=payload,
            name="fraud_bet",
        )

    @task(20)
    def probe_endpoints(self):
        """Simulate basic recon — ASM will flag this."""
        probes = [
            "/admin",
            "/../etc/passwd",
            "/api/v1/users",
            "/debug",
            "/?q=<script>alert(1)</script>",
        ]
        self.client.get(random.choice(probes), name="asm_probe")


class OddsWatcherUser(HttpUser):
    """
    Automated odds monitoring bot — polls every event constantly.
    Represents arbing bots. Good for showing high-frequency read traffic.
    """
    wait_time = between(0.5, 2)
    weight = 15

    @task(90)
    def poll_all_odds(self):
        for sport in SPORTS:
            self.client.get(f"/odds/bulk/{sport}", name=f"poll_odds_{sport}")

    @task(10)
    def trigger_recalculate(self):
        """Simulate a score change triggering odds recalculation."""
        if not ACTIVE_EVENT_IDS:
            return
        self.client.post("/odds/recalculate", json={
            "event_id": random.choice(ACTIVE_EVENT_IDS),
            "trigger": "score_change",
        }, name="recalculate_odds")


# ── Event hooks ────────────────────────────────────────────────────────────

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("🦅 Hippogriff load generator starting...")
    print(f"   Diurnal weight: {_diurnal_weight():.2f}")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("🦅 Hippogriff load generator stopped.")
