
import streamlit as st

st.set_page_config(
    page_title="YouTube AI Ekibim",
    page_icon="🎬"
)

st.title("🎬 YouTube AI Ekibim")
st.success("Bot yönetim paneli hazır!")

bot = st.selectbox(
    "Hangi botu çalıştırmak istiyorsun?",
    [
        "🏗️ Kanal İnşa Botu",
        "📊 Analiz Botu",
        "🎥 İçerik Üretim Botu",
        "🤖 Yönetici Bot"
    ]
)

st.write("Seçilen bot:", bot)
st.info("Bot özelliklerini sırayla ekleyeceğiz.")
