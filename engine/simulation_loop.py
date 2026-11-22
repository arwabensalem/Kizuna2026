"""Discrete tick loop for a what-if run.

Each tick is one hour. A run keeps its own steps and leaves live site
state unchanged unless apply_to_live is set. The algorithm is specified
in ARCHITECTURE.md.
"""


def tick(run_id: int, steps: int = 1) -> dict:
    """Advance a run and return the latest digital-twin state."""
    raise NotImplementedError('simulation_loop.tick is phase 3.')
