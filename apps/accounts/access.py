from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import DeleteView, UpdateView

from apps.accounts.permissions import RoleRequiredMixin, user_is_admin


class OwnedUpdateView(RoleRequiredMixin, UpdateView):
    owner_lookup = 'owner'
    template_name = 'manage/edit.html'
    title = 'Edit'
    success_message = 'Saved.'

    def get_queryset(self):
        queryset = super().get_queryset()
        if user_is_admin(self.request.user):
            return queryset
        return queryset.filter(**{self.owner_lookup: self.request.user})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if getattr(self.get_form_class(), 'needs_user', False):
            kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.title
        context['cancel_url'] = self.success_url
        return context


class OwnedDeleteView(RoleRequiredMixin, DeleteView):
    owner_lookup = 'owner'

    def get_queryset(self):
        queryset = super().get_queryset()
        if user_is_admin(self.request.user):
            return queryset
        return queryset.filter(**{self.owner_lookup: self.request.user})

    def get(self, request, *args, **kwargs):
        return redirect(self.success_url)

    def form_valid(self, form):
        messages.success(self.request, 'Deleted.')
        return super().form_valid(form)
