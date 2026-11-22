import json
import tempfile
from pathlib import Path

import joblib
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.ai_engine.services import detect_anomaly, predict_energy, predict_farm_water, predict_water
from apps.ai_engine.training import train_all
from engine.orchestrator import Orchestrator

User = get_user_model()

WATER = {
    'residents': 3,
    'temperature': 28,
    'day_of_week': 1,
    'historical_consumption': 10,
    'appliance_usage': 4,
}
ENERGY = {
    'temperature': 28,
    'appliance_load': 800,
    'solar_production': 400,
    'hour': 18,
    'historical_energy': 700,
}
FARM = {
    'soil_moisture': 40,
    'temperature': 30,
    'humidity': 45,
    'rainfall': 0,
    'crop_type': 'olive',
    'soil_type': 'loam',
    'area': 1000,
}
NORMAL_READING = {
    'temperature': 27,
    'humidity': 58,
    'water_consumption': 14,
    'electricity_consumption': 700,
    'soil_moisture': 46,
    'rainfall': 0,
    'tank_level': 70,
    'solar_production': 1200,
}
EXTREME_READING = {
    'temperature': 68,
    'humidity': 2,
    'water_consumption': 800,
    'electricity_consumption': 18000,
    'soil_moisture': 1,
    'rainfall': 120,
    'tank_level': 1,
    'solar_production': 12000,
}


class OrchestratorContractTests(TestCase):
    def test_decide_waits_for_its_phase(self):
        with self.assertRaises(NotImplementedError):
            Orchestrator().decide({})


class AiEngineTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media = tempfile.TemporaryDirectory()
        cls.report = train_all(Path(cls._media.name) / 'models')

    @classmethod
    def tearDownClass(cls):
        cls._media.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.override = override_settings(MEDIA_ROOT=self._media.name)
        self.override.enable()
        self.user = User.objects.create_user('ai.demo', password='Kizuna-ai-2026')
        self.client.force_login(self.user)

    def tearDown(self):
        self.override.disable()
        super().tearDown()

    def test_validation_metrics_come_from_the_held_out_split(self):
        water = self.report['tasks']['water']['validation']
        anomaly = self.report['tasks']['anomaly']['validation']
        for key in ('mae', 'rmse', 'r2'):
            self.assertIsInstance(water[key], float)
        for key in ('precision', 'recall', 'f1'):
            self.assertIsInstance(anomaly[key], float)
        saved = json.loads(Path(self._media.name, 'models', 'metrics.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['tasks']['water']['validation'], water)
        self.assertEqual(saved['training_data'], 'synthetic_demo')
        self.assertIn('Synthetic', saved['label'])
        bundle = joblib.load(Path(self._media.name, 'models', 'anomaly.joblib'))
        self.assertNotIn('is_anomaly', bundle['columns'])

    def test_predictions_follow_the_demo_features(self):
        low = predict_water(WATER)
        high = predict_water({**WATER, 'residents': 8})
        self.assertGreater(high['prediction'], low['prediction'])
        self.assertEqual(low['prediction'], predict_water(WATER)['prediction'])
        self.assertEqual(low['training_data'], 'synthetic_demo')
        self.assertIn('Synthetic', low['label'])
        self.assertEqual(low['validation']['mae'], self.report['tasks']['water']['validation']['mae'])

        quiet = predict_energy(ENERGY)
        loaded = predict_energy({**ENERGY, 'appliance_load': 3000})
        self.assertGreater(loaded['prediction'], quiet['prediction'])

        small = predict_farm_water(FARM)
        large = predict_farm_water({**FARM, 'area': 4000})
        self.assertGreater(large['prediction'], small['prediction'])

        typical = detect_anomaly(NORMAL_READING)
        extreme = detect_anomaly(EXTREME_READING)
        self.assertLess(extreme['score'], typical['score'])
        self.assertTrue(extreme['anomaly'])
        self.assertIn('planted', extreme['validation_note'])

    def test_api_scores_and_rejects_bad_input(self):
        response = self.client.post(
            '/api/ai/water/',
            data=json.dumps(WATER),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['training_data'], 'synthetic_demo')
        self.assertIn('Synthetic', body['label'])
        self.assertEqual(body['model'], 'RandomForestRegressor')
        self.assertEqual(body['validation']['mae'], self.report['tasks']['water']['validation']['mae'])

        energy = self.client.post(
            '/api/ai/energy/',
            data=json.dumps(ENERGY),
            content_type='application/json',
        )
        self.assertEqual(energy.status_code, 200)
        self.assertEqual(energy.json()['model'], 'GradientBoostingRegressor')

        farm = self.client.post(
            '/api/ai/farm-water/',
            data=json.dumps(FARM),
            content_type='application/json',
        )
        self.assertEqual(farm.status_code, 200)
        self.assertEqual(farm.json()['unit'], 'L/day')

        stress = self.client.post(
            '/api/ai/crop-stress/',
            data=json.dumps(FARM),
            content_type='application/json',
        )
        self.assertEqual(stress.status_code, 200)
        self.assertGreaterEqual(stress.json()['prediction'], 0)
        self.assertLessEqual(stress.json()['prediction'], 100)

        reading = self.client.post(
            '/api/ai/anomaly/',
            data=json.dumps(EXTREME_READING),
            content_type='application/json',
        )
        self.assertEqual(reading.status_code, 200)
        self.assertTrue(reading.json()['anomaly'])
        self.assertEqual(reading.json()['model'], 'IsolationForest')

        rejected = self.client.post(
            '/api/ai/farm-water/',
            data=json.dumps({**FARM, 'crop_type': 'banana'}),
            content_type='application/json',
        )
        self.assertEqual(rejected.status_code, 400)

        page = self.client.get('/ai/')
        self.assertContains(page, 'Synthetic demo')
        self.assertContains(page, 'Validation MAE')
        self.assertContains(page, 'not a claim about real households')

    def test_anonymous_cannot_predict(self):
        self.client.logout()
        response = self.client.post(
            '/api/ai/energy/',
            data=json.dumps(ENERGY),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_model_is_reported(self):
        with tempfile.TemporaryDirectory() as empty:
            with override_settings(MEDIA_ROOT=empty):
                response = self.client.post(
                    '/api/ai/water/',
                    data=json.dumps(WATER),
                    content_type='application/json',
                )
        self.assertEqual(response.status_code, 503)
        self.assertIn('train_models', response.json()['detail'])
