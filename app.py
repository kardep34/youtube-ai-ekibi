
import hmac
import time

import streamlit as st
from google import genai

st.set_page_config(
    page_title="YouTube Yapay Zeka Ekibim",
    page_icon="🎬"
)

st.title("🎬 YouTube Yapay Zeka Ekibim")

# Şifreli giriş
if "giris" not in st.session_state:
    st.session_state["giris"] = False

if not st.session_state["giris"]:
    sifre = st.text_input(
        "Panel şifresi",
        type="password"
    )

    if st.button("Giriş Yap"):
        if hmac.compare_digest(
            sifre,
            st.secrets["PANEL_PASSWORD"]
        ):
            st.session_state["giris"] = True
            st.rerun()
        else:
            st.error("Şifre yanlış!")

    st.stop()

st.success("✅ Panele hoş geldin!")

if st.button("Çıkış Yap"):
    st.session_state["giris"] = False
    st.rerun()

st.divider()
st.header("🤖 Yapay Zeka Ekibim")

botlar = {
    "💡 Fikir Üretici": "10 özgün YouTube video fikri üret.",
    "✍️ Senaryo Yazarı": "Giriş, gelişme ve kapanış içeren ayrıntılı YouTube video senaryosu yaz.",
    "🎯 Başlık Uzmanı": "10 dikkat çekici ve arama dostu YouTube başlığı üret.",
    "📝 Açıklama Uzmanı": "YouTube video açıklaması, etiketler ve hashtagler hazırla.",
    "🎨 Kanal Tasarımcısı": "5 kanal ismi öner. Profil resmi ve kanal kapağı için ayrıntılı tasarım tarifleri hazırla."
}

secim = st.selectbox(
    "Bot seç",
    list(botlar.keys())
)

konu = st.text_area(
    "Kanal veya video konusunu yaz"
)

if st.button("🤖 Botu Çalıştır"):
    if not konu.strip():
        st.warning("Önce bir konu yaz.")
    else:
        try:
            with st.spinner("Yapay zeka çalışıyor..."):
                client = genai.Client(
                    api_key=st.secrets["GEMINI_API_KEY"]
                )

                istem = (
                    "Türkçe yanıt ver.\n"
                    + botlar[secim]
                    + "\nKonu: "
                    + konu
                )

                for deneme in range(3):
                    try:
                        yanit = client.models.generate_content(
                            model="gemini-3.1-flash-lite",
                            contents=istem
                        )
                        break
                    except Exception as hata:
                        if "503" in str(hata) and deneme < 2:
                            time.sleep(10)
                        else:
                            raise

            if yanit.text:
                st.subheader("✨ Botun Cevabı")
                st.markdown(yanit.text)
            else:
                st.warning("Bot boş yanıt verdi.")

        except Exception as hata:
            st.error("Bot çalıştırılamadı.")
            st.code(str(hata))
st.divider()
st.header("🚀 5 Botu Tek Tuşla Çalıştır")

toplu_konu = st.text_area(
    "YouTube video konusunu yaz",
    key="toplu_konu"
)

if st.button("🚀 Tüm Ekibi Çalıştır"):
    if not toplu_konu.strip():
        st.warning("Önce bir konu yaz.")
    else:
        client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"]
        )

        for bot_adi, bot_gorevi in botlar.items():
            with st.spinner(f"{bot_adi} çalışıyor..."):
                try:
                    yanit = client.models.generate_content(
                        model="gemini-3.1-flash-lite",
                        contents=(
                            "Türkçe yanıt ver. "
                            + bot_gorevi
                            + "\nKonu: "
                            + toplu_konu
                        )
                    )

                    st.subheader(bot_adi)
                    if yanit.text:
                        st.markdown(yanit.text)
                    else:
                        st.warning("Boş yanıt geldi.")

                except Exception as hata:
                    st.error(f"{bot_adi} çalıştırılamadı.")
                    st.warning("Bu botu daha sonra tekrar deneyebilirsin.")
