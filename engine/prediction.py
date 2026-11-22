"""Short-horizon demand forecast for one site and one resource."""


class ForecastAgent:
    def run(self, state: dict) -> list[dict]:
        """Forecast the next tick from profiles, then from sklearn if a model file exists.

        Phase 3 uses the household, farm, and business formulas.
        Phase 7 may load a model from media/models/.
        """
        raise NotImplementedError('ForecastAgent.run is phase 3.')
