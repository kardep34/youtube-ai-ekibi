from base64 import b64encode
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
import wave

import pytest
from streamlit.testing.v1 import AppTest

from task_inbox import create_narration, SAMPLE_TEXT


def button(at, label):
    return next(b for b in at.button if b.label == label)


def app():
    at = AppTest.from_file('../app.py')
    at.secrets['PANEL_PASSWORD'] = 'test-password'
    at.secrets['GEMINI_API_KEY'] = 'test-key'
    at.session_state['giris'] = True
    return at


def test_narration_wav_and_duration():
    pcm = b'\x00\x00' * 24000
    client = Mock()
    client.interactions.create.return_value = SimpleNamespace(output_audio=SimpleNamespace(
        data=b64encode(pcm).decode(), mime_type='audio/l16', channels=1, sample_rate=24000
    ))
    data, duration = create_narration(client, 'Merhaba')
    with wave.open(BytesIO(data)) as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 24000)
        assert wav.readframes(wav.getnframes()) == pcm
    assert duration == 1
    options = client.interactions.create.call_args.kwargs
    assert options["response_format"] == {"type": "audio"}
    assert options["generation_config"]["speech_config"] == [{"voice": "Orus"}]
    assert options["store"] is False


@pytest.mark.parametrize("audio", [None, SimpleNamespace(data=None), SimpleNamespace(
    data=b64encode(b"invalid").decode(), mime_type="audio/mp3"
)])
def test_missing_audio(audio):
    client = Mock()
    client.interactions.create.return_value = SimpleNamespace(output_audio=audio)
    client.models.generate_content.return_value = SimpleNamespace(parts=[])
    with pytest.raises(ValueError):
        create_narration(client, "Merhaba")


def test_login_gate():
    at = AppTest.from_file('../app.py').run()
    assert not at.exception
    assert [x.label for x in at.text_input] == ['Panel şifresi']
    assert not at.header


def test_sample_and_existing_panels():
    at = app().run()
    assert not at.exception
    assert '🤖 Beş Bot Tek Panelde' in [h.value for h in at.header]
    assert '🔗 YouTube Resmi Bağlantısı' in [h.value for h in at.header]
    assert button(at, "🚀 YouTube'a Yükle").disabled
    button(at, 'İlk seslendirme görevini getir').click().run()
    assert not at.exception
    assert at.session_state['vortex_task_script'] == SAMPLE_TEXT
    assert not button(at, 'Ses örneği üret').disabled


def test_task_validation_and_isolated_bot_failure():
    at = app().run()
    button(at, 'Görevi çalıştır').click().run()
    assert at.warning
    at.text_input(key='vortex_task_title').set_value('Test')
    at.text_area(key='vortex_task_brief').set_value('Bilim')
    with patch('google.genai.Client') as client:
        client.return_value.models.generate_content.side_effect = [RuntimeError('failed')] + [SimpleNamespace(text='sonuç')] * 4
        button(at, 'Görevi çalıştır').click().run()
    assert not at.exception
    assert len(at.session_state['vortex_task_results'][1]) == 4
    assert len(at.error) == 1


def test_existing_bot_package():
    at = app().run()
    with patch('google.genai.Client') as client:
        client.return_value.models.generate_content.return_value = SimpleNamespace(text='Eski bot sonucu')
        button(at, '🚀 Tüm Ekibi Çalıştır').click().run()
    assert not at.exception
    assert at.session_state['icerik_paketi'].count('Eski bot sonucu') == 5
    button(at, '📋 Bot Sonuçlarını Aktar').click().run()
    assert at.session_state['aktarilan_icerik'] == at.session_state['icerik_paketi']


def test_audio_success_failure_and_logout():
    at = app().run()
    button(at, 'İlk seslendirme görevini getir').click().run()
    with patch('task_inbox.create_narration', return_value=(b'RIFFtest', 1.5)), patch('google.genai.Client'):
        button(at, 'Ses örneği üret').click().run()
    assert not at.exception
    assert at.session_state['vortex_task_audio'][1] == 1.5
    with patch('task_inbox.create_narration', side_effect=RuntimeError('quota')), patch('google.genai.Client'):
        button(at, 'Ses örneği üret').click().run()
    assert not at.exception
    assert 'vortex_task_audio' not in at.session_state
    assert at.error
    button(at, 'Çıkış Yap').click().run()
    assert not at.exception
    assert 'vortex_task_script' not in at.session_state
    assert 'giris' not in at.session_state
