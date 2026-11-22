import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from apps.accounts.models import User

PUBLIC_ROLES = (
    (User.Role.CITIZEN, 'Citoyen : je suis ma maison'),
    (User.Role.FARMER, 'Agriculteur : je suis ma ferme'),
)


def style_form(form):
    from apps.accounts.fr import french_form
    french_form(form)
    for field in form.fields.values():
        widget_name = field.widget.__class__.__name__
        if widget_name in {'Select', 'SelectMultiple'}:
            css = 'form-select'
        elif getattr(field.widget, 'input_type', '') == 'checkbox':
            css = 'form-check-input'
        else:
            css = 'form-control'
        field.widget.attrs['class'] = css


class BootstrapModelForm(forms.ModelForm):
    needs_user = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


def normalize_phone(raw):
    """Numéro tunisien : 8 chiffres, avec ou sans +216 / 00216, espaces tolérés."""
    digits = re.sub(r'[^0-9+]', '', raw or '')
    if digits.startswith('00216'):
        digits = digits[5:]
    elif digits.startswith('+216'):
        digits = digits[4:]
    elif digits.startswith('216') and len(digits) == 11:
        digits = digits[3:]
    if not re.fullmatch(r'[2-9][0-9]{7}', digits):
        return None
    return '+216' + digits


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False, label='Adresse e-mail')
    phone = forms.CharField(
        required=False,
        label='Numéro de téléphone',
        max_length=20,
        help_text='8 chiffres, par exemple 98 123 456. Vous pourrez vous connecter avec ce numéro.',
    )
    role = forms.ChoiceField(
        choices=PUBLIC_ROLES,
        label='Je suis',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'role', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields['email'].help_text = 'Pour vous joindre. Aucune confirmation n’est demandée.'
        self.fields['phone'].widget.attrs.update({
            'inputmode': 'tel', 'autocomplete': 'tel', 'placeholder': '+216 98 123 456',
        })
        self.fields['email'].widget.attrs['autocomplete'] = 'email'

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        email = (cleaned.get('email') or '').strip()
        raw_phone = (cleaned.get('phone') or '').strip()
        if role == User.Role.FARMER:
            cleaned['email'] = ''
            phone = normalize_phone(raw_phone)
            if not raw_phone:
                self.add_error('phone', 'Entrez votre numéro de téléphone.')
            elif not phone:
                self.add_error('phone', 'Numéro invalide : 8 chiffres, par exemple 98 123 456.')
            elif User.objects.filter(phone=phone).exists():
                self.add_error('phone', 'Un compte utilise déjà ce numéro. Connectez-vous avec lui.')
            else:
                cleaned['phone'] = phone
        else:
            cleaned['phone'] = ''
            if not email:
                self.add_error('email', 'Entrez votre adresse e-mail.')
            elif User.objects.filter(email__iexact=email).exists():
                self.add_error(
                    'email',
                    'Un compte utilise déjà cette adresse. Connectez-vous, ou choisissez une autre adresse.',
                )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        style_form(self)


class KizunaPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)


class KizunaLoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'Nom d’utilisateur ou mot de passe incorrect. '
            'Vérifiez les majuscules, ou créez un compte si vous n’en avez pas encore.'
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_form(self)
        self.fields['username'].label = 'Nom d’utilisateur ou numéro de téléphone'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'
