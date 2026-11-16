from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from streamlit.testing.v1 import AppTest

from task_inbox import create_narration, parse_task_packet


def button(at, label):
    return next(b for b in at.button if b.label == label)


@pytest.mark.parametrize("raw", ['{}', '{"title":"t","brief":"b","command":"x"}', '{"title":" ","brief":"b"}'])
def test_rejects_invalid_packets(raw):
    with pytest.raises(ValueError):
        parse_task_packet(raw)


def test_login_and_manual_queue_dedup_and_retry():
    app_path = str(Path(__file__).resolve().with_name("app.py"))
    at = AppTest.from_file(app_path, default_timeout=15)
    at.secrets["PANEL_PASSWORD"] = "test-password"
    at.secrets["GEMINI_API_KEY"] = "test-key"
    at.run()
    assert not any("Panelden çalıştırılan görevler" in h.value for h in at.subheader)
    at.session_state["giris"] = True
    at.run()
    packet = next(t for t in at.text_area if t.label == "Görev paketi (JSON)")
    packet.set_value('{"title":"Kara Delik","brief":"Türkçe belgesel"}')
    button(at, "Oturum kuyruğuna ekle").click().run()
    button(at, "Oturum kuyruğuna ekle").click().run()
    jobs = at.session_state["vortex_task_manual_jobs"]
    assert len(jobs) == 1
    with patch("google.genai.Client") as client:
        synth = client.return_value.models.generate_content
        synth.side_effect = [RuntimeError("robot failed")] + [SimpleNamespace(text="sonuç")] * 4
        button(at, "Kuyruk görevini çalıştır").click().run()
        job = next(iter(jobs.values()))
        assert job["status"] == "Kısmen tamamlandı" and len(job["outputs"]) == 4
        synth.side_effect = None
        synth.return_value = SimpleNamespace(text="yeniden deneme")
        button(at, "Başarısız robotları yeniden çalıştır").click().run()
        assert synth.call_count == 6
    assert job["status"] == "Tamamlandı" and len(job["outputs"]) == 5
    assert not at.exception


def test_missing_interactions_model_falls_back_to_flash_preview():
    client = Mock()
    error = RuntimeError("not found")
    error.status_code = 404
    client.interactions.create.side_effect = error
    client.models.generate_content.return_value = SimpleNamespace(
        parts=[SimpleNamespace(inline_data=SimpleNamespace(
            data=bytes(48000), mime_type="audio/L16;rate=24000"
        ))]
    )
    wav, duration = create_narration(client, "Deneme")
    assert wav.startswith(b"RIFF") and duration == 1
    assert client.models.generate_content.call_args.kwargs["model"] == "gemini-2.5-flash-preview-tts"


def test_legacy_tts_request_and_safe_errors():
    def error(code, status, message):
        exc = RuntimeError("never display raw exceptions")
        exc.status_code = code
        exc.body = {"error": {"message": message, "status": status}}
        return exc

    client = Mock()
    client.interactions.create.side_effect = error(
        404, "NOT_FOUND", "Model not found for API version, secret example-not-for-display"
    )
    client.models.generate_content.side_effect = error(
        400, "INVALID_ARGUMENT", "Invalid JSON payload received; authorization: hidden"
    )
    diagnostics = []
    with pytest.raises(RuntimeError):
        create_narration(client, "Türkçe örnek.", diagnostics)
    request = client.models.generate_content.call_args.kwargs
    assert request["model"] == "gemini-2.5-flash-preview-tts"
    assert request["contents"].endswith("Türkçe örnek.")
    assert request["config"].response_modalities == ["AUDIO"]
    assert request["config"].speech_config.voice_config.prebuilt_voice_config.voice_name == "Orus"
    report = str(diagnostics)
    assert "HTTP 404" in report and "HTTP 400" in report
    assert "NOT_FOUND" in report and "INVALID_ARGUMENT" in report
    assert "example-not-for-display" not in report and "authorization" not in report
