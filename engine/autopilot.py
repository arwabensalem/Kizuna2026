"""Choose conserve mode, irrigation shifts, and actuator commands."""


class AutopilotAgent:
    def run(self, state: dict, forecast: list[dict], crisis: dict) -> list[dict]:
        """Return command dicts with source autopilot or weather.

        Phase 6 implements the rules. Phase 3 can run with an empty action list.
        """
        raise NotImplementedError('AutopilotAgent.run is phase 6.')
