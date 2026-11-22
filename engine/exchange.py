"""Match a surplus listing to the neighbour with the highest stress."""


class ExchangeAgent:
    def run(self, state: dict) -> list[dict]:
        """Propose trades inside one neighbourhood. Credits are integers, not payments."""
        raise NotImplementedError('ExchangeAgent.run is phase 6.')
