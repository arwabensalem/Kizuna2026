from django.test import TestCase
from django.urls import reverse

from apps.crisis.day import build_crisis_day
from apps.crisis.demo_mode import CHAPTERS, FINALE_QUOTE, build_demo
from apps.simulation.models import SimulationClock, SimulationStep
from apps.tunisia.index import _mean_scores, _profile
from apps.tunisia.places import GOVERNORATES


class DemoModeTests(TestCase):
    def test_the_story_is_the_same_every_time(self):
        self.assertEqual(build_demo(), build_demo())

    def test_the_twenty_four_chapters_follow_the_script(self):
        demo = build_demo()
        self.assertEqual([step['title'] for step in demo['steps']], list(CHAPTERS))
        self.assertEqual(demo['finale']['quote'], FINALE_QUOTE)
        self.assertEqual(demo['finale']['headline'], 'CRISIS CONTAINED')

    def test_the_home_rules_and_the_crisis_series_are_the_source(self):
        demo = build_demo()
        steps = {step['title']: step for step in demo['steps']}
        self.assertEqual(steps['NORMAL RESOURCE CONSUMPTION']['brain'][1]['value'], 'normal')
        self.assertEqual(steps['LEAK DETECTION']['brain'][1]['value'], 'critical_abnormal')
        self.assertEqual(steps['AUTONOMOUS VALVE CLOSURE']['twin']['valve'], 'closed')
        self.assertIn('critical water leak', steps['AUTONOMOUS VALVE CLOSURE']['narration'])
        self.assertEqual(steps['SOLAR-POWERED IRRIGATION']['twin']['pump'], 'solar')
        self.assertEqual(steps['PUMP INTERRUPTION']['twin']['pump'], 'off')
        chain = {
            (item['source'], item['destination'])
            for item in steps['SOLAR → BATTERY → PUMP']['flows']
        }
        self.assertIn(('solar', 'pump'), chain)
        self.assertIn(('solar', 'battery'), chain)
        day = {frame['time']: frame for frame in build_crisis_day()['beats']}
        recovered = [item for item in day['18:01']['flows'] if item['source'] == 'rain']
        shown = [item for item in steps['WATER RECOVERY']['flows'] if item['source'] == 'rain']
        self.assertEqual(shown[0]['quantity'], recovered[0]['quantity'])
        self.assertEqual(
            steps['CRISIS CONTAINED']['summary']['headline'],
            'CRISIS CONTAINED',
        )

    def test_the_tunisia_score_is_the_fixed_profile_mean(self):
        demo = build_demo()
        rows = [
            _profile(name, band, 'NORMAL')
            for name, (band, *_rest) in GOVERNORATES.items()
        ]
        expected = _mean_scores(rows)
        self.assertEqual(demo['atlas']['national']['overall'], expected['overall'])
        self.assertIn('Not a measurement', demo['atlas']['note'])

    def test_playing_the_page_does_not_move_the_clock(self):
        before_clock = list(SimulationClock.objects.values_list('hour', 'scenario'))
        before_steps = SimulationStep.objects.count()
        page = self.client.get(reverse('demo'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'DEMO MODE')
        self.assertContains(page, 'START KIZUNA')
        self.assertContains(page, 'START DEMO')
        self.assertContains(page, 'PAUSE')
        self.assertContains(page, 'RESET')
        self.assertContains(page, FINALE_QUOTE)
        self.assertContains(page, 'CRISIS CONTAINED')
        self.assertContains(page, 'shared simulation clock')
        self.assertContains(page, 'weather service')
        self.assertContains(page, 'js/demo.js')
        self.assertEqual(
            list(SimulationClock.objects.values_list('hour', 'scenario')),
            before_clock,
        )
        self.assertEqual(SimulationStep.objects.count(), before_steps)

    def test_the_home_page_opens_the_demo(self):
        page = self.client.get('/')
        self.assertContains(page, 'Voir la démonstration')
        self.assertContains(page, reverse('demo'))
