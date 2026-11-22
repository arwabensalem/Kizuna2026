"""Chat Bourse KIZUNA : l'agriculteur et l'acheteur écrivent chacun dans leur langue.

Les deux personnes tapent elles-mêmes leurs messages. L'IA sert uniquement à
traduire : ce que l'agriculteur écrit (derja, arabe, français) s'affiche chez
l'acheteur dans la langue de l'acheteur, et inversement.

Fournisseur, choisi par les variables d'environnement (fichier .env à la racine) :
- OPENROUTER_API_KEY : OpenRouter, modèle KIZUNA_AI_MODEL, puis les modèles de
  secours KIZUNA_AI_FALLBACK_MODELS (séparés par des virgules), essayés dans l'ordre ;
- sinon ANTHROPIC_API_KEY : Claude via le SDK Anthropic.
Les clés ne sont jamais écrites dans le code. Si aucune traduction n'aboutit,
l'interface affiche une erreur claire au lieu du texte non traduit.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
OPENROUTER_MODELS_URL = 'https://openrouter.ai/api/v1/models'
# Familles de modèles gratuits essayées en premier quand on cherche un remplaçant.
PREFERRED_FAMILIES = (
    'meta-llama/', 'google/gemma', 'mistralai/', 'qwen/', 'deepseek/', 'openai/gpt-oss',
    'z-ai/', 'moonshotai/', 'nvidia/',
)
MAX_ATTEMPTS = 8
CACHE_SECONDS = 3600
# Mémoire du processus : le dernier modèle qui a marché, les modèles disparus (404),
# et la liste des modèles gratuits lue sur OpenRouter.
_cache = {'good': None, 'dead': {}, 'free': None, 'free_at': 0.0}


def provider():
    if os.environ.get('OPENROUTER_API_KEY'):
        return 'openrouter'
    if os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        return 'anthropic'
    return None


def model_name():
    default = 'claude-opus-5-5' if provider() == 'anthropic' else 'perplexity/pplx-decider-flash-v1.3:free'
    return os.environ.get('KIZUNA_AI_MODEL') or default


def model_chain():
    """Modèle principal puis modèles de secours, sans doublon."""
    chain = [model_name()]
    for name in os.environ.get('KIZUNA_AI_FALLBACK_MODELS', '').split(','):
        name = name.strip()
        if name and name not in chain:
            chain.append(name)
    return chain


class AIError(Exception):
    """La traduction a échoué ; le message est montré à l'écran (jamais la clé)."""


def ai_available():
    return provider() is not None


FARMER_LANGS = {
    'derja': {'label': 'Tunisien (derja, lettres arabes)', 'prompt': 'Tunisian Arabic (Derja), written in Arabic script'},
    'derja_latin': {'label': 'Tunisien (derja en lettres latines, ex. « 3aslema »)', 'prompt': 'Tunisian Arabic (Derja), written in Latin letters with numbers (Arabizi, e.g. "3aslema, chnowa a7walek")'},
    'fr': {'label': 'Français', 'prompt': 'French'},
    'ar': {'label': 'Arabe standard', 'prompt': 'Modern Standard Arabic'},
    'en': {'label': 'Anglais', 'prompt': 'English'},
}

# Langues possibles côté acheteur : l'écran suit la langue dans laquelle il écrit.
BUYER_LANGS = {
    'ja': {'label': '日本語', 'prompt': 'Japanese'},
    'en': {'label': 'English', 'prompt': 'English'},
    'de': {'label': 'Deutsch', 'prompt': 'German'},
    'fr': {'label': 'Français', 'prompt': 'French'},
    'it': {'label': 'Italiano', 'prompt': 'Italian'},
    'es': {'label': 'Español', 'prompt': 'Spanish'},
    'pl': {'label': 'Polski', 'prompt': 'Polish'},
    'ar': {'label': 'العربية', 'prompt': 'Modern Standard Arabic'},
}

PERSONAS = {
    'tokyo': {
        'name': 'Yuki Tanaka', 'flag': '🇯🇵', 'lang': 'ja', 'lang_label': '日本語',
        'company': 'Midori Organic Market, Tokyo',
        'prompt_lang': 'Japanese',
        'profile': (
            'Buyer for a chain of 12 organic grocery stores in Tokyo. Polite, precise, cares about '
            'traceability, JAS organic certification, pesticide residue tests, harvest date, packaging '
            'quality and reliable delivery. Pays fairly for quality but negotiates calmly. Wants to cut '
            'out European middlemen and buy directly from the farm.'
        ),
    },
    'osaka': {
        'name': 'Kenji Sato', 'flag': '🇯🇵', 'lang': 'ja', 'lang_label': '日本語',
        'company': 'Sato Shokuhin (food importer), Osaka',
        'prompt_lang': 'Japanese',
        'profile': (
            'Importer supplying restaurants in Osaka. Business-like, asks about minimum order, '
            'container volumes, shelf life, Incoterms and payment terms. Negotiates harder on price.'
        ),
    },
    'london': {
        'name': 'Emma Clarke', 'flag': '🇬🇧', 'lang': 'en', 'lang_label': 'English',
        'company': 'Clarke & Daughters Fine Foods, London',
        'prompt_lang': 'English',
        'profile': 'Fine-food shop owner. Friendly, loves the farmer’s story, asks about organic and fair trade.',
    },
    'hamburg': {
        'name': 'Jonas Becker', 'flag': '🇩🇪', 'lang': 'de', 'lang_label': 'Deutsch',
        'company': 'Becker Bio-Handel, Hamburg',
        'prompt_lang': 'German',
        'profile': 'Organic wholesaler. Direct, asks about EU organic certificate, EUR.1 and lot sizes.',
    },
}
DEFAULT_PERSONA = 'tokyo'


def clean_persona(code):
    return code if code in PERSONAS else DEFAULT_PERSONA


def clean_farmer_lang(code):
    return code if code in FARMER_LANGS else 'derja'


_ARABIC = re.compile(r'[\u0600-\u06FF]')
_DERJA_WORDS = {
    'slm', 'salam', 'aslema', '3aslema', 'aslama', 'chnoua', 'chnowa', 'chnia', 'chniya', 'behi', 'bahi',
    'barcha', 'yaatik', 'ya3tik', 'ya3tek', 'mte3', 'mta3', 'mte3i', 'mta3i', 'famma', 'fama', 'nheb',
    'n7eb', 'n7ebb', 'essoum', 'soum', 'enti', 'inti', 'ena', 'ana', 'kifech', 'kifeh', '9adech', 'qadech',
    'kadech', 'w', 'yezzi', 'taw', 'tawa', 'lyoum', 'ghodwa', 'mriguel', 'mrigel', 'sa7a', 'saha',
    'choukran', 'labes', 'el', 'dinar', 'dinars', 'ya', 'kima', 'zouz', 'mouch', 'mech', 'barra', 'labess', 'a7wel', 'ahwel', 'nab3athlek', 'zit', 'zitoun',
}
_STOPWORDS = {
    'fr': {
        'bonjour', 'je', 'vous', 'nous', 'le', 'la', 'les', 'est', 'avec', 'pour', 'prix', 'litre', 'merci',
        'oui', 'non', 'notre', 'votre', 'huile', 'qualité', 'combien', 'envoyer', 'bien', 'une', 'des',
        'du', 'et', 'pas', 'mais', 'très', 'salut', 'cette', 'quel', 'quelle', 'récolte', "c'est", 'livraison',
    },
    'en': {
        'hello', 'hi', 'the', 'is', 'are', 'you', 'your', 'we', 'our', 'and', 'price', 'how', 'much',
        'what', 'thanks', 'thank', 'please', 'can', 'would', 'per', 'oil', 'of', 'for', 'with', 'this',
        'that', 'it', 'yes', 'good', 'buy', 'want', 'need', 'do', 'have', 'i', "i'm", 'to', 'my',
        'delivery', 'harvest', 'organic', 'when', 'ok', 'okay', 'deal', 'send', 'sample', 'quality',
    },
    'de': {
        'hallo', 'guten', 'tag', 'ich', 'sie', 'wir', 'und', 'der', 'die', 'das', 'ist', 'nicht', 'mit',
        'für', 'preis', 'danke', 'bitte', 'wie', 'viel', 'kostet', 'ja', 'nein', 'öl', 'liter', 'haben',
    },
    'it': {
        'ciao', 'buongiorno', 'grazie', 'prezzo', 'quanto', 'costa', 'olio', 'il', 'che', 'sono', 'per',
        'con', 'non', 'è', 'di', 'vorrei', 'siamo',
    },
    'es': {
        'hola', 'gracias', 'precio', 'cuánto', 'cuanto', 'cuesta', 'aceite', 'el', 'los', 'que', 'es', 'por',
        'con', 'sí', 'quiero', 'somos', 'buenos', 'días', 'muy', 'y',
    },
    'pl': {
        'dzień', 'dobry', 'cześć', 'dziękuję', 'cena', 'ile', 'kosztuje', 'oliwa', 'jest', 'nie', 'tak',
        'proszę', 'chcemy', 'mamy', 'litr', 'i', 'z', 'na', 'w',
    },
}
_JAPANESE = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
_DERJA_DIGITS = re.compile(r'[a-z][3795][a-z]|^[3795][a-z]|[a-z][3795]$')


def detect_lang(text, current, allowed):
    """Devine la langue du message parmi allowed ; garde current si on ne sait pas."""
    text = text or ''
    if _JAPANESE.search(text) and 'ja' in allowed:
        return 'ja'
    if _ARABIC.search(text):
        if current == 'ar' or 'derja' not in allowed:
            return 'ar' if 'ar' in allowed else current
        return 'derja'
    words = re.findall(r"[a-zà-ÿąćęłńóśźż0-9']+", text.lower())
    if not words:
        return current
    scores = {}
    for lang in allowed:
        if lang == 'derja_latin':
            scores[lang] = sum(1 for w in words if w in _DERJA_WORDS or _DERJA_DIGITS.search(w))
        elif lang in _STOPWORDS:
            scores[lang] = sum(1 for w in words if w in _STOPWORDS[lang])
    if not scores:
        return current
    best = max(scores.values())
    leaders = [lang for lang, score in scores.items() if score == best]
    if best == 0 or len(leaders) > 1:
        return current if current in leaders or best == 0 else leaders[0]
    return leaders[0]


def detect_farmer_lang(text, current='derja'):
    """Devine la langue dans laquelle l'agriculteur écrit, pour lui répondre dans la même."""
    return detect_lang(text, current, FARMER_LANGS)


def detect_buyer_lang(text, current='ja'):
    """Même chose côté acheteur : s'il écrit en anglais, son écran passe en anglais."""
    return detect_lang(text, current, BUYER_LANGS)


SYSTEM_PROMPT = (
    'You are the translator of a chat between a Tunisian farmer and a foreign buyer on KIZUNA, '
    'a marketplace for direct agricultural trade. Translate the message faithfully and naturally '
    'into the requested language. Keep numbers, prices, currencies, units, product names and '
    'Incoterms exactly. The farmer may write Tunisian Arabic (Derja), mixing Arabic, French and '
    'Italian words, in Arabic script or in Latin letters with digits (3 = ع, 7 = ح, 9 = ق, 5 = خ, 2 = ء): '
    'understand it and translate its meaning. Output only the translation: no quotes, no notes, '
    'no explanation, no original text.'
)

NO_KEY_ERROR = 'Aucune clé IA : ajoutez OPENROUTER_API_KEY dans le fichier .env puis relancez le serveur.'


def _clean(text):
    text = (text or '').strip()
    text = re.sub(r'^```[a-z]*\s*|\s*```$', '', text).strip()
    text = re.sub(r'^(translation|traduction|翻訳)\s*[:：]\s*', '', text, flags=re.I).strip()
    if len(text) >= 2 and text[0] in '"«“「' and text[-1] in '"»”」':
        text = text[1:-1].strip()
    return text


def translate(text, target):
    """Traduit text vers la langue décrite par target (en anglais). Lève AIError."""
    if not provider():
        raise AIError(NO_KEY_ERROR)
    prompt = f'Translate this chat message into {target}.\n\nMESSAGE:\n{text}'
    if provider() == 'anthropic':
        result = _call_anthropic(prompt)
    else:
        result = _call_openrouter(prompt)
    result = _clean(result)
    if not result:
        raise AIError('Le modèle a renvoyé une traduction vide.')
    return result


def _call_anthropic(prompt):
    import anthropic

    client = anthropic.Anthropic(timeout=60.0, max_retries=1)
    try:
        response = client.beta.messages.create(
            model=model_name(),
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            output_config={'effort': 'low'},
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            messages=[{'role': 'user', 'content': prompt}],
        )
    except anthropic.APIStatusError as exc:
        raise AIError(f'Claude : erreur HTTP {exc.status_code}') from exc
    except anthropic.APIConnectionError as exc:
        raise AIError('Claude : connexion impossible') from exc
    if response.stop_reason == 'refusal':
        raise AIError('Claude : demande refusée')
    return ''.join(block.text for block in response.content if block.type == 'text')


def _openrouter_once(model, prompt):
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
        'max_tokens': 800,
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {os.environ["OPENROUTER_API_KEY"]}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'http://127.0.0.1:8001',
            'X-Title': 'KIZUNA',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('error', {}).get('message', '')
        except Exception:
            pass
        raise AIError(f'{model} : erreur HTTP {exc.code} {detail}'.strip()) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise AIError('OpenRouter injoignable (connexion Internet ?)') from exc
    if data.get('error'):
        raise AIError(f"{model} : {data['error'].get('message', 'erreur')}")
    try:
        content = data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError(f'{model} : réponse vide') from exc
    if not (content or '').strip():
        raise AIError(f'{model} : réponse vide')
    return content


def reset_cache():
    _cache.update(good=None, dead={}, free=None, free_at=0.0)


def free_models():
    """Modèles gratuits proposés en ce moment par OpenRouter (liste lue sur l'API, gardée 1 h)."""
    now = time.time()
    if _cache['free'] is not None and now - _cache['free_at'] < CACHE_SECONDS:
        return _cache['free']
    request = urllib.request.Request(OPENROUTER_MODELS_URL, headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8')).get('data', [])
    except Exception as exc:  # réseau, JSON : on garde la liste configurée
        log.warning('KIZUNA: liste des modèles OpenRouter indisponible: %s', exc)
        return _cache['free'] or []
    found = []
    for item in data:
        model_id = item.get('id') or ''
        pricing = item.get('pricing') or {}
        free = model_id.endswith(':free') or (
            str(pricing.get('prompt')) in ('0', '0.0') and str(pricing.get('completion')) in ('0', '0.0')
        )
        modality = ((item.get('architecture') or {}).get('modality') or 'text->text')
        if not free or not modality.endswith('->text') or model_id.startswith('openrouter/'):
            continue
        rank = next((i for i, fam in enumerate(PREFERRED_FAMILIES) if model_id.startswith(fam)), len(PREFERRED_FAMILIES))
        found.append((rank, -(item.get('context_length') or 0), model_id))
    _cache['free'] = [model_id for _, _, model_id in sorted(found)]
    _cache['free_at'] = now
    return _cache['free']


def _is_dead(model):
    since = _cache['dead'].get(model)
    return since is not None and time.time() - since < CACHE_SECONDS


def _candidates(include_free=True):
    """Ordre d'essai : dernier modèle qui a marché, modèles du .env encore vivants, puis gratuits du moment."""
    chain = []
    for model in [_cache['good']] + model_chain():
        if model and model not in chain and not _is_dead(model):
            chain.append(model)
    if include_free:
        for model in free_models():
            if model not in chain and not _is_dead(model):
                chain.append(model)
    if not chain:
        chain = model_chain()  # tout est marqué mort : on réessaie quand même pour afficher l'erreur
    return chain[:MAX_ATTEMPTS]


def _call_openrouter(prompt):
    errors = []
    tried = set()
    for include_free in (False, True):
        for model in _candidates(include_free):
            if model in tried:
                continue
            tried.add(model)
            try:
                content = _openrouter_once(model, prompt)
            except AIError as exc:
                log.warning('KIZUNA translation failed: %s', exc)
                errors.append(str(exc))
                if ' 404' in str(exc) or ' 400' in str(exc):
                    _cache['dead'][model] = time.time()  # modèle retiré ou plus gratuit
                if 'injoignable' in str(exc):
                    raise
                continue
            _cache['good'] = model
            return content
    if not errors:
        raise AIError('Aucun modèle OpenRouter disponible.')
    raise AIError(f'{len(tried)} modèles essayés, aucun ne répond. Dernière erreur : {errors[-1]}')


def diagnose():
    """Essaie chaque modèle configuré sur une phrase test ; renvoie le résultat par modèle."""
    if not provider():
        return [{'model': '-', 'ok': False, 'detail': NO_KEY_ERROR}]
    prompt = 'Translate this chat message into English.\n\nMESSAGE:\n3aslema, essoum 16 dinar el litre.'
    if provider() == 'anthropic':
        try:
            return [{'model': model_name(), 'ok': True, 'detail': _clean(_call_anthropic(prompt))}]
        except AIError as exc:
            return [{'model': model_name(), 'ok': False, 'detail': str(exc)}]
    results = []
    for model in model_chain():
        try:
            results.append({'model': model, 'ok': True, 'detail': _clean(_openrouter_once(model, prompt))})
        except AIError as exc:
            results.append({'model': model, 'ok': False, 'detail': str(exc)})
    if not any(r['ok'] for r in results):
        # Aucun modèle du .env ne marche : on cherche parmi les modèles gratuits du moment.
        for model in [m for m in free_models() if m not in model_chain()][:MAX_ATTEMPTS]:
            try:
                detail = _clean(_openrouter_once(model, prompt))
            except AIError as exc:
                results.append({'model': model, 'ok': False, 'detail': str(exc)})
                continue
            _cache['good'] = model
            results.append({'model': model, 'ok': True, 'detail': f'{detail} (trouvé automatiquement : mettez KIZUNA_AI_MODEL={model} dans .env)'})
            break
    return results
