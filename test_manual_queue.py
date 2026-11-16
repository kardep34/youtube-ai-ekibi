from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from task_inbox import parse_task_packet


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
