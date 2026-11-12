
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
st.divider()
st.header("🎬 YouTube Yapay Zeka Ekibi")

botlar = {
    "💡 Fikir Üretici": "Yeni video fikirleri hazırlar.",
    "✍️ Senaryo Yazarı": "Video senaryoları hazırlar.",
    "🎯 Başlık Uzmanı": "Video başlıkları önerir.",
    "📝 Açıklama Uzmanı": "Açıklama ve etiket hazırlar.",
    "🎨 Kanal Tasarımcısı": "Kanal ismi, logo, profil resmi, kapak ve küçük resim tasarımlarını planlar."
}

secim = st.selectbox("Bot seç", list(botlar))
st.info(botlar[secim])

konu = st.text_input("Kanal veya video konusunu yaz")

if st.button("Botu Çalıştır"):
    if konu.strip():
        st.success(f"{secim} için görev hazır!")
        st.write("Konu:", konu)
    else:
        st.warning("Önce bir konu yaz.")


