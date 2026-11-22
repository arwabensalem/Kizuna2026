"""KIZUNA Orchestrator.

One class inside the Django process. It calls the specialist agents
in a fixed order and returns a single decision bundle for a tick.
"""

from engine.anomaly import AnomalyAgent
from engine.autopilot import AutopilotAgent
from engine.crisis_engine import CrisisAgent
from engine.exchange import ExchangeAgent
from engine.prediction import ForecastAgent


class Orchestrator:
    def __init__(self):
        self.forecast = ForecastAgent()
        self.anomaly = AnomalyAgent()
        self.crisis = CrisisAgent()
        self.autopilot = AutopilotAgent()
        self.exchange = ExchangeAgent()

    def decide(self, state: dict) -> dict:
        """Return forecast, anomalies, crisis, actions, and trades.

        Phase 3 fills forecast and crisis. Actions and trades stay empty
        until phase 6. Anomalies stay empty until phase 7.
        """
        raise NotImplementedError('Orchestrator.decide is phase 3.')
