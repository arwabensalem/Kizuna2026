from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.crisis.day import BEATS, build_crisis_day


class CrisisDayTests(TestCase):
    def test_the_day_is_the_same_every_time(self):
        self.assertEqual(build_crisis_day(), build_crisis_day())

    def test_the_timeline_matches_the_script(self):
        frames = build_crisis_day()['beats']
        self.assertEqual(
            [(frame['time'], frame['title']) for frame in frames],
            [(f'{clock:02d}:{minute:02d}', title) for clock, minute, title in BEATS],
        )

    def test_shared_hours_do_not_invent_a_second_sample(self):
        frames = {frame['time']: frame for frame in build_crisis_day()['beats']}
        for stamp in ('14:15', '14:20', '14:25'):
            self.assertEqual(frames[stamp]['twin']['soil'], frames['14:00']['twin']['soil'])
            self.assertEqual(frames[stamp]['chart']['crop_stress'], frames['14:00']['chart']['crop_stress'])
            self.assertIn('Lab hour 14:00', frames[stamp]['note'])
        self.assertEqual(_flag(frames['14:20'], 'KIZUNA'), 'OFF')
        self.assertEqual(_flag(frames['14:25'], 'KIZUNA'), 'ON')
        self.assertEqual(frames['14:25']['twin']['pump'], 'off')
        self.assertEqual(_flag(frames['14:26'], 'KIZUNA'), 'ON')
        for frame in frames.values():
            brain = _flag(frame, 'KIZUNA')
            chain = next(item['value'] for item in frame['propagation'] if item['label'] == 'KIZUNA')
            self.assertEqual(brain, chain)

    def test_pumps_stop_then_solar_runs_them(self):
        frames = {frame['time']: frame for frame in build_crisis_day()['beats']}
        self.assertEqual(frames['14:15']['twin']['pump'], 'off')
        self.assertEqual(frames['14:26']['twin']['pump'], 'solar')
        chain = {(item['source'], item['destination']) for item in frames['14:26']['flows']}
        self.assertIn(('solar', 'pump'), chain)
        self.assertIn(('solar', 'battery'), chain)
        self.assertIn(('pump', 'irrigation'), chain)

    def test_rain_is_collected_only_after_it_falls(self):
        frames = {frame['time']: frame for frame in build_crisis_day()['beats']}
        self.assertFalse(any(item['source'] == 'rain' for item in frames['18:00']['flows']))
        collected = [item for item in frames['18:01']['flows'] if item['source'] == 'rain']
        self.assertEqual(len(collected), 1)
        self.assertGreater(collected[0]['quantity'], 0)

    def test_the_end_uses_the_run(self):
        day = build_crisis_day()
        summary = day['summary']
        self.assertEqual(summary['headline'], 'CRISIS CONTAINED')
        self.assertEqual(summary['homes_stabilized'], 1)
        self.assertEqual(summary['water_saved_l'], summary['water_recovered_l'])
        self.assertGreater(summary['energy_recovered_wh'], 0)
        self.assertGreater(summary['crops_protected'], 0)
        self.assertLess(summary['final']['crop_stress'], 55)
        self.assertTrue(frames_actions(day))

    def test_page_and_api_require_login(self):
        self.assertEqual(self.client.get(reverse('crisis:day')).status_code, 302)
        response = self.client.get(reverse('crisis_day'))
        self.assertEqual(response.status_code, 403)

    def test_page_has_the_controls(self):
        user = User.objects.create_user(username='day', password='Kizuna-day-2026')
        self.client.force_login(user)
        page = self.client.get(reverse('crisis:day'))
        self.assertContains(page, 'START CRISIS DAY')
        self.assertContains(page, 'PAUSE')
        self.assertContains(page, 'RESET')
        self.assertContains(page, 'does not call a weather service')
        api = self.client.get(reverse('crisis_day'))
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json()['summary']['headline'], 'CRISIS CONTAINED')


def frames_actions(day):
    return any(frame['actions'] for frame in day['beats'])


def _flag(frame, label):
    return next(item['value'] for item in frame['brain'] if item['label'] == label)
