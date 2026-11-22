import json
import os
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.marketplace import buyer_ai
from apps.marketplace.models import Product

NO_KEY = {'ANTHROPIC_API_KEY': '', 'ANTHROPIC_AUTH_TOKEN': '', 'OPENROUTER_API_KEY': '', 'KIZUNA_AI_FALLBACK_MODELS': ''}


def _reply(content):
    class Resp:
        def read(self):
            return json.dumps({'choices': [{'message': {'content': content}}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return Resp()


class TranslatedChatTests(TestCase):
    def setUp(self):
        buyer_ai.reset_cache()
        self.farmer = User.objects.create_user(username='hedi', password='Kizuna-market-2026', role=User.Role.FARMER)
        self.product = Product.objects.create(
            farmer=self.farmer, name='Huile Chemlali', category='oil', quantity=Decimal('500'),
            unit='litre', origin='Sfax', harvest_date=date(2026, 11, 8), price_tnd=Decimal('16.00'),
        )
        self.client.force_login(self.farmer)
        self.say = reverse('market:simulation_say', args=[self.product.pk])

    def history(self):
        return self.client.session[f'kizuna_sim_{self.product.pk}']['history']

    @mock.patch.dict(os.environ, NO_KEY)
    def test_page_warns_when_no_key_and_messages_carry_an_error(self):
        page = self.client.get(reverse('market:simulation', args=[self.product.pk]))
        self.assertContains(page, 'Traduction désactivée')
        data = self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة'}).json()
        turn = data['added'][0]
        self.assertEqual(turn['translated'], '')
        self.assertIn('OPENROUTER_API_KEY', turn['error'])

    def test_farmer_message_is_translated_into_the_buyer_language_with_no_ai_reply(self):
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'sk-or-test'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('「こんにちは、オイルは有機です。」')) as urlopen:
            data = self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة، الزيت بيو'}).json()
        self.assertEqual(len(data['added']), 1)
        turn = data['added'][0]
        self.assertEqual(turn['role'], 'farmer')
        self.assertEqual(turn['translated'], 'こんにちは、オイルは有機です。')
        body = json.loads(urlopen.call_args.args[0].data)
        self.assertIn('Japanese', body['messages'][1]['content'])
        self.assertEqual(len(self.history()), 1)

    def test_buyer_message_is_translated_into_the_farmer_language(self):
        self.client.get(reverse('market:simulation', args=[self.product.pk]), {'persona': 'tokyo', 'farmer_lang': 'derja_latin'})
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'sk-or-test'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('3aslema, 9adech essoum?')) as urlopen:
            data = self.client.post(self.say, {'role': 'buyer', 'text': 'こんにちは、価格はいくらですか？'}).json()
        self.assertEqual(data['added'][0]['translated'], '3aslema, 9adech essoum?')
        self.assertIn('Latin letters', json.loads(urlopen.call_args.args[0].data)['messages'][1]['content'])

    def test_fallback_model_is_tried_and_errors_never_show_the_key(self):
        import urllib.error
        env = {**NO_KEY, 'OPENROUTER_API_KEY': 'sk-or-secret', 'KIZUNA_AI_MODEL': 'bad/model', 'KIZUNA_AI_FALLBACK_MODELS': 'good/model'}
        calls = []

        def fake(request, timeout=0):
            model = json.loads(request.data)['model']
            calls.append(model)
            if model == 'bad/model':
                raise urllib.error.HTTPError(request.full_url, 404, 'nf', {}, None)
            return _reply('Hello')
        with mock.patch.dict(os.environ, env), mock.patch('urllib.request.urlopen', side_effect=fake):
            self.assertEqual(buyer_ai.translate('عسلامة', 'English'), 'Hello')
        self.assertEqual(calls, ['bad/model', 'good/model'])
        buyer_ai.reset_cache()
        with mock.patch.dict(os.environ, {**env, 'KIZUNA_AI_FALLBACK_MODELS': ''}), \
                mock.patch('urllib.request.urlopen', side_effect=fake):
            data = self.client.post(self.say, {'role': 'farmer', 'text': 'x'}).json()
        self.assertIn('bad/model', data['error'])
        self.assertNotIn('sk-or-secret', data['error'])

    def test_dead_models_are_replaced_by_free_models_listed_by_openrouter(self):
        import urllib.error
        env = {**NO_KEY, 'OPENROUTER_API_KEY': 'k', 'KIZUNA_AI_MODEL': 'qwen/old:free', 'KIZUNA_AI_FALLBACK_MODELS': 'deepseek/paid-now:free'}
        catalog = {'data': [
            {'id': 'qwen/old:free', 'pricing': {'prompt': '0', 'completion': '0'}},
            {'id': 'acme/image-maker:free', 'architecture': {'modality': 'text->image'}},
            {'id': 'acme/paid', 'pricing': {'prompt': '0.000001', 'completion': '0.000002'}},
            {'id': 'zzz/tiny:free', 'context_length': 8000},
            {'id': 'meta-llama/llama-new:free', 'context_length': 128000},
        ]}
        calls = []

        class Listing:
            def read(self):
                return json.dumps(catalog).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake(request, timeout=0):
            if request.data is None:
                return Listing()
            model = json.loads(request.data)['model']
            calls.append(model)
            if model in ('qwen/old:free', 'deepseek/paid-now:free'):
                raise urllib.error.HTTPError(request.full_url, 404, 'nf', {}, None)
            return _reply('Hello')
        with mock.patch.dict(os.environ, env), mock.patch('urllib.request.urlopen', side_effect=fake):
            self.assertEqual(buyer_ai.translate('عسلامة', 'English'), 'Hello')
            self.assertEqual(calls, ['qwen/old:free', 'deepseek/paid-now:free', 'meta-llama/llama-new:free'])
            calls.clear()
            # La traduction suivante part directement sur le modèle qui a marché.
            buyer_ai.translate('باهي', 'English')
            self.assertEqual(calls, ['meta-llama/llama-new:free'])

    def test_choosing_another_buyer_switches_the_buyer_screen(self):
        url = reverse('market:simulation', args=[self.product.pk])
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('こんにちは')):
            self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة'})
        response = self.client.get(url, {'persona': 'london', 'farmer_lang': 'derja'})
        self.assertRedirects(response, url)
        page = self.client.get(url)
        self.assertContains(page, 'Emma Clarke</strong>')
        self.assertContains(page, 'data-buyer-lang="en"')
        self.assertNotContains(page, 'Yuki Tanaka</strong>')
        self.assertEqual(self.history(), [])
        prompts = []

        def fake(request, timeout=0):
            prompts.append(json.loads(request.data)['messages'][1]['content'])
            return _reply('Hello')
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', side_effect=fake):
            self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة'})
        self.assertIn('into English', prompts[0])
        # Changer seulement la langue de l'agriculteur garde la conversation.
        self.client.get(url, {'persona': 'london', 'farmer_lang': 'fr'})
        self.assertEqual(len(self.history()), 1)
        self.client.get(url, {'persona': 'london', 'farmer_lang': 'fr', 'new': '1'})
        self.assertEqual(self.history(), [])

    def test_language_detection(self):
        self.assertEqual(buyer_ai.detect_buyer_lang('Hello, what is your price per litre?', 'ja'), 'en')
        self.assertEqual(buyer_ai.detect_buyer_lang('こんにちは', 'en'), 'ja')
        self.assertEqual(buyer_ai.detect_buyer_lang('Guten Tag, wie viel kostet das Öl?', 'ja'), 'de')
        self.assertEqual(buyer_ai.detect_buyer_lang('Bonjour, quel est le prix ?', 'ja'), 'fr')
        self.assertEqual(buyer_ai.detect_buyer_lang('12000', 'en'), 'en')
        self.assertEqual(buyer_ai.detect_farmer_lang('Hello, the oil is organic and the price is 16 dinars', 'derja'), 'en')
        self.assertEqual(buyer_ai.detect_farmer_lang('3aslema, essoum 16 dinar', 'en'), 'derja_latin')
        self.assertEqual(buyer_ai.detect_farmer_lang('عسلامة', 'en'), 'derja')

    def test_buyer_writing_english_switches_both_directions(self):
        prompts = []

        def fake(request, timeout=0):
            prompts.append(json.loads(request.data)['messages'][1]['content'])
            return _reply('ok')
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', side_effect=fake):
            data = self.client.post(self.say, {'role': 'buyer', 'text': 'Hello, what is your price per litre?'}).json()
            self.assertEqual(data['buyer_lang'], 'en')
            self.assertEqual(data['buyer_lang_label'], 'English')
            self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة، 16 دينار'})
        self.assertIn('Tunisian Arabic', prompts[0])
        self.assertIn('into English', prompts[1])
        page = self.client.get(reverse('market:simulation', args=[self.product.pk]))
        self.assertContains(page, 'data-buyer-lang="en"')

    def test_french_version_only_on_request(self):
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('Bonjour')) as urlopen:
            self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة', 'fr': '0'})
            self.assertEqual(urlopen.call_count, 1)
            data = self.client.post(self.say, {'role': 'farmer', 'text': 'عسلامة', 'fr': '1'}).json()
            self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(data['added'][0]['fr'], 'Bonjour')

    def test_farmer_screen_follows_the_language_the_farmer_writes_in(self):
        self.assertEqual(buyer_ai.detect_farmer_lang('slm', 'fr'), 'derja_latin')
        self.assertEqual(buyer_ai.detect_farmer_lang('Essoum 16 dinar el litre', 'fr'), 'derja_latin')
        self.assertEqual(buyer_ai.detect_farmer_lang('عسلامة', 'fr'), 'derja')
        self.assertEqual(buyer_ai.detect_farmer_lang('Bonjour, le prix est bien', 'derja'), 'fr')
        self.client.get(reverse('market:simulation', args=[self.product.pk]), {'persona': 'london', 'farmer_lang': 'fr'})
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('Hi')):
            data = self.client.post(self.say, {'role': 'farmer', 'text': 'slm'}).json()
        self.assertEqual(data['farmer_lang'], 'derja_latin')
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'k'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('3aslema')) as urlopen:
            self.client.post(self.say, {'role': 'buyer', 'text': 'Hello'})
        self.assertIn('Latin letters', json.loads(urlopen.call_args.args[0].data)['messages'][1]['content'])

    def test_old_demo_conversation_is_cleared(self):
        session = self.client.session
        session[f'kizuna_sim_{self.product.pk}'] = {'persona': 'london', 'farmer_lang': 'fr', 'history': [{'role': 'buyer', 'original': 'demo'}]}
        session.save()
        self.client.get(reverse('market:simulation', args=[self.product.pk]))
        with mock.patch.dict(os.environ, NO_KEY):
            self.client.post(self.say, {'role': 'buyer', 'text': 'Hello'})
        self.assertEqual(len(self.history()), 1)

    def test_ai_check_reports_each_model(self):
        import urllib.error

        def fake(request, timeout=0):
            if json.loads(request.data)['model'] == 'bad/model':
                raise urllib.error.HTTPError(request.full_url, 404, 'nf', {}, None)
            return _reply('Hello, the price is 16 dinars per litre.')
        env = {**NO_KEY, 'OPENROUTER_API_KEY': 'k', 'KIZUNA_AI_MODEL': 'bad/model', 'KIZUNA_AI_FALLBACK_MODELS': 'good/model'}
        with mock.patch.dict(os.environ, env), mock.patch('urllib.request.urlopen', side_effect=fake):
            data = self.client.get(reverse('market:ai_check')).json()
        self.assertEqual([r['ok'] for r in data['results']], [False, True])
        self.assertIn('404', data['results'][0]['detail'])

    def test_empty_message_and_reset(self):
        self.assertEqual(self.client.post(self.say, {'role': 'buyer', 'text': ''}).status_code, 400)
        with mock.patch.dict(os.environ, NO_KEY):
            self.client.post(self.say, {'role': 'buyer', 'text': 'Hello'})
        self.client.post(self.say, {'reset': '1'})
        self.assertEqual(self.history(), [])

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.say, {'text': 'x'}).status_code, 302)


class EntryPointTests(TestCase):
    def test_menu_and_board_lead_to_the_chat(self):
        farmer = User.objects.create_user(username='amel', password='Kizuna-market-2026', role=User.Role.FARMER)
        product = Product.objects.create(
            farmer=farmer, name='Harissa', category='vegetable', quantity=Decimal('10'),
            unit='kg', origin='Nabeul', harvest_date=date(2026, 9, 15), price_tnd=Decimal('22'),
        )
        self.client.force_login(farmer)
        board = self.client.get(reverse('market:board'))
        self.assertContains(board, reverse('market:simulation', args=[product.pk]))
        self.assertContains(board, 'Chat traduit avec un acheteur')
        self.assertRedirects(self.client.get(reverse('market:negotiation')), reverse('market:simulation', args=[product.pk]))


class VoiceMessageTests(TestCase):
    def setUp(self):
        import tempfile
        self.media = tempfile.mkdtemp()
        self.override = self.settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.farmer = User.objects.create_user(username='hedi', password='Kizuna-market-2026', role=User.Role.FARMER)
        self.product = Product.objects.create(
            farmer=self.farmer, name='Huile Chemlali', category='oil', quantity=Decimal('500'),
            unit='litre', origin='Sfax', harvest_date=date(2026, 11, 8), price_tnd=Decimal('16.00'),
        )
        self.client.force_login(self.farmer)
        self.say = reverse('market:simulation_say', args=[self.product.pk])

    def tearDown(self):
        import shutil
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def voice(self, content_type='audio/webm', size=2000):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile('vocal.webm', b'\x1a' * size, content_type=content_type)

    def test_voice_with_transcript_is_saved_and_translated(self):
        with mock.patch.dict(os.environ, {**NO_KEY, 'OPENROUTER_API_KEY': 'sk-or-test'}), \
                mock.patch('urllib.request.urlopen', return_value=_reply('こんにちは')):
            data = self.client.post(self.say, {
                'role': 'farmer', 'text': 'عسلامة', 'audio': self.voice('audio/webm;codecs=opus'),
            }).json()
        turn = data['added'][0]
        self.assertEqual(turn['translated'], 'こんにちは')
        self.assertTrue(turn['audio'].startswith('/media/chat_audio/'))
        self.assertTrue(turn['audio'].endswith('.webm'))
        self.assertTrue(os.path.exists(os.path.join(self.media, 'chat_audio', os.path.basename(turn['audio']))))

    @mock.patch.dict(os.environ, NO_KEY)
    def test_voice_without_transcript_is_kept_untranslated(self):
        data = self.client.post(self.say, {'role': 'buyer', 'text': '', 'audio': self.voice('audio/mp4')}).json()
        turn = data['added'][0]
        self.assertEqual(turn['original'], '')
        self.assertEqual(turn['error'], '')
        self.assertTrue(turn['audio'].endswith('.m4a'))

    def test_non_audio_and_oversized_uploads_are_refused(self):
        bad = self.client.post(self.say, {'role': 'farmer', 'audio': self.voice('text/html')})
        self.assertEqual(bad.status_code, 400)
        big = self.client.post(self.say, {'role': 'farmer', 'audio': self.voice(size=5 * 1024 * 1024 + 1)})
        self.assertEqual(big.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.media, 'chat_audio')))

    def test_chat_page_has_microphone_buttons(self):
        page = self.client.get(reverse('market:simulation', args=[self.product.pk]))
        self.assertContains(page, "btn btn-outline-primary sim-mic", count=2)
        self.assertContains(page, 'data-buyer-lang="ja"')
