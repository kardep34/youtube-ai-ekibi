"""Contract and real local-render tests; never contact a paid service."""
import json
from pathlib import Path
import shutil
import subprocess
from unittest.mock import Mock

import pytest

from free_media import parse_catalog, public_url
from free_policy import FreeOnlyBlocked, require_free_generation
from free_render import check_rows, duration, probe, render, subtitles


def test_free_policy_fails_before_provider_call():
    from task_inbox import create_narration, voice_client
    client = Mock()
    with pytest.raises(FreeOnlyBlocked):
        create_narration(client, "Deneme")
    client.interactions.create.assert_not_called()
    client.models.generate_content.assert_not_called()
    with pytest.raises(FreeOnlyBlocked):
        voice_client()
    with pytest.raises(FreeOnlyBlocked):
        require_free_generation()


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), 3601])
def test_invalid_scene_duration(seconds):
    with pytest.raises(ValueError):
        check_rows([{"media": "x.png", "seconds": seconds}])


@pytest.mark.parametrize("media", ["../x.png", "/tmp/x.png", "a\\x.png", ""])
def test_scene_names_cannot_escape_uploads(media):
    with pytest.raises(ValueError):
        check_rows([{"media": media, "seconds": 1}])


def test_timed_turkish_subtitles():
    srt = subtitles([
        {"media": "a.png", "seconds": 1.25, "caption": "Türkçe: ışık, çığ, öğüt."},
        {"media": "b.png", "seconds": 2, "caption": "<script>Gök</script>"},
    ])
    assert "00:00:01,250 --> 00:00:03,250" in srt
    assert "Türkçe" in srt and "<script>" not in srt


def test_catalogs_keep_provenance_and_do_not_clear_rights():
    nasa = parse_catalog("NASA", {"collection": {"items": [{"data": [{
        "nasa_id": "a/b", "title": "<b>Moon</b>", "center": "JSC", "media_type": "image",
    }]}]}})[0]
    assert nasa["source_url"].endswith("a%2Fb")
    assert nasa["title"] == "Moon" and not nasa["rights_checked"]
    commons = parse_catalog("Wikimedia Commons", {"query": {"pages": {"1": {
        "title": "File:Moon", "imageinfo": [{"descriptionurl": "https://commons.wikimedia.org/wiki/File:Moon",
        "extmetadata": {"Artist": {"value": "<a>Photographer</a>"},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"}}}],
    }}}})[0]
    assert commons["creator"] == "Photographer"
    assert commons["license"] == "CC BY-SA 4.0" and not commons["rights_checked"]
    assert public_url("javascript:alert(1)") == ""


def test_project_round_trip_and_rejection():
    from free_studio import load_project
    project = {"version": 1, "topic": "Farklı konu", "script": "Merhaba", "format": "Yatay 16:9",
               "scenes": [{"media": "a.png", "seconds": 15, "caption": "Merhaba"}], "sources": []}
    assert load_project(json.dumps(project)) == project
    project["scenes"][0]["seconds"] = float("nan")
    with pytest.raises(ValueError):
        load_project(json.dumps(project))


def test_shared_team_brief_uses_each_projects_duration_voice_and_script():
    from free_studio import team_brief
    brief = team_brief("Tarih", "Onaylı farklı anlatım", "Yatay 16:9", [
        {"media": "x.png", "seconds": 173.5, "caption": ""}])
    assert "173.50" in brief and "Onaylı farklı anlatım" in brief and "Yatay 16:9" in brief
    assert "her projede aynı sesi dayatma" in brief
    assert "düşük kaliteli" in brief


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
@pytest.mark.parametrize("format_name,dimensions", [("Dikey 9:16", (540, 960)), ("Yatay 16:9", (960, 540)), ("Kare 1:1", (540, 540))])
def test_real_render_with_subtitles_and_audio(tmp_path, format_name, dimensions):
    # A two-pixel PPM avoids adding an imaging dependency to the application.
    source = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=128x128",
                    "-frames:v", "1", "-threads", "1", str(source)], check=True)
    narration = tmp_path / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    str(narration)], check=True)
    rows = [{"media": "frame.png", "seconds": 1, "caption": "Türkçe ilk sahne"},
            {"media": "frame.png", "seconds": 1, "caption": "İkinci sahne"}]
    output, srt = render(rows, {"frame.png": source}, tmp_path / "result", narration=narration,
                         music=narration, format_name=format_name)
    metadata = probe(output)
    video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == dimensions
    assert any(s["codec_type"] == "audio" for s in metadata["streams"])
    assert abs(duration(output) - 2) < 0.15
    assert "İkinci sahne" in srt.read_text()
    with pytest.raises(ValueError, match="uyuşmuyor"):
        render(rows[:1], {"frame.png": source}, tmp_path / "bad", narration=narration)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_full_resolution_silent_clip_and_report(tmp_path):
    from free_render import quality_report
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=128x128:d=0.25",
                    "-threads", "1", str(clip)], check=True)
    output, _ = render([{"media": "clip.mp4", "seconds": 0.5}], {"clip.mp4": clip},
                       tmp_path / "result", preview=False, burn_subtitles=False)
    report = quality_report(output)
    assert (report["width"], report["height"]) == (1080, 1920)
    assert report["audio_codec"] is None
    assert not report["professional_quality_certified"]


def test_free_ui_loads_and_prevents_cloud_generation():
    from streamlit.testing.v1 import AppTest
    from unittest.mock import patch
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=15)
    at.secrets["PANEL_PASSWORD"] = "test"
    at.session_state["giris"] = True
    with patch("google.genai.Client") as client:
        at.run()
        assert not at.exception
        assert "🎬 Ücretsiz Üretim Stüdyosu" in [h.value for h in at.header]
        next(b for b in at.button if b.label == "🚀 Tüm Ekibi Çalıştır").click().run()
        assert not at.exception
        client.assert_not_called()
        assert any("Yalnızca ücretsiz mod" in e.value for e in at.error)


def test_multiple_catalog_results_render_without_duplicate_widgets():
    from streamlit.testing.v1 import AppTest
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=15)
    at.secrets["PANEL_PASSWORD"] = "test"
    at.session_state["giris"] = True
    at.session_state["vortex_free_search"] = parse_catalog("NASA", {"collection": {"items": [
        {"data": [{"nasa_id": "one", "title": "One"}]},
        {"data": [{"nasa_id": "two", "title": "Two"}]},
    ]}})
    at.run()
    assert not at.exception
    next(b for b in at.button if b.label == "Proje kaynaklarına ekle").click().run()
    assert not at.exception
    assert len(at.session_state["vortex_free_sources"]) == 1
