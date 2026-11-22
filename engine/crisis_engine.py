"""Move shortage along twin edges, one hop per tick."""


class CrisisAgent:
    def run(self, state: dict) -> dict:
        """Allocate shared stocks and record unmet demand.

        The volume rules are in ARCHITECTURE.md. This is not a separate crisis service.
        """
        raise NotImplementedError('CrisisAgent.run is phase 3.')
