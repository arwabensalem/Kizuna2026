from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.forms import BootstrapModelForm, style_form
from apps.farms.models import Farm
from apps.marketplace import trade
from apps.marketplace.models import BuyerRequest, Product

CERT_FIELDS = tuple(f'cert_{code}' for code in trade.CERTIFICATIONS)


class ProductForm(BootstrapModelForm):
    class Meta:
        model = Product
        fields = (
            'name',
            'category',
            'quantity',
            'unit',
            'price_tnd',
            'min_order',
            'origin',
            'farm',
            'harvest_date',
            'availability',
            'export_ready',
            'description',
        )
        widgets = {
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'name': 'Product name',
            'harvest_date': 'Harvest date',
            'price_tnd': 'Votre prix juste, départ ferme (TND par unité)',
            'min_order': 'Commande minimum (en unités)',
            'farm': 'Ferme d’origine (pour la carte et la traçabilité)',
            'export_ready': 'Je peux préparer un envoi à l’étranger',
            'description': "L'histoire de cette récolte",
        }
        help_texts = {
            'price_tnd': "C'est ce que vous touchez. Les acheteurs voient aussi le prix converti en €, $ et ¥.",
        }

    def __init__(self, *args, farmer=None, **kwargs):
        super().__init__(*args, **kwargs)
        farms = Farm.objects.filter(owner=farmer) if farmer is not None else Farm.objects.none()
        if self.instance.pk and self.instance.farm_id:
            farms = Farm.objects.filter(pk=self.instance.farm_id) | farms
        self.fields['farm'].queryset = farms
        current = set(self.instance.certification_codes) if self.instance.pk else set()
        for code, labels in trade.CERTIFICATIONS.items():
            field = forms.BooleanField(required=False, label=f'Certification : {labels["fr"]}')
            field.widget.attrs['class'] = 'form-check-input'
            field.initial = code in current
            self.fields[f'cert_{code}'] = field

    def save(self, commit=True):
        product = super().save(commit=False)
        product.certifications = ','.join(
            code for code in trade.CERTIFICATIONS if self.cleaned_data.get(f'cert_{code}')
        )
        if commit:
            product.save()
        return product


OFFER_LABELS = {
    'fr': {
        'quantity': 'Quantité souhaitée',
        'offer_price': 'Votre prix proposé (par unité)',
        'currency': 'Devise',
        'destination': 'Destination',
        'incoterm': 'Incoterm',
        'message': "Message à l'agriculteur",
        'listed': 'En ligne',
        'empty_price': 'Laissez vide pour accepter le prix affiché.',
    },
    'en': {
        'quantity': 'Quantity wanted',
        'offer_price': 'Your price offer (per unit)',
        'currency': 'Currency',
        'destination': 'Destination',
        'incoterm': 'Incoterm',
        'message': 'Message to the farmer',
        'listed': 'Listed',
        'empty_price': 'Leave empty to accept the listed price.',
    },
    'ja': {
        'quantity': '希望数量',
        'offer_price': '提示価格（1単位あたり）',
        'currency': '通貨',
        'destination': '仕向地',
        'incoterm': 'インコタームズ',
        'message': '農家へのメッセージ',
        'listed': '掲載数量',
        'empty_price': '空欄の場合は掲載価格で承諾します。',
    },
}

INCOTERMS = (
    ('FOB', 'FOB Radès (port tunisien)'),
    ('CIF', 'CIF (port de destination)'),
    ('EXW', 'EXW (départ ferme)'),
)


class BuyerRequestForm(BootstrapModelForm):
    offer_price = forms.DecimalField(
        required=False, min_value=Decimal('0.01'), decimal_places=2, max_digits=12,
    )
    currency = forms.ChoiceField(required=False, choices=[(c, c) for c in trade.CURRENCIES])
    destination = forms.ChoiceField(required=False)
    incoterm = forms.ChoiceField(required=False, choices=INCOTERMS)

    class Meta:
        model = BuyerRequest
        fields = ('quantity', 'message')
        labels = {
            'quantity': 'Quantity to request',
            'message': 'Message to the farmer',
        }
        widgets = {'message': forms.Textarea(attrs={'rows': 3})}

    field_order = ('quantity', 'offer_price', 'currency', 'destination', 'incoterm', 'message')

    def __init__(self, *args, product, lang='fr', currency='TND', destination='', **kwargs):
        self.product = product
        super().__init__(*args, **kwargs)
        lang = trade.clean_lang(lang)
        words = OFFER_LABELS[lang]
        self.fields['destination'].choices = trade.destination_choices(lang)
        self.fields['currency'].initial = trade.clean_currency(currency)
        self.fields['destination'].initial = trade.clean_destination(destination)
        self.fields['incoterm'].initial = 'FOB'
        for name in ('quantity', 'offer_price', 'currency', 'destination', 'incoterm', 'message'):
            self.fields[name].label = words[name]
        self.fields['quantity'].required = True
        self.fields['message'].required = False
        self.fields['quantity'].help_text = (
            f"{words['listed']} : {product.quantity} {product.get_unit_display()}."
        )
        self.fields['offer_price'].help_text = words['empty_price']

    def clean_currency(self):
        return trade.clean_currency(self.cleaned_data.get('currency'))

    def save(self, commit=True):
        offer = super().save(commit=False)
        currency = self.cleaned_data.get('currency') or 'TND'
        price = self.cleaned_data.get('offer_price')
        offer.currency = currency
        offer.offer_price_tnd = trade.to_tnd(price, currency) if price else self.product.price_tnd
        offer.destination = self.cleaned_data.get('destination') or ''
        offer.incoterm = self.cleaned_data.get('incoterm') or 'FOB'
        if commit:
            offer.save()
        return offer

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity > self.product.quantity:
            raise ValidationError(
                f'Only {self.product.quantity} {self.product.get_unit_display()} is listed.'
            )
        return quantity


class FarmerContactForm(forms.Form):
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        required=False,
        label='About a listing',
    )
    quantity = forms.DecimalField(
        required=False,
        min_value=Decimal('0.01'),
        decimal_places=2,
        max_digits=10,
        label='Quantity',
    )
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, farmer, **kwargs):
        self.farmer = farmer
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(farmer=farmer)
        self.fields['product'].help_text = 'Leave this empty to contact the farmer without a listing.'
        style_form(self)

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get('product')
        quantity = cleaned.get('quantity')
        if product and product.farmer_id != self.farmer.id:
            self.add_error('product', 'Choose one of this farmer’s listings.')
        if quantity and product is None:
            self.add_error('product', 'Choose a listing for that quantity.')
        if product and quantity and quantity > product.quantity:
            self.add_error(
                'quantity',
                f'Only {product.quantity} {product.get_unit_display()} is listed.',
            )
        if product and product.availability == Product.Availability.UNAVAILABLE and quantity:
            self.add_error('quantity', 'That listing is unavailable.')
        return cleaned


class OfferReplyForm(forms.Form):
    """Réponse dans le fil d'une offre : message, contre-offre ou décision."""

    ACTIONS = ('message', 'counter', 'accept', 'decline')

    action = forms.ChoiceField(choices=[(a, a) for a in ACTIONS])
    body = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}), label='Message')
    price = forms.DecimalField(
        required=False, min_value=Decimal('0.01'), decimal_places=2, max_digits=12,
        label='Nouveau prix par unité',
    )
    currency = forms.ChoiceField(
        required=False, choices=[(c, c) for c in trade.CURRENCIES], label='Devise',
    )

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get('action')
        if action == 'counter' and not cleaned.get('price'):
            self.add_error('price', 'Indiquez votre nouveau prix.')
        if action == 'message' and not (cleaned.get('body') or '').strip():
            self.add_error('body', 'Écrivez un message.')
        return cleaned
