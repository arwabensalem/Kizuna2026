from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.homes.models import Home
from apps.resources.league import _place, build_league
from apps.resources.passport import hour_scores
from apps.simulation.models import SimulationStep
from apps.simulation.services import advance_simulation, reset_simulation


def summary(values):
    mid = len(values) // 2
    baseline = round(sum(values[:mid]) / mid, 1)
    current = round(sum(values[mid:]) / (len(values) - mid), 1)
    improvement = round((current - baseline) / baseline * 100, 1)
    return baseline, current, improvement


class LeagueTests(TestCase):
    def setUp(self):
        reset_simulation(scenario='NORMAL')
        advance_simulation(steps=12)
        self.user = User.objects.create_user(username='league', password='Kizuna-league-2026')
        self.other = User.objects.create_user(username='league-other', password='Kizuna-league-2026')
        Home.objects.create(owner=self.user, name='House 1')
        Home.objects.create(owner=self.other, name='Arwa')

    def test_home_improvement_is_the_later_hours_against_the_earlier_ones(self):
        values = [hour_scores(step.payload)['home'] for step in SimulationStep.objects.order_by('hour')]
        baseline, current, improvement = summary(values)
        row = next(item for item in build_league(self.user)['rows'] if item['id'] == 'clock-home')
        self.assertEqual(row['baseline'], baseline)
        self.assertEqual(row['current'], current)
        self.assertEqual(row['improvement'], improvement)
        self.assertEqual(row['rank'], 1 if row['improvement'] == max(
            item['improvement'] for item in build_league(self.user)['rows'] if item['improvement'] is not None
        ) else row['rank'])

    def test_the_board_is_ordered_by_improvement(self):
        ranked = [row for row in build_league(self.user)['rows'] if row['rank']]
        improvements = [row['improvement'] for row in ranked]
        self.assertEqual(improvements, sorted(improvements, reverse=True))
        self.assertGreater(len(ranked), 1)

    def test_higher_use_still_ranks_first_when_it_improved_more(self):
        ordered = _place([
            {'name': 'Quiet', 'improvement': 4.0, 'water_l': 10},
            {'name': 'Busy', 'improvement': 18.0, 'water_l': 900},
        ])
        self.assertEqual(ordered[0]['name'], 'Busy')
        self.assertEqual(ordered[0]['rank'], 1)
        self.assertGreater(ordered[0]['water_l'], ordered[1]['water_l'])

    def test_neighbourhoods_move_by_different_amounts(self):
        rows = build_league(self.user, 'neighborhood')['rows']
        self.assertEqual(len(rows), 24)
        improvements = {row['improvement'] for row in rows}
        self.assertGreater(len(improvements), 1)
        self.assertTrue(all(row['kind'] == 'neighborhood' for row in rows))

    def test_a_home_without_an_earlier_reading_is_not_ranked(self):
        rows = build_league(self.user, 'home')['rows']
        house = next(row for row in rows if row['name'] == 'House 1')
        self.assertIsNone(house['rank'])
        self.assertIsNone(house['improvement'])
        self.assertIsNotNone(house['resilience'])
        self.assertNotIn('Arwa', {row['name'] for row in rows})

    def test_filters_keep_one_kind(self):
        self.assertTrue(all(row['kind'] == 'farm' for row in build_league(self.user, 'farm')['rows']))
        self.assertTrue(all(row['kind'] == 'business' for row in build_league(self.user, 'business')['rows']))

    def test_the_same_hours_give_the_same_board(self):
        self.assertEqual(build_league(self.user)['rows'], build_league(self.user)['rows'])


class LeaguePageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='board', password='Kizuna-league-2026')

    def test_page_requires_login(self):
        self.assertEqual(self.client.get(reverse('league:board')).status_code, 302)

    def test_page_shows_the_filters_and_the_rule(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('league:board'))
        self.assertContains(response, 'not by who uses the least')
        self.assertContains(response, 'Home A')
        for name in ('Homes', 'Farms', 'Workshops', 'Neighborhoods'):
            self.assertContains(response, name)
        filtered = self.client.get(reverse('league:board'), {'kind': 'neighborhoods'})
        self.assertContains(filtered, 'Lafayette')
        self.assertNotContains(filtered, 'Home A')
