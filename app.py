

import streamlit as st
import hmac
from google import genai

st.set_page_config(page_title="YouTube Yapay Zeka Ekibim", page_icon="🎬")

st.title("🎬 YouTube Yapay Zeka Ekibim")

# Şifreli giriş
if "giris" not in st.session_state:
    st.session_state["giris"] = False

if not st.session_state["giris"]:
    sifre = st.text_input("Panel şifresi", type="password")

    if st.button("Giriş Yap"):
        if hmac.compare_digest(
            sifre, st.secrets["PANEL_PASSWORD"]
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
    "💡 Fikir Üretici": "YouTube için 10 özgün video fikri üret.",
    "✍️ Senaryo Yazarı": "YouTube videosu için giriş, gelişme ve kapanış içeren ayrıntılı bir senaryo yaz.",
    "🎯 Başlık Uzmanı": "YouTube için 10 dikkat çekici, doğal ve arama dostu başlık üret.",
    "📝 Açıklama Uzmanı": "YouTube video açıklaması, etiketler ve hashtagler hazırla.",
    "🎨 Kanal Tasarımcısı": "5 kanal ismi öner. Profil resmi ve kanal kapağı için ayrıntılı görsel tasarım tarifleri hazırla."
}

secim = st.selectbox("Bot seç", list(botlar.keys()))
konu = st.text_area("Kanal veya video konusunu yaz")

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
                    "Türkçe yanıt ver. "
                    + botlar[secim]
                    + "\nKonu: "
                    + konu
                )

                yanit = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=istem
                )

            if yanit.text:
                st.subheader("✨ Botun Cevabı")
                st.markdown(yanit.text)
            else:
                st.warning("Bot boş yanıt verdi.")

        except Exception as hata:
            st.error("Bot çalıştırılamadı.")
            st.code(str(hata))


