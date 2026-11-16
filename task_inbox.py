from base64 import b64decode
from hashlib import sha256
from importlib.metadata import version
from io import BytesIO
import json
import re
import wave

import streamlit as st
from google import genai
from google.genai import types


SAMPLE_TITLE = "Kara Deliğe Düşersen Ne Olur?"
SAMPLE_TEXT = (
    "Bir an için hayal et... Uzayın derinliklerindesin. Karşında, ışığın bile kaçamadığı devasa bir kara delik var. "
    "Geri dönmek istiyorsun. Ama artık çok geç olabilir. Çünkü birazdan, evrenin en korkutucu sınırını geçeceksin. "
    "Ve o sınırın ötesinden... geri dönüş yok."
)
VOICE_DIRECTION = (
    "Doğal Türkiye Türkçesiyle, tok ve güçlü bir yetişkin erkek sesiyle anlat. Derin rezonans kullan. "
    "Sakin ama otoriter, sinematik belgesel tonunda oku. Bağırma, robotik okuma yapma. "
    "Üç noktalarda kısa, doğal duraklamalar yap. Yalnızca aşağıdaki metni seslendir."
)
TTS_VOICES = (
    "Algenib", "Orus", "Charon", "Alnilam", "Gacrux", "Schedar", "Zephyr", "Puck", "Kore", "Fenrir",
    "Leda", "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina",
    "Erinome", "Rasalgethi", "Laomedeia", "Achernar", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
)
VOICE_API_VERSION = "v1beta"
VOICE_MODELS = ("gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts")


def gemini_http_status(exc):
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status if type(status) is int and 400 <= status <= 599 else None


def safe_gemini_error(exc):
    """Show only reviewed provider signals, never the raw response or request."""
    status = gemini_http_status(exc)
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        body = getattr(exc, "response_json", None)
    if not isinstance(body, dict):
        body = getattr(exc, "details", None)
    if not isinstance(body, dict):
        body = {}
    provider = body.get("error", body)
    if not isinstance(provider, dict):
        provider = {}
    message = str(provider.get("message") or getattr(exc, "message", "")).lower()
    signals = (
        (("user location is not supported", "location is not supported"), "Proje veya sunucu bölgesi Gemini API için desteklenmiyor."),
        (("api key not valid", "api key invalid"), "Gemini API anahtarını geçersiz buldu."),
        (("billing", "paid tier"), "Sağlayıcı yanıtı faturalandırma veya ücretli katman koşuluna işaret ediyor."),
        (("not found for api version",), "Model bu API sürümünde bulunamadı veya bu yöntemi desteklemiyor."),
        (("not supported for generatecontent", "does not support generatecontent"), "Model GenerateContent yöntemini desteklemiyor."),
        (("not supported for interactions", "does not support interactions"), "Model Interactions yöntemini desteklemiyor."),
        (("only supports text output", "requested modality", "response_modalities"), "İstenen ses çıktı biçimi reddedildi."),
        (("voice is not supported", "invalid voice", "unsupported voice", "voice name"), "Seçilen ses yapılandırması reddedildi."),
        (("invalid json payload", "unknown name", "unknown field"), "Gönderilen istek alanlarından biri API şemasıyla uyuşmuyor."),
        (("quota", "rate limit"), "Sağlayıcı kota veya istek sınırı bildirdi."),
        (("requested entity was not found",), "Sağlayıcı hedef kaynağı bulamadı; hangi kaynağın eksik olduğunu belirtmedi."),
    )
    if status is None and isinstance(exc, ValueError):
        return "Gemini yanıtında kullanılabilir ses verisi bulunamadı."
    parts = [f"HTTP {status}" if status else "HTTP kodu yok"]
    known_status = {"INVALID_ARGUMENT", "NOT_FOUND", "PERMISSION_DENIED", "UNAUTHENTICATED",
                    "RESOURCE_EXHAUSTED", "UNAVAILABLE", "FAILED_PRECONDITION", "INTERNAL"}
    provider_status = provider.get("status") or getattr(exc, "status", None)
    if isinstance(provider_status, str) and provider_status in known_status:
        parts.append(provider_status)
    reasons = {"API_KEY_INVALID", "API_KEY_SERVICE_BLOCKED", "SERVICE_DISABLED",
               "BILLING_DISABLED", "RATE_LIMIT_EXCEEDED", "CONSUMER_INVALID",
               "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "LOCATION_POLICY_VIOLATED"}
    for detail in provider.get("details") or []:
        if isinstance(detail, dict) and detail.get("reason") in reasons:
            parts.append(detail["reason"])
    if status == 400:
        fields = {
            "contents": "contents", "generationconfig": "generationConfig",
            "responsemodalities": "responseModalities", "speechconfig": "speechConfig",
            "voiceconfig": "voiceConfig", "prebuiltvoiceconfig": "prebuiltVoiceConfig",
            "voicename": "voiceName",
        }
        match = re.search(r'unknown (?:name|field)\s+["\']([a-z_]+)["\']', message)
        field = fields.get(match.group(1).replace("_", "")) if match else None
        if field:
            parts.append(f"Reddedilen alan: {field}")
    parts.append(next((description for phrases, description in signals
                       if any(phrase in message for phrase in phrases)),
                      "Sağlayıcıdan gösterilebilir özel hata nedeni alınamadı."))
    return " · ".join(dict.fromkeys(parts))


def voice_client():
    return genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"],
        vertexai=False,
        http_options=types.HttpOptions(api_version=VOICE_API_VERSION),
    )


def voice_model_report(default_client, tts_client):
    api_options = default_client._api_client._http_options
    default_version = api_options.api_version
    if default_version not in ("v1", "v1beta", "v1alpha", "v1beta1"):
        default_version = "belirlenemedi"
    report = [
        f"Google GenAI SDK {version('google-genai')} · Varsayılan API: {default_version}"
        f" · Seslendirme API: {VOICE_API_VERSION}",
    ]
    for api_version, client in {default_version: default_client, VOICE_API_VERSION: tts_client}.items():
        try:
            models = list(client.models.list())
            voice_models = sorted({
                model.name.removeprefix("models/")
                for model in models
                if model.name and "tts" in model.name.lower()
                and model.name.replace("/", "").replace(".", "").replace("-", "").isalnum()
            })
            names = ", ".join(voice_models) if voice_models else "yok"
            report.append(f"{api_version} · {len(models)} model · TTS: {names}")
        except Exception as exc:
            report.append(f"{api_version} · Model listesi: {safe_gemini_error(exc)}")
    for model in VOICE_MODELS:
        try:
            tts_client.models.get(model=model)
            report.append(f"{VOICE_API_VERSION} · {model} · Model bilgisi alındı.")
        except Exception as exc:
            report.append(f"{VOICE_API_VERSION} · {model} · {safe_gemini_error(exc)}")
    return "\n".join(report)


def create_narration(client, text, diagnostics=None, *, voice="Orus"):
    if voice not in TTS_VOICES:
        raise ValueError("Desteklenmeyen ses seçimi.")
    prompt = f"{VOICE_DIRECTION}\n\nSESLENDİRİLECEK METİN:\n{text}"
    try:
        response = client.interactions.create(
            model=VOICE_MODELS[0], input=prompt, response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]}, store=False,
        )
        audio = response.output_audio
        if not audio or not audio.data:
            raise ValueError("Ses servisi bir ses örneği döndürmedi.")
        return narration_wav(
            b64decode(audio.data, validate=True), audio.mime_type,
            getattr(audio, "channels", None), getattr(audio, "sample_rate", None),
        )
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.append(("Gemini 3.1 Flash TTS · Interactions", safe_gemini_error(exc)))
    try:
        result = client.models.generate_content(
            model=VOICE_MODELS[1], contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                http_options=types.HttpOptions(extra_body={
                    "generationConfig": {"speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                    }}
                }),
            ),
        )
        for part in result.parts or []:
            audio = part.inline_data
            if audio and audio.data and (audio.mime_type or "").lower().startswith("audio/"):
                return narration_wav(audio.data, audio.mime_type)
        raise ValueError("Ses servisi bir ses örneği döndürmedi.")
    except Exception as exc:
        if diagnostics is not None:
            diagnostics.append(("Gemini 2.5 Flash Preview TTS · GenerateContent", safe_gemini_error(exc)))
        raise


def narration_wav(data, mime_type, channels=None, sample_rate=None):
    if data.startswith(b"RIFF"):
        with wave.open(BytesIO(data), "rb") as output:
            return data, output.getnframes() / output.getframerate()
    mime = (mime_type or "").lower().split(";", 1)[0]
    if mime != "audio/l16" or not data or len(data) % 2:
        raise ValueError("Gemini desteklenmeyen bir ses biçimi döndürdü.")
    channels = channels or 1
    sample_rate = sample_rate or 24000
    with BytesIO() as buffer:
        with wave.open(buffer, "wb") as output:
            output.setparams((channels, 2, sample_rate, 0, "NONE", "not compressed"))
            output.writeframes(data)
        return buffer.getvalue(), len(data) / (2 * channels * sample_rate)


def parse_task_packet(raw):
    if len(raw) > 40000:
        raise ValueError("Görev paketi çok büyük.")
    packet = json.loads(raw)
    if not isinstance(packet, dict) or set(packet) != {"title", "brief"}:
        raise ValueError("Paket yalnızca title ve brief alanlarını içermeli.")
    title, brief = packet["title"], packet["brief"]
    if not isinstance(title, str) or not isinstance(brief, str):
        raise ValueError("Görev başlığı ve açıklaması metin olmalı.")
    title, brief = title.strip(), brief.strip()
    if not (0 < len(title) <= 200 and 0 < len(brief) <= 6000):
        raise ValueError("Görev başlığı veya açıklaması boş ya da çok uzun.")
    return title, brief


def render_manual_queue(bot_roles, run_bot, make_client):
    st.subheader("Panelden çalıştırılan görevler")
    st.caption("ChatGPT görev paketini buraya yapıştır. Görevler bu oturumda tutulur ve düğmeyle çalıştırılır.")
    jobs = st.session_state.setdefault("vortex_task_manual_jobs", {})
    with st.form("vortex_task_manual_packet"):
        raw = st.text_area("Görev paketi (JSON)", max_chars=40000)
        roles = st.multiselect("Kuyruk robotları", list(bot_roles), default=list(bot_roles))
        add = st.form_submit_button("Oturum kuyruğuna ekle")
    if add:
        try:
            title, brief = parse_task_packet(raw)
            if not roles:
                raise ValueError("En az bir robot seç.")
        except (ValueError, TypeError):
            st.warning('Geçerli bir {"title": "...", "brief": "..."} paketi ve robot seçimi gerekli.')
        else:
            roles = [name for name in bot_roles if name in roles]
            encoded = json.dumps([title, brief, roles], ensure_ascii=False)
            task_id = sha256(encoded.encode()).hexdigest()
            if task_id in jobs:
                st.info("Bu görev zaten oturum kuyruğunda.")
            elif len(jobs) >= 20:
                st.warning("Bu oturumun görev sınırına ulaşıldı. Sonuçları indirin.")
            else:
                jobs[task_id] = {
                    "title": title, "brief": brief, "roles": roles,
                    "outputs": {}, "failed": [], "status": "Bekliyor",
                }
    for task_id, job in jobs.items():
        with st.expander(f"{job['title']} · {job['status']}"):
            st.text(job["brief"])
            ready = job["status"] in {"Bekliyor", "Başarısız", "Kısmen tamamlandı"}
            label = "Kuyruk görevini çalıştır" if job["status"] == "Bekliyor" else "Başarısız robotları yeniden çalıştır"
            if ready and st.button(label, key=f"vortex_task_run_{task_id}"):
                job["status"] = "Çalışıyor"
                pending = [role for role in job["roles"] if role not in job["outputs"]]
                try:
                    with st.spinner("Görev çalışıyor…"):
                        client = make_client()
                        for role in pending:
                            try:
                                result = run_bot(client, bot_roles[role], f"{job['title']}\n\n{job['brief']}")
                                job["outputs"][role] = result
                            except Exception:
                                continue
                except Exception:
                    pass
                finally:
                    job["failed"] = [role for role in pending if role not in job["outputs"]]
                    job["status"] = (
                        "Tamamlandı" if not job["failed"] else
                        "Kısmen tamamlandı" if job["outputs"] else "Başarısız"
                    )
                st.rerun()
            for role, result in job["outputs"].items():
                st.write(role)
                st.text(result)
            if job["failed"]:
                st.warning("Yanıt alınamayan robotlar: " + ", ".join(job["failed"]))
    if jobs:
        st.download_button(
            "Oturum görevlerini indir",
            json.dumps(list(jobs.values()), ensure_ascii=False, indent=2),
            "vortex360-gorevler.json", "application/json",
        )


def render_voice_studio():
    st.subheader("Ses Karşılaştırma Stüdyosu")
    script = st.text_area(
        "Ortak Türkçe belgesel metni", value=SAMPLE_TEXT, max_chars=2500,
        key="vortex_studio_script",
    ).strip()
    selected = st.multiselect(
        "Karşılaştırılacak Gemini sesleri", TTS_VOICES,
        default=("Algenib", "Alnilam", "Gacrux", "Charon", "Rasalgethi"),
        max_selections=5, key="vortex_studio_voices",
    )
    generate = st.button(
        "Seçili sesleri üret", key="vortex_studio_generate",
        disabled=not script or not selected or len(selected) > 5,
    )
    if not script:
        return

    studio = st.session_state.setdefault("vortex_voice_studio", {})
    script_id = sha256(script.encode("utf-8")).hexdigest()
    batch = studio.get(script_id)
    if generate and len(selected) <= 5:
        batch = studio.setdefault(script_id, {"clips": {}, "errors": {}, "favorite": None})
        for voice in selected:
            if voice in batch["clips"]:
                continue
            diagnostics = []
            try:
                with st.spinner(f"{voice} hazırlanıyor…"), voice_client() as client:
                    recording = create_narration(client, script, diagnostics, voice=voice)
                batch["clips"][voice] = recording
                batch["errors"].pop(voice, None)
            except Exception as exc:
                batch["errors"][voice] = diagnostics or [("Gemini", safe_gemini_error(exc))]

    if not batch:
        return
    voices = dict.fromkeys([*selected, *batch["clips"], *batch["errors"]])
    for voice in voices:
        key_suffix = f"{script_id}_{voice}"
        with st.container(border=True):
            st.write(voice)
            if voice in batch["clips"]:
                data, duration = batch["clips"][voice]
                st.audio(data, format="audio/wav")
                st.caption(f"{duration:.1f} saniye")
                st.download_button(
                    "WAV indir", data, f"vortex360-{voice.lower()}.wav", "audio/wav",
                    key=f"vortex_studio_download_{key_suffix}",
                )
                favorite = batch["favorite"] == voice
                st.button(
                    "★ Favori" if favorite else "Favori seç", disabled=favorite,
                    key=f"vortex_studio_favorite_{key_suffix}",
                    on_click=batch.__setitem__, args=("favorite", voice),
                )
            elif voice in batch["errors"]:
                for route, detail in batch["errors"][voice]:
                    st.error(f"{route}: {detail}")
            else:
                st.caption("Henüz kayıt yok.")

def render_task_inbox(bot_roles, run_bot, make_client):
    st.header("📥 ChatGPT Görev Kutusu")
    if st.button("İlk seslendirme görevini getir"):
        st.session_state["vortex_task_title"] = SAMPLE_TITLE
        st.session_state["vortex_task_brief"] = (
            "30 saniyelik Türkçe bilim belgeseli açılışı. "
            "Olay ufkunu ve farklı uzaklıklardaki çekim farkını sade bir dille anlat."
        )
        st.session_state["vortex_task_script"] = SAMPLE_TEXT
        st.session_state.pop("vortex_task_audio", None)
    with st.form("vortex_task_inbox"):
        title = st.text_input("Görev başlığı", max_chars=200, key="vortex_task_title")
        brief = st.text_area("ChatGPT görev metni", max_chars=6000, key="vortex_task_brief")
        selected = st.multiselect(
            "Robotlar", list(bot_roles), default=list(bot_roles), key="vortex_task_roles"
        )
        submitted = st.form_submit_button("Görevi çalıştır")
    if submitted:
        if not title.strip() or not brief.strip() or not selected:
            st.warning("Başlık, görev metni ve en az bir robot seçimi gerekli.")
        else:
            results = {}
            try:
                client = make_client()
                for role in selected:
                    try:
                        with st.spinner(f"{role} çalışıyor…"):
                            results[role] = run_bot(
                                client, bot_roles[role], f"{title.strip()}\n\n{brief.strip()}"
                            )
                    except Exception:
                        st.error(f"{role} görevi tamamlayamadı.")
            except Exception:
                st.error("Gemini bağlantısı kurulamadı.")
            st.session_state["vortex_task_results"] = (title, results)
    completed = st.session_state.get("vortex_task_results")
    if completed and completed[1]:
        st.subheader(completed[0])
        for role, output in completed[1].items():
            with st.expander(role):
                st.text(output)
    script = st.text_area("Seslendirilecek Türkçe metin", max_chars=2500, key="vortex_task_script")
    voice = st.selectbox("Gemini sesi", TTS_VOICES, key="vortex_task_voice")
    if st.button("Hesaptaki ses modellerini kontrol et"):
        try:
            with make_client() as default_client, voice_client() as tts_client:
                st.session_state["vortex_task_voice_models"] = voice_model_report(default_client, tts_client)
        except Exception as exc:
            st.session_state["vortex_task_voice_models"] = safe_gemini_error(exc)
    if st.session_state.get("vortex_task_voice_models"):
        st.text(st.session_state["vortex_task_voice_models"])
    if st.button("Ses örneği üret", disabled=not script.strip()):
        st.session_state.pop("vortex_task_audio", None)
        diagnostics = []
        st.session_state["vortex_task_voice_diagnostics"] = diagnostics
        try:
            with st.spinner("Ses örneği hazırlanıyor…"), voice_client() as client:
                st.session_state["vortex_task_audio"] = create_narration(client, script, diagnostics, voice=voice)
                st.session_state["vortex_task_audio_voice"] = voice
        except ValueError:
            st.error("Gemini yanıtında kullanılabilir ses verisi bulunamadı.")
        except Exception as exc:
            st.error(safe_gemini_error(exc))
    for route, detail in st.session_state.get("vortex_task_voice_diagnostics", []):
        st.text(f"{route}: {detail}")
    audio = st.session_state.get("vortex_task_audio")
    if audio:
        data, duration = audio
        st.audio(data, format="audio/wav")
        recorded_voice = st.session_state.get("vortex_task_audio_voice")
        voice_label = f"Ses: {recorded_voice} · " if recorded_voice else ""
        st.caption(f"{voice_label}Ölçülen süre: {duration:.1f} saniye")
        st.download_button("WAV indir", data, "vortex360-ses-ornegi.wav", "audio/wav")
    render_voice_studio()
    render_manual_queue(bot_roles, run_bot, make_client)
