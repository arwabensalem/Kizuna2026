from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.resources.league import KINDS, LABEL, build_league


@login_required
def league_board(request):
    kind = KINDS.get(request.GET.get('kind', ''))
    board = build_league(request.user, kind)
    return render(request, 'league/board.html', {
        'label': LABEL,
        'period': board['period'],
        'rows': board['rows'],
        'kind': request.GET.get('kind', '') if kind else '',
        'filters': (
            ('', 'All'),
            ('homes', 'Homes'),
            ('farms', 'Farms'),
            ('businesses', 'Workshops'),
            ('neighborhoods', 'Neighborhoods'),
        ),
    })
