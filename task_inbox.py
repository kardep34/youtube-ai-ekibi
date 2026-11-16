from base64 import b64decode
from hashlib import sha256
from io import BytesIO
import json
import wave

import streamlit as st


SAMPLE_TITLE = "Kara Deliğe Düşersen Ne Olur?"
SAMPLE_TEXT = "Bir kara deliğe düşseydin ne olurdu? Yaklaştıkça, kara deliğe daha yakın olan ayakların başından daha güçlü çekilirdi. Bu fark seni uzatmaya başlardı. Ama kara delik çok büyükse, olay ufkunu geçtiğin an hiçbir şey hissetmeyebilirsin. Yine de o sınırdan sonra geri dönüş yok. Oradan gönderdiğin bir ışık sinyali bile dışarı ulaşamaz."


def create_narration(client, text):
    response = client.interactions.create(
        model="gemini-3.1-flash-tts-preview",
        input=(
            "Read only the transcript in natural Turkish with a deep adult male "
            "documentary voice. Use brief pauses and aim for 30 seconds.\n\n"
            f"TRANSCRIPT:\n{text}"
        ),
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": "Orus"}]},
        store=False,
    )
    audio = response.output_audio
    if not audio or not audio.data:
        raise ValueError("Ses servisi bir ses örneği döndürmedi.")

    data = b64decode(audio.data, validate=True)
    if data.startswith(b"RIFF"):
        with wave.open(BytesIO(data), "rb") as output:
            return data, output.getnframes() / output.getframerate()
    mime = (audio.mime_type or "").lower().split(";", 1)[0]
    if mime != "audio/l16" or not data or len(data) % 2:
        raise ValueError("Gemini desteklenmeyen bir ses biçimi döndürdü.")

    channels = audio.channels or 1
    sample_rate = audio.sample_rate or 24000
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
    if st.button("Ses örneği üret", disabled=not script.strip()):
        st.session_state.pop("vortex_task_audio", None)
        try:
            with st.spinner("Ses örneği hazırlanıyor…"):
                st.session_state["vortex_task_audio"] = create_narration(make_client(), script)
        except ValueError:
            st.error("Gemini yanıtında kullanılabilir ses verisi bulunamadı.")
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            messages = {
                400: "Gemini ses isteğini geçersiz buldu.",
                401: "Gemini kimlik doğrulaması başarısız.",
                403: "Gemini projesinin bu ses modeline erişimi yok.",
                404: "Ses modeli bu Gemini projesinde bulunamadı.",
                429: "Gemini ses kotası veya istek sınırı aşıldı.",
                503: "Gemini ses hizmeti geçici olarak kullanılamıyor.",
            }
            detail = messages.get(status, "Ses üretimi tamamlanamadı.")
            st.error(f"{detail} (HTTP {status})" if type(status) is int and 400 <= status <= 599 else detail)

    audio = st.session_state.get("vortex_task_audio")
    if audio:
        data, duration = audio
        st.audio(data, format="audio/wav")
        st.caption(f"Ölçülen süre: {duration:.1f} saniye")
        st.download_button("WAV indir", data, "vortex360-ses-ornegi.wav", "audio/wav")

    render_manual_queue(bot_roles, run_bot, make_client)
