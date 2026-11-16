from io import BytesIO
import wave

import streamlit as st
from google.genai import types


SAMPLE_TITLE = "Kara Deliğe Düşersen Ne Olur?"
SAMPLE_TEXT = "Bir kara deliğe düşseydin ne olurdu? Yaklaştıkça, kara deliğe daha yakın olan ayakların başından daha güçlü çekilirdi. Bu fark seni uzatmaya başlardı. Ama kara delik çok büyükse, olay ufkunu geçtiğin an hiçbir şey hissetmeyebilirsin. Yine de o sınırdan sonra geri dönüş yok. Oradan gönderdiğin bir ışık sinyali bile dışarı ulaşamaz."


def create_narration(client, text):
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents="Metni Türkçe, sakin ve merak uyandıran bir belgesel tonuyla oku. "
        "Yalnızca aşağıdaki metni seslendir, yaklaşık 30 saniye hedefle.\n\n" + text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
        ),
    )
    for candidate in response.candidates or []:
        for part in getattr(candidate.content, "parts", None) or []:
            audio = part.inline_data
            if audio and audio.data and (audio.mime_type or "").startswith("audio/"):
                with BytesIO() as buffer:
                    with wave.open(buffer, "wb") as output:
                        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                        output.writeframes(audio.data)
                    return buffer.getvalue(), len(audio.data) / 48000
    raise ValueError("Ses servisi bir ses örneği döndürmedi.")


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
        except Exception:
            st.error("Ses üretilemedi. Gemini ses modeli erişimini ve kotasını kontrol edin.")

    audio = st.session_state.get("vortex_task_audio")
    if audio:
        data, duration = audio
        st.audio(data, format="audio/wav")
        st.caption(f"Ölçülen süre: {duration:.1f} saniye")
        st.download_button("WAV indir", data, "vortex360-ses-ornegi.wav", "audio/wav")
