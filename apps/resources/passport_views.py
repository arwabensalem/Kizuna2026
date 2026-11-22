from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.resources.passport import LABEL, build_passports


@login_required
def passport_board(request):
    board = build_passports(request.user)
    return render(request, 'passport/board.html', {
        'label': LABEL,
        'period': board['period'],
        'passports': board['passports'],
    })
