"""Load the saved demo models and score one row.

Django views call these functions directly. Metrics attached to a result
are the validation numbers written when the model was trained.
"""

import json

import joblib
import pandas as pd

from apps.ai_engine.datasets import CROP_TYPES, SOIL_TYPES
from apps.ai_engine.training import LABEL, models_dir

_CACHE = {}


class PredictionError(Exception):
    def __init__(self, message, missing=False):
        super().__init__(message)
        self.missing = missing


def load_report(directory=None):
    path = models_dir(directory) / 'metrics.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def predict_water(payload):
    values = {
        'residents': _integer(payload, 'residents', 1, 20),
        'temperature': _number(payload, 'temperature', -5, 55),
        'day_of_week': _integer(payload, 'day_of_week', 0, 6),
        'historical_consumption': _number(payload, 'historical_consumption', 0, 500),
        'appliance_usage': _number(payload, 'appliance_usage', 0, 200),
    }
    return _score('water', values, floor=0)


def predict_energy(payload):
    values = {
        'temperature': _number(payload, 'temperature', -5, 55),
        'appliance_load': _number(payload, 'appliance_load', 0, 20000),
        'solar_production': _number(payload, 'solar_production', 0, 20000),
        'hour': _integer(payload, 'hour', 0, 23),
        'historical_energy': _number(payload, 'historical_energy', 0, 20000),
    }
    return _score('energy', values, floor=0)


def predict_farm_water(payload):
    return _score('farm_water', _farm_values(payload), floor=0)


def predict_crop_stress(payload):
    return _score('crop_stress', _farm_values(payload), floor=0, ceiling=100)


def predict_crop_stress_rows(rows):
    """Score several already-validated farm rows in one call."""
    from apps.ai_engine.datasets import design_matrix

    bundle = _load('crop_stress')
    frame = pd.DataFrame({
        column: [row[column] for row in rows]
        for column in bundle['spec']['numeric'] + list(bundle['spec']['categories'])
    })
    matrix = design_matrix(frame, bundle['spec']).loc[:, bundle['columns']]
    return [min(100.0, max(0.0, float(value))) for value in bundle['estimator'].predict(matrix)]


def detect_anomaly(payload):
    values = {
        'temperature': _number(payload, 'temperature', -10, 80),
        'humidity': _number(payload, 'humidity', 0, 100),
        'water_consumption': _number(payload, 'water_consumption', 0, 5000),
        'electricity_consumption': _number(payload, 'electricity_consumption', 0, 50000),
        'soil_moisture': _number(payload, 'soil_moisture', 0, 100),
        'rainfall': _number(payload, 'rainfall', 0, 300),
        'tank_level': _number(payload, 'tank_level', 0, 100),
        'solar_production': _number(payload, 'solar_production', 0, 30000),
    }
    bundle = _load('anomaly')
    frame = _matrix(bundle, values)
    estimator = bundle['estimator']
    score = float(estimator.decision_function(frame)[0])
    flagged = int(estimator.predict(frame)[0]) == -1
    result = _envelope('anomaly', bundle, values)
    result['anomaly'] = flagged
    result['score'] = round(score, 6)
    result['score_note'] = (
        'IsolationForest decision_function. A negative score is the outlier '
        'side of this model.'
    )
    return result


def _farm_values(payload):
    crop = _choice(payload, 'crop_type', CROP_TYPES)
    soil = _choice(payload, 'soil_type', SOIL_TYPES)
    return {
        'soil_moisture': _number(payload, 'soil_moisture', 0, 100),
        'temperature': _number(payload, 'temperature', -5, 55),
        'humidity': _number(payload, 'humidity', 0, 100),
        'rainfall': _number(payload, 'rainfall', 0, 200),
        'crop_type': crop,
        'soil_type': soil,
        'area': _number(payload, 'area', 1, 1_000_000),
    }


def _score(task, values, floor=None, ceiling=None):
    bundle = _load(task)
    frame = _matrix(bundle, values)
    prediction = float(bundle['estimator'].predict(frame)[0])
    if floor is not None:
        prediction = max(floor, prediction)
    if ceiling is not None:
        prediction = min(ceiling, prediction)
    result = _envelope(task, bundle, values)
    result['prediction'] = round(prediction, 2)
    result['unit'] = bundle['unit']
    return result


def _envelope(task, bundle, values):
    report = load_report() or {}
    tasks = report.get('tasks') or {}
    trained = tasks.get(task) or {}
    return {
        'task': task,
        'model': bundle['model_name'],
        'training_data': 'synthetic_demo',
        'label': LABEL,
        'seed': report.get('seed'),
        'inputs': values,
        'validation': trained.get('validation'),
        'n_validation': trained.get('n_validation'),
        'validation_note': trained.get('note', (
            'Validation metrics were calculated on the held-out synthetic split.'
        )),
    }


def _matrix(bundle, values):
    from apps.ai_engine.datasets import design_matrix

    row = {}
    for column in bundle['spec']['numeric']:
        row[column] = [values[column]]
    for name in bundle['spec']['categories']:
        row[name] = [values[name]]
    frame = design_matrix(pd.DataFrame(row), bundle['spec'])
    return frame.loc[:, bundle['columns']]


def _load(task):
    path = models_dir() / f'{task}.joblib'
    key = str(path.resolve()) if path.exists() else str(path)
    if key not in _CACHE:
        if not path.exists():
            raise PredictionError(
                'The demo model is not on disk. Run: python manage.py train_models',
                missing=True,
            )
        _CACHE[key] = joblib.load(path)
    return _CACHE[key]


def _number(payload, name, low, high):
    if name not in payload:
        raise PredictionError(f'{name} is required.')
    value = payload[name]
    if isinstance(value, bool):
        raise PredictionError(f'{name} must be a number.')
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise PredictionError(f'{name} must be a number.')
    if value != value or value in (float('inf'), float('-inf')):
        raise PredictionError(f'{name} must be a finite number.')
    if value < low or value > high:
        raise PredictionError(f'{name} must be between {low} and {high}.')
    return value


def _integer(payload, name, low, high):
    value = _number(payload, name, low, high)
    if int(value) != value:
        raise PredictionError(f'{name} must be a whole number.')
    return int(value)


def _choice(payload, name, allowed):
    if name not in payload or payload[name] in (None, ''):
        raise PredictionError(f'{name} is required.')
    value = str(payload[name])
    if value not in allowed:
        raise PredictionError(f'{name} must be one of: {", ".join(allowed)}.')
    return value

