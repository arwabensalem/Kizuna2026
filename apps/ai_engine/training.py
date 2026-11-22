"""Train the demo models and write them under media/models.

Run `python manage.py train_models`. Validation metrics are computed on the
held-out split and saved. They are not typed in by hand.
"""

import json
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest, RandomForestRegressor
from sklearn.metrics import (
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    root_mean_squared_error,
)
from sklearn.model_selection import train_test_split

from apps.ai_engine.datasets import (
    DATASET,
    SEED,
    anomaly_frame,
    design_matrix,
    energy_frame,
    farm_frame,
    water_frame,
    ANOMALY_SPEC,
    ENERGY_SPEC,
    FARM_SPEC,
    WATER_SPEC,
)

ROWS = 3200
VALIDATION_FRACTION = 0.2
LABEL = (
    'Synthetic demo model. Trained on generated rows, not on live meters '
    'and not on a real place.'
)


def models_dir(directory=None):
    if directory is None:
        return Path(settings.MEDIA_ROOT) / 'models'
    return Path(directory)


def train_all(directory=None):
    directory = models_dir(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'datasets').mkdir(exist_ok=True)

    water = water_frame(ROWS, SEED)
    energy = energy_frame(ROWS, SEED)
    farm = farm_frame(ROWS, SEED)
    anomaly = anomaly_frame(ROWS, SEED)

    tasks = {
        'water': _train_regressor(
            'water',
            water,
            'water_liters_per_hour',
            WATER_SPEC,
            RandomForestRegressor(
                n_estimators=80,
                max_depth=8,
                min_samples_leaf=2,
                random_state=SEED,
                n_jobs=1,
            ),
            'L/h',
            directory,
        ),
        'energy': _train_regressor(
            'energy',
            energy,
            'electricity_watts',
            ENERGY_SPEC,
            GradientBoostingRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.08,
                random_state=SEED,
            ),
            'W',
            directory,
        ),
        'farm_water': _train_regressor(
            'farm_water',
            farm,
            'farm_water_liters_per_day',
            FARM_SPEC,
            RandomForestRegressor(
                n_estimators=80,
                max_depth=8,
                min_samples_leaf=2,
                random_state=SEED,
                n_jobs=1,
            ),
            'L/day',
            directory,
        ),
        'crop_stress': _train_regressor(
            'crop_stress',
            farm,
            'crop_stress',
            FARM_SPEC,
            GradientBoostingRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.08,
                random_state=SEED,
            ),
            'points',
            directory,
        ),
        'anomaly': _train_anomaly(anomaly, directory),
    }
    report = {
        'training_data': DATASET,
        'label': LABEL,
        'seed': SEED,
        'rows': ROWS,
        'validation_fraction': VALIDATION_FRACTION,
        'tasks': tasks,
    }
    (directory / 'metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def _train_regressor(name, frame, target, spec, estimator, unit, directory):
    features = design_matrix(frame, spec)
    values = frame[target].to_numpy(dtype=float)
    x_train, x_val, y_train, y_val = train_test_split(
        features,
        values,
        test_size=VALIDATION_FRACTION,
        random_state=SEED,
    )
    estimator.fit(x_train, y_train)
    predicted = estimator.predict(x_val)
    validation = {
        'mae': _round(mean_absolute_error(y_val, predicted)),
        'rmse': _round(root_mean_squared_error(y_val, predicted)),
        'r2': _round(r2_score(y_val, predicted)),
    }
    _dump(name, estimator, spec, list(features.columns), unit, directory)
    _write_csv(frame, directory / 'datasets' / f'{name}.csv')
    return _task(estimator, spec, unit, len(x_train), len(x_val), validation)


def _train_anomaly(frame, directory):
    features = design_matrix(frame, ANOMALY_SPEC)
    labels = frame['is_anomaly'].to_numpy(dtype=int)
    x_train, x_val, y_train, y_val = train_test_split(
        features,
        labels,
        test_size=VALIDATION_FRACTION,
        random_state=SEED,
        stratify=labels,
    )
    rate = float(np.mean(y_train))
    rate = min(max(rate, 0.01), 0.5)
    estimator = IsolationForest(
        n_estimators=200,
        contamination=rate,
        random_state=SEED,
        n_jobs=1,
    )
    estimator.fit(x_train)
    predicted = estimator.predict(x_val) == -1
    validation = {
        'precision': _round(precision_score(y_val, predicted, zero_division=0)),
        'recall': _round(recall_score(y_val, predicted, zero_division=0)),
        'f1': _round(f1_score(y_val, predicted, zero_division=0)),
    }
    _dump('anomaly', estimator, ANOMALY_SPEC, list(features.columns), '', directory)
    _write_csv(frame, directory / 'datasets' / 'anomaly.csv')
    task = _task(estimator, ANOMALY_SPEC, '', len(x_train), len(x_val), validation)
    task['note'] = (
        'Precision, recall, and F1 compare the model with outliers planted '
        'by the demo generator. Those rows sit far outside the generated '
        'normal range, and the labels are not field observations.'
    )
    return task


def _dump(name, estimator, spec, columns, unit, directory):
    joblib.dump(
        {
            'estimator': estimator,
            'spec': spec,
            'columns': columns,
            'model_name': type(estimator).__name__,
            'unit': unit,
            'task': name,
            'training_data': DATASET,
        },
        directory / f'{name}.joblib',
    )


def _write_csv(frame, path):
    exported = frame.copy()
    if 'dataset' not in exported.columns:
        exported.insert(0, 'dataset', DATASET)
    exported.to_csv(path, index=False)


def _task(estimator, spec, unit, n_train, n_validation, validation):
    features = list(spec['numeric']) + list(spec['categories'])
    return {
        'model': type(estimator).__name__,
        'unit': unit,
        'features': features,
        'n_train': int(n_train),
        'n_validation': int(n_validation),
        'validation': validation,
    }


def _round(value):
    return round(float(value), 6)
