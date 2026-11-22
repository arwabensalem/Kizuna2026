import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required, user_is_admin
from apps.farms.models import Farm
from apps.marketplace.catalog import search_products
from apps.marketplace import buyer_ai, trade
from apps.marketplace.forms import BuyerRequestForm, FarmerContactForm, OfferReplyForm, ProductForm
from apps.marketplace.models import BuyerRequest, OfferMessage, Product
from apps.marketplace.proof import farm_proof, proof_labels


def _prefs(request):
    """Langue, devise et destination de l'acheteur, gardées en session."""
    session = request.session
    for key, param, clean in (
        ('market_lang', 'lang', trade.clean_lang),
        ('market_cur', 'cur', trade.clean_currency),
        ('market_dest', 'dest', trade.clean_destination),
    ):
        if param in request.GET:
            session[key] = clean(request.GET[param])
    lang = trade.clean_lang(session.get('market_lang', 'fr'))
    return {
        'lang': lang,
        'cur': trade.clean_currency(session.get('market_cur', 'TND')),
        'dest': trade.clean_destination(session.get('market_dest', trade.DEFAULT_DESTINATION)),
        'T': trade.STRINGS[lang],
        'languages': trade.LANGUAGES,
        'currencies': list(trade.CURRENCIES),
    }


def _decorate(product, prefs):
    """Ajoute à une annonce les textes traduits et le prix dans la devise choisie."""
    lang, cur = prefs['lang'], prefs['cur']
    product.cat_label = trade.CATEGORY_LABELS[product.category][lang]
    product.unit_label = trade.UNIT_LABELS[product.unit][lang]
    product.avail_label = trade.AVAILABILITY_LABELS[product.availability][lang]
    product.cert_labels = trade.certification_labels(product.certification_codes, lang)
    product.price_text = trade.money(product.price_tnd, cur) if product.price_tnd else ''
    product.share = trade.farmer_share(product.price_tnd, product.category, prefs['dest'])
    return product


def _offer_party(request, pk):
    offer = get_object_or_404(
        BuyerRequest.objects.select_related('buyer', 'farmer', 'product'), pk=pk,
    )
    if request.user.id not in (offer.buyer_id, offer.farmer_id) and not user_is_admin(request.user):
        raise Http404
    return offer


def _farmer_or_404(pk):
    farmer = get_object_or_404(User, pk=pk)
    if farmer.role != User.Role.FARMER and not Product.objects.filter(farmer=farmer).exists():
        raise Http404
    return farmer


def _owned_product(request, pk):
    products = Product.objects.all() if user_is_admin(request.user) else Product.objects.filter(farmer=request.user)
    return get_object_or_404(products, pk=pk)


@login_required
def marketplace(request):
    category = request.GET.get('category', '')
    availability = request.GET.get('availability', '')
    query = request.GET.get('q', '').strip()
    if category not in Product.Category.values:
        category = ''
    if availability not in Product.Availability.values:
        availability = ''
    export_only = request.GET.get('export') == '1'
    prefs = _prefs(request)
    lang = prefs['lang']
    products = [_decorate(p, prefs) for p in search_products(query, category, availability, export_only)]
    priced = [p for p in Product.objects.exclude(price_tnd=None)]
    shares = [trade.farmer_share(p.price_tnd, p.category, prefs['dest']) for p in priced]
    share = round(sum(shares) / len(shares)) if shares else 70
    return render(request, 'marketplace/marketplace.html', {
        **prefs,
        'products': products,
        'query': query,
        'category': category,
        'availability': availability,
        'export_only': export_only,
        'categories': [(v, trade.CATEGORY_LABELS[v][lang]) for v in Product.Category.values],
        'availabilities': [(v, trade.AVAILABILITY_LABELS[v][lang]) for v in Product.Availability.values],
        'can_list': user_is_admin(request.user) or request.user.role == User.Role.FARMER,
        'negotiation_product': (
            Product.objects.exclude(price_tnd=None)
            .exclude(availability=Product.Availability.UNAVAILABLE)
            .order_by('created_at').first()
            or Product.objects.first()
        ),
        'stats': {
            'farmers': Product.objects.values('farmer').distinct().count(),
            'listings': Product.objects.exclude(availability=Product.Availability.UNAVAILABLE).count(),
            'offers': BuyerRequest.objects.exclude(destination='').count(),
            'share': share,
            'cost': 100 - share,
        },
    })


@role_required(User.Role.FARMER)
def product_create(request):
    form = ProductForm(request.POST or None, farmer=request.user)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.farmer = request.user
        product.save()
        messages.success(request, f'« {product.name} » est en ligne.')
        return redirect('market:detail', pk=product.pk)
    return render(request, 'marketplace/product_form.html', {
        'form': form,
        'heading': 'Proposer une récolte',
    })


@role_required(User.Role.FARMER)
def product_edit(request, pk):
    product = _owned_product(request, pk)
    form = ProductForm(request.POST or None, instance=product, farmer=product.farmer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'« {product.name} » est mis à jour.')
        return redirect('market:detail', pk=product.pk)
    return render(request, 'marketplace/product_form.html', {
        'form': form,
        'heading': f'Modifier « {product.name} »',
        'product': product,
    })


@role_required(User.Role.FARMER)
@require_POST
def product_delete(request, pk):
    product = _owned_product(request, pk)
    name = product.name
    product.delete()
    messages.success(request, f'« {name} » n’est plus en ligne.')
    return redirect('market:board')


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related('farmer', 'farm'), pk=pk)
    prefs = _prefs(request)
    _decorate(product, prefs)
    is_farmer = product.farmer_id == request.user.id or user_is_admin(request.user)
    can_request = (
        product.farmer_id != request.user.id
        and product.availability != Product.Availability.UNAVAILABLE
    )
    form = None
    if can_request:
        form = BuyerRequestForm(
            request.POST or None, product=product,
            lang=prefs['lang'], currency=prefs['cur'], destination=prefs['dest'],
        )
        if request.method == 'POST' and form.is_valid():
            buyer_request = form.save(commit=False)
            buyer_request.buyer = request.user
            buyer_request.farmer = product.farmer
            buyer_request.product = product
            buyer_request.save()
            OfferMessage.objects.create(
                offer=buyer_request,
                author=request.user,
                body=buyer_request.message,
                price_tnd=buyer_request.offer_price_tnd,
                event='offer',
            )
            messages.success(
                request,
                f'Demande envoyée à {product.farmer.username} pour {buyer_request.quantity} {product.get_unit_display()}.',
            )
            return redirect('market:detail', pk=product.pk)

    lang, T = prefs['lang'], prefs['T']
    route = trade.route(prefs['dest'], lang)
    chain = direct = None
    if product.price_tnd:
        chain = trade.chain_labels(trade.traditional_chain(product.price_tnd, product.category), lang)
        direct = trade.direct_deal(product.price_tnd, product.category, prefs['dest'])
        direct['rows'] = trade.chain_labels(direct['rows'], lang)
        cur = prefs['cur']
        for step in chain + direct['rows']:
            step['text'] = trade.money(step['price'], cur)
        direct['landed_text'] = trade.money(direct['landed'], cur)
        direct['shelf_text'] = trade.money(direct['shelf_price'], cur)
        direct['multiplier_text'] = f"{direct['multiplier']:.1f}".replace('.', ',')
    farm = product.farm
    if farm and farm.latitude is not None and farm.longitude is not None:
        coords = (float(farm.latitude), float(farm.longitude))
    else:
        coords = trade.origin_coords(product.origin) or trade.origin_coords(farm.location if farm else '')
    listed = timezone.localdate(product.created_at) if product.created_at else timezone.localdate()
    ship = max(listed, timezone.localdate()) + timedelta(days=5)
    arrival_days = int(route['days'].split('–')[-1])
    return render(request, 'marketplace/product_detail.html', {
        **prefs,
        'product': product,
        'form': form,
        'is_farmer': is_farmer,
        'can_request': can_request,
        'chain': chain,
        'direct': direct,
        'route': route,
        'destinations': trade.destination_choices(lang),
        'prices': trade.all_prices(product.price_tnd) if product.price_tnd else [],
        'coords': coords,
        'proof': farm_proof(farm, lang),
        'proof_T': proof_labels(lang),
        'timeline': [
            (T['timeline_harvest'], product.harvest_date),
            (T['timeline_listed'], listed),
            (T['timeline_ship'], ship),
            (T['timeline_arrival'], ship + timedelta(days=arrival_days)),
        ],
    })


@login_required
def fair_price(request):
    """Calculateur : du prix départ ferme au prix en rayon, chaîne classique contre directe."""
    prefs = _prefs(request)
    lang = prefs['lang']
    category = request.GET.get('category', 'oil')
    if category not in Product.Category.values:
        category = 'oil'
    try:
        price = trade.Decimal(request.GET.get('price', '15').replace(',', '.'))
        if price <= 0 or price > 100000:
            raise ValueError
    except (ArithmeticError, ValueError):
        price = trade.Decimal('15')
    chain = trade.chain_labels(trade.traditional_chain(price, category), lang)
    direct = trade.direct_deal(price, category, prefs['dest'])
    direct['rows'] = trade.chain_labels(direct['rows'], lang)
    for step in chain + direct['rows']:
        step['text'] = trade.money(step['price'], prefs['cur'])
    direct['landed_text'] = trade.money(direct['landed'], prefs['cur'])
    direct['shelf_text'] = trade.money(direct['shelf_price'], prefs['cur'])
    direct['multiplier_text'] = f"{direct['multiplier']:.1f}".replace('.', ',')
    # Même en payant l'agriculteur deux fois plus, l'acheteur reste sous le prix en rayon.
    double = trade.direct_deal(price * 2, category, prefs['dest'])
    tonne = trade.Decimal('1000')
    return render(request, 'marketplace/fair_price.html', {
        **prefs,
        'price': price,
        'category': category,
        'categories': [(v, trade.CATEGORY_LABELS[v][lang]) for v in Product.Category.values],
        'destinations': trade.destination_choices(lang),
        'chain': chain,
        'direct': direct,
        'route': trade.route(prefs['dest'], lang),
        'prices': trade.all_prices(price),
        'tonne_shelf': trade.money(direct['shelf_price'] * tonne, prefs['cur']),
        'tonne_direct': trade.money(direct['landed'] * tonne, prefs['cur']),
        'tonne_double': trade.money(double['landed'] * tonne, prefs['cur']),
        'tonne_farmer': trade.money(price * tonne, prefs['cur']),
        'tonne_farmer_double': trade.money(price * 2 * tonne, prefs['cur']),
    })


@login_required
def offers(request):
    """Toutes les offres où l'utilisateur est acheteur ou agriculteur."""
    prefs = _prefs(request)
    items = (
        BuyerRequest.objects.filter(Q(buyer=request.user) | Q(farmer=request.user))
        .select_related('buyer', 'farmer', 'product')
    )
    rows = []
    for item in items:
        rows.append({
            'offer': item,
            'role': 'buyer' if item.buyer_id == request.user.id else 'farmer',
            'price': trade.money(item.offer_price_tnd, prefs['cur']) if item.offer_price_tnd else '—',
            'route': trade.route(item.destination, prefs['lang']) if item.destination else None,
        })
    return render(request, 'marketplace/offers.html', {**prefs, 'rows': rows})


def _last_proposer(offer):
    last = offer.thread.exclude(price_tnd=None).order_by('-created_at', '-pk').first()
    return last.author_id if last else offer.buyer_id


@login_required
def offer_detail(request, pk):
    offer = _offer_party(request, pk)
    prefs = _prefs(request)
    open_deal = offer.status in (BuyerRequest.Status.PENDING, BuyerRequest.Status.COUNTERED)
    form = OfferReplyForm(request.POST or None, initial={'currency': prefs['cur']})
    if request.method == 'POST' and form.is_valid():
        action = form.cleaned_data['action']
        body = (form.cleaned_data.get('body') or '').strip()
        if action != 'message' and not open_deal:
            messages.error(request, 'Cette offre est déjà conclue.')
            return redirect('market:offer', pk=offer.pk)
        if action == 'accept' and _last_proposer(offer) == request.user.id:
            messages.error(request, "Attendez la réponse de l'autre partie avant d'accepter votre propre prix.")
            return redirect('market:offer', pk=offer.pk)
        price = None
        if action == 'counter':
            price = trade.to_tnd(form.cleaned_data['price'], form.cleaned_data.get('currency') or 'TND')
            offer.offer_price_tnd = price
            offer.status = BuyerRequest.Status.COUNTERED
        elif action == 'accept':
            offer.status = BuyerRequest.Status.ACCEPTED
        elif action == 'decline':
            offer.status = BuyerRequest.Status.DECLINED
        offer.save()
        OfferMessage.objects.create(offer=offer, author=request.user, body=body, price_tnd=price, event=action)
        notes = {
            'message': 'Message envoyé.',
            'counter': 'Contre-offre envoyée.',
            'accept': 'Offre acceptée : vente conclue en direct, sans intermédiaire.',
            'decline': 'Offre refusée.',
        }
        messages.success(request, notes[action])
        return redirect('market:offer', pk=offer.pk)
    thread = []
    for item in offer.thread.select_related('author'):
        item.price_text = trade.money(item.price_tnd, prefs['cur']) if item.price_tnd else ''
        thread.append(item)
    product = offer.product
    deal = None
    if offer.offer_price_tnd and product:
        deal = trade.direct_deal(offer.offer_price_tnd, product.category, offer.destination or prefs['dest'])
    return render(request, 'marketplace/offer_detail.html', {
        **prefs,
        'offer': offer,
        'thread': thread,
        'form': form,
        'open_deal': open_deal,
        'can_accept': open_deal and _last_proposer(offer) != request.user.id,
        'price_text': trade.money(offer.offer_price_tnd, prefs['cur']) if offer.offer_price_tnd else '—',
        'total_text': trade.money(offer.total_tnd, prefs['cur']) if offer.total_tnd else '—',
        'route': trade.route(offer.destination, prefs['lang']) if offer.destination else None,
        'deal': deal,
        'is_buyer': offer.buyer_id == request.user.id,
    })


@login_required
def farmer_profile(request, pk):
    farmer = _farmer_or_404(pk)
    is_self = farmer.pk == request.user.id or user_is_admin(request.user)
    form = None
    if not is_self:
        form = FarmerContactForm(request.POST or None, farmer=farmer)
        if request.method == 'POST' and form.is_valid():
            contact = BuyerRequest.objects.create(
                buyer=request.user,
                farmer=farmer,
                product=form.cleaned_data.get('product'),
                quantity=form.cleaned_data.get('quantity'),
                message=form.cleaned_data['message'],
            )
            OfferMessage.objects.create(offer=contact, author=request.user, body=contact.message, event='message')
            messages.success(request, f'Message envoyé à {farmer.username}.')
            return redirect('market:farmer', pk=farmer.pk)
    requests = ()
    if is_self:
        requests = list(
            BuyerRequest.objects.filter(farmer=farmer)
            .select_related('buyer', 'product')
        )
        for item in requests:
            if item.destination:
                info = trade.route(item.destination)
                item.destination_label = f"{info['flag']} {info['city']}"
            else:
                item.destination_label = ''
    return render(request, 'marketplace/farmer_profile.html', {
        'farmer': farmer,
        'products': Product.objects.filter(farmer=farmer).select_related('farmer'),
        'farms': Farm.objects.filter(owner=farmer),
        'form': form,
        'is_self': is_self,
        'requests': requests,
    })


# --------------------------------------------------------------------------
# Simulation : un acheteur étranger joué par l'IA, traduction dans les deux sens
# --------------------------------------------------------------------------

def _sim_key(product):
    return f'kizuna_sim_{product.pk}'


SIM_VERSION = 2


def _sim_state(request, product):
    state = request.session.get(_sim_key(product)) or {}
    if state.get('v') != SIM_VERSION:
        # Ancienne conversation (réponses « démo » de l'IA) : on repart de zéro.
        state = {'v': SIM_VERSION, 'persona': state.get('persona'), 'farmer_lang': state.get('farmer_lang')}
        state = {k: v for k, v in state.items() if v}
    state.setdefault('persona', buyer_ai.DEFAULT_PERSONA)
    state.setdefault('farmer_lang', 'derja')
    if state.get('buyer_lang') not in buyer_ai.BUYER_LANGS:
        state['buyer_lang'] = buyer_ai.PERSONAS[state['persona']]['lang']
    state.setdefault('history', [])
    return state


def _lang_payload(state):
    return {
        'farmer_lang': state['farmer_lang'],
        'farmer_lang_label': buyer_ai.FARMER_LANGS[state['farmer_lang']]['label'],
        'buyer_lang': state['buyer_lang'],
        'buyer_lang_label': buyer_ai.BUYER_LANGS[state['buyer_lang']]['label'],
    }


@login_required
def negotiation_start(request):
    """Entrée du menu : ouvre le chat sur la première récolte en vente."""
    product = (
        Product.objects.exclude(price_tnd=None)
        .exclude(availability=Product.Availability.UNAVAILABLE)
        .order_by('created_at').first()
        or Product.objects.first()
    )
    if product is None:
        messages.info(request, 'Aucune récolte en ligne : publiez-en une pour ouvrir la négociation.')
        return redirect('market:board')
    return redirect('market:simulation', pk=product.pk)


@login_required
def simulation(request, pk):
    product = get_object_or_404(Product.objects.select_related('farmer'), pk=pk)
    state = _sim_state(request, product)
    if 'persona' in request.GET or 'farmer_lang' in request.GET:
        persona_code = buyer_ai.clean_persona(request.GET.get('persona', state['persona']))
        farmer_lang = buyer_ai.clean_farmer_lang(request.GET.get('farmer_lang', state['farmer_lang']))
        if persona_code != state['persona'] or request.GET.get('new'):
            # Autre acheteur (ou « Nouvelle conversation ») : nouvel écran, nouvelle langue, historique vide.
            state = {
                'v': SIM_VERSION, 'persona': persona_code, 'farmer_lang': farmer_lang,
                'buyer_lang': buyer_ai.PERSONAS[persona_code]['lang'], 'history': [],
            }
        else:
            state['farmer_lang'] = farmer_lang  # changer sa langue ne coupe pas la conversation
        request.session[_sim_key(product)] = state
        return redirect('market:simulation', pk=product.pk)
    persona = buyer_ai.PERSONAS[state['persona']]
    return render(request, 'marketplace/simulation.html', {
        'product': product,
        'state': state,
        'persona': persona,
        'personas': buyer_ai.PERSONAS,
        'farmer_langs': buyer_ai.FARMER_LANGS,
        'ai_on': buyer_ai.ai_available(),
        'model': buyer_ai.model_name(),
        'no_key_error': buyer_ai.NO_KEY_ERROR,
        'farmer_lang_label': buyer_ai.FARMER_LANGS[state['farmer_lang']]['label'],
        'buyer_lang_label': buyer_ai.BUYER_LANGS[state['buyer_lang']]['label'],
    })


VOICE_MAX_BYTES = 5 * 1024 * 1024
VOICE_TYPES = {
    'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a', 'audio/mpeg': 'mp3',
    'audio/wav': 'wav', 'audio/x-wav': 'wav', 'audio/aac': 'aac',
}


def _save_voice(upload):
    """Enregistre un message vocal du chat dans MEDIA_ROOT/chat_audio/ et renvoie son URL."""
    kind = (upload.content_type or '').split(';')[0].strip().lower()
    if kind not in VOICE_TYPES:
        raise ValueError('Format audio non pris en charge.')
    if upload.size > VOICE_MAX_BYTES:
        raise ValueError('Message vocal trop long (5 Mo maximum).')
    name = default_storage.save(f'chat_audio/{uuid.uuid4().hex}.{VOICE_TYPES[kind]}', upload)
    return default_storage.url(name)


@login_required
@require_POST
def simulation_say(request, pk):
    """Un message tapé par l'agriculteur (role=farmer) ou l'acheteur (role=buyer), traduit pour l'autre."""
    product = get_object_or_404(Product, pk=pk)
    state = _sim_state(request, product)
    if request.POST.get('reset'):
        state['history'] = []
        request.session[_sim_key(product)] = state
        return JsonResponse({'history': [], 'source': 'reset'})
    role = 'buyer' if request.POST.get('role') == 'buyer' else 'farmer'
    text = (request.POST.get('text') or '').strip()[:1500]
    upload = request.FILES.get('audio')
    if not text and not upload:
        return JsonResponse({'detail': 'Message vide.'}, status=400)
    if len(state['history']) >= 80:
        return JsonResponse({'detail': 'Conversation trop longue : effacez-la pour recommencer.'}, status=400)
    audio_url = ''
    if upload:
        try:
            audio_url = _save_voice(upload)
        except ValueError as exc:
            return JsonResponse({'detail': str(exc)}, status=400)
    if not text:
        # Message vocal sans transcription (navigateur sans reconnaissance vocale) :
        # l'autre côté entend la voix, mais rien n'est traduit.
        turn = {'role': role, 'original': '', 'translated': '', 'fr': '', 'error': '', 'audio': audio_url}
        state['history'] = state['history'] + [turn]
        request.session[_sim_key(product)] = state
        return JsonResponse({'added': [turn], 'error': '', **_lang_payload(state)})
    # Chaque écran suit la langue dans laquelle la personne écrit (ou parle) :
    # si l'acheteur passe à l'anglais, son écran passe à l'anglais, et pareil pour l'agriculteur.
    if role == 'farmer':
        state['farmer_lang'] = buyer_ai.detect_farmer_lang(text, state['farmer_lang'])
        target = buyer_ai.BUYER_LANGS[state['buyer_lang']]['prompt']
    else:
        state['buyer_lang'] = buyer_ai.detect_buyer_lang(text, state['buyer_lang'])
        target = buyer_ai.FARMER_LANGS[state['farmer_lang']]['prompt']
    turn = {'role': role, 'original': text, 'translated': '', 'fr': '', 'error': '', 'audio': audio_url}
    try:
        turn['translated'] = buyer_ai.translate(text, target)
        source_is_french = (state['farmer_lang'] if role == 'farmer' else state['buyer_lang']) == 'fr'
        if request.POST.get('fr') == '1' and target != 'French' and not source_is_french:
            turn['fr'] = buyer_ai.translate(text, 'French')
    except buyer_ai.AIError as exc:
        turn['error'] = str(exc)
    state['history'] = state['history'] + [turn]
    request.session[_sim_key(product)] = state
    return JsonResponse({'added': [turn], 'error': turn['error'], **_lang_payload(state)})


@login_required
def ai_check(request):
    """Diagnostic : la traduction fonctionne-t-elle, et avec quel modèle ?"""
    return JsonResponse({'provider': buyer_ai.provider() or 'aucun', 'results': buyer_ai.diagnose()})
