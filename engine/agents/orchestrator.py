"""KIZUNA Orchestrator.

Asks the water, energy, agriculture, and climate modules about one state,
then keeps the actions that do not contradict a higher-priority rule.
Water limits and climate rain outrank a request to irrigate. An energy
shortfall outranks irrigation when the pump cannot be powered.

The result is a recommendation. It does not write the clock, move an
actuator, or call a language model.
"""

from engine.agents import agriculture_agent, climate_agent, energy_agent, water_agent

LABEL = (
    'Deterministic rules on one system state. '
    'No language model is called. Nothing here changes the clock or an actuator.'
)
ORDER = (
    ('water', water_agent.assess),
    ('climate', climate_agent.assess),
    ('energy', energy_agent.assess),
    ('agriculture', agriculture_agent.assess),
)
RANK = {'unknown': -1, 'normal': 0, 'watch': 1, 'alert': 2}


def coordinate(state):
    if not isinstance(state, dict):
        state = {}
    reports = [module(state) for _name, module in ORDER]
    kept = []
    blocked = {}
    trace = []
    for report in reports:
        trace.append(f"{report['agent']}: {report['status']}.")
        for action in report['actions']:
            blocker = blocked.get(action['id'])
            if blocker is not None:
                trace.append(
                    f"Not taken: {action['action']}. {blocker}"
                )
                continue
            existing = next((item for item in kept if item['id'] == action['id']), None)
            if existing is None:
                kept.append({
                    'id': action['id'],
                    'action': action['action'],
                    'sources': [report['agent']],
                    'reason': action['reason'],
                })
                trace.append(f"Taken: {action['action']}. {action['reason']}")
            elif report['agent'] not in existing['sources']:
                existing['sources'].append(report['agent'])
                existing['reason'] = f"{existing['reason']} {action['reason']}"
                trace.append(f"Same action from {report['agent']}: {action['reason']}")
            for blocked_id in action.get('blocks', []):
                blocked.setdefault(blocked_id, action['reason'])
    if not any(report['status'] != 'unknown' for report in reports):
        trace.append('The state did not include enough readings, so no action was chosen.')
    statuses = [report['status'] for report in reports]
    status = max(statuses, key=lambda item: RANK.get(item, -1))
    return {
        'label': LABEL,
        'status': status,
        'modules': reports,
        'actions': kept,
        'trace': trace,
    }


class KizunaOrchestrator:
    """Fixed order: water, climate, energy, then agriculture."""

    def coordinate(self, state):
        return coordinate(state)
