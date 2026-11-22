from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from apps.accounts.access import OwnedDeleteView, OwnedUpdateView
from apps.accounts.models import User
from apps.accounts.permissions import role_required, user_is_admin
from apps.resources.forms import ResourcePassportForm
from apps.resources.models import ResourcePassport


def _rows(objects, cells, edit_name, delete_name):
    return [
        {
            'cells': cells(obj),
            'edit_url': reverse(edit_name, args=[obj.pk]),
            'delete_url': reverse(delete_name, args=[obj.pk]),
        }
        for obj in objects
    ]


@role_required(User.Role.CITIZEN)
def passport_list(request):
    form = ResourcePassportForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        passport = form.save(commit=False)
        passport.owner = request.user
        passport.save()
        messages.success(request, 'Passport saved.')
        return redirect('resources:passports')
    passports = ResourcePassport.objects.select_related('home', 'owner')
    if not user_is_admin(request.user):
        passports = passports.filter(owner=request.user)
    return render(request, 'manage/collection.html', {
        'title': 'Resource passport',
        'kicker': 'Citizen',
        'form': form,
        'form_title': 'Add a passport entry',
        'empty_note': 'Add a home before you add a passport entry.',
        'headings': ['Home', 'Period', 'Water m³', 'Energy kWh'],
        'rows': _rows(
            passports,
            lambda item: [item.home.name, item.period_label, item.water_used_m3, item.energy_used_kwh],
            'resources:passport_edit',
            'resources:passport_delete',
        ),
    })


class PassportUpdateView(OwnedUpdateView):
    model = ResourcePassport
    form_class = ResourcePassportForm
    allowed_roles = (User.Role.CITIZEN,)
    success_url = reverse_lazy('resources:passports')
    title = 'Edit passport entry'


class PassportDeleteView(OwnedDeleteView):
    model = ResourcePassport
    allowed_roles = (User.Role.CITIZEN,)
    success_url = reverse_lazy('resources:passports')
