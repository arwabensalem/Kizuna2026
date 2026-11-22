"""Read fields from one system-state dict.

A missing key stays missing. Nothing here fills in a number.
"""


def walk(state, path):
    current = state
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def number(state, path):
    current = walk(state, path)
    if isinstance(current, dict):
        current = current.get('value')
    if isinstance(current, bool) or current is None:
        return None
    try:
        value = float(current)
    except (TypeError, ValueError):
        return None
    if value != value:
        return None
    return value


def text(state, path):
    current = walk(state, path)
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def flag(state, key):
    if not isinstance(state, dict) or key not in state:
        return None
    return bool(state[key])


def show(value, suffix=''):
    if value is None:
        return 'not in this state'
    rendered = f'{value:.2f}'.rstrip('0').rstrip('.')
    return f'{rendered}{suffix}'
