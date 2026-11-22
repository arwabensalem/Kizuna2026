"""Authored weather series.

Every value on these rows is written for the simulation. Nothing here is a
reading from a station or a forecast service.
"""

HOUR_COUNT = 12

# temperature °C, humidity %, rainfall probability %, rainfall mm,
# solar radiation W/m², wind km/h.
RAIN_IN_4_HOURS = (
    (23.0, 58, 20, 0, 620, 12),
    (24.0, 60, 35, 0, 700, 14),
    (25.0, 64, 55, 0, 640, 16),
    (24.0, 70, 75, 0, 420, 18),
    (21.0, 82, 90, 4.0, 180, 22),
    (20.0, 88, 95, 8.0, 90, 24),
    (20.5, 84, 80, 2.0, 160, 20),
    (22.0, 72, 40, 0, 380, 16),
    (23.0, 64, 20, 0, 560, 14),
    (24.0, 58, 10, 0, 680, 12),
    (24.0, 55, 10, 0, 700, 12),
    (23.0, 55, 10, 0, 640, 11),
)

RAIN_NOW = (
    (20.0, 86, 95, 5.0, 120, 20),
    (20.0, 88, 90, 3.0, 140, 18),
    (21.0, 76, 50, 0, 320, 16),
    (22.0, 68, 30, 0, 480, 14),
    (23.0, 60, 15, 0, 620, 12),
    (24.0, 55, 10, 0, 700, 12),
    (24.0, 52, 10, 0, 720, 11),
    (23.5, 52, 10, 0, 680, 11),
    (23.0, 54, 10, 0, 600, 12),
    (22.0, 58, 15, 0, 420, 12),
    (21.0, 62, 15, 0, 180, 10),
    (20.5, 66, 20, 0, 40, 10),
)


def _steady(temp, humidity, probability, solar, wind):
    rows = []
    for hour in range(HOUR_COUNT):
        rows.append((
            temp + (1 if 2 <= hour <= 4 else 0),
            humidity,
            probability,
            0,
            solar,
            wind + (hour % 3),
        ))
    return tuple(rows)


SCENARIOS = {
    'rain_in_4_hours': {
        'label': 'Rain expected in 4 hours',
        'summary': 'The first rainfall is at hour 4. Earlier hours stay dry.',
        'hours': RAIN_IN_4_HOURS,
    },
    'clear_day': {
        'label': 'Clear day',
        'summary': 'Warm and dry for the whole simulated day.',
        'hours': _steady(26, 45, 5, 760, 10),
    },
    'rain_now': {
        'label': 'Rain this hour',
        'summary': 'Rain is already falling in hour 0 of the simulated series.',
        'hours': RAIN_NOW,
    },
    'hot_dry': {
        'label': 'Hot and dry',
        'summary': 'High temperature, strong sun, and no rainfall.',
        'hours': _steady(36, 25, 5, 900, 8),
    },
    'windy': {
        'label': 'Windy',
        'summary': 'Stronger wind, a dry sky, and no rainfall.',
        'hours': _steady(22, 50, 15, 500, 42),
    },
}
