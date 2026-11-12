
import streamlit as st
import hmac

st.title("🔐 YouTube Yapay Zeka Ekibim")

sifre = st.text_input("Şifrenizi girin", type="password")

if st.button("Giriş Yap"):
    if "PANEL_PASSWORD" not in st.secrets:
        st.error("Panel şifresi henüz ayarlanmadı.")
    elif hmac.compare_digest(
        sifre, st.secrets["PANEL_PASSWORD"]
    ):
        st.session_state["giris"] = True
    else:
        st.error("Yanlış şifre!")

if st.session_state.get("giris", False):
    st.success("Bot yönetim paneli hazır!")
else:
    st.stop()

