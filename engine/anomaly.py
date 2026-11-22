"""Flag sensor readings that jump away from the recent baseline."""


class AnomalyAgent:
    def run(self, state: dict) -> list[dict]:
        """Return anomaly dicts. Phase 7 adds a z-score check, then IsolationForest if time remains."""
        raise NotImplementedError('AnomalyAgent.run is phase 7.')
