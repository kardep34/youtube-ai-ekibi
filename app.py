
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
    sifre = st.text_input("Panel şifresi", type="password")

    if st.button("Giriş Yap"):
        if hmac.compare_digest(
            sifre,
            st.secrets["PANEL_PASSWORD"]
        ):
            st.session_state["giris"] = True
            st.rerun()
        else:
            st.error("Şifre yanlış.")

    st.stop()

if st.button("Çıkış Yap"):
    st.session_state["giris"] = False
    st.rerun()

st.divider()

botlar = {
    "💡 Fikir Üretici": (
        "Bu konuda 10 özgün YouTube video fikri üret. "
        "Her fikri kısaca açıkla."
    ),
    "✍️ Senaryo Yazarı": (
        "Bu konuda giriş, gelişme ve kapanış içeren "
        "ayrıntılı bir YouTube video senaryosu yaz."
    ),
    "🎯 Başlık Uzmanı": (
        "Bu konuda 10 dikkat çekici, dürüst "
        "YouTube video başlığı öner."
    ),
    "📝 Açıklama Uzmanı": (
        "Bu konuda YouTube açıklaması, "
        "etiketler ve hashtagler hazırla."
    ),
    "🎨 Kanal Tasarımcısı": (
        "Bu konuda kanal isimleri, logo fikirleri, "
        "profil resmi ve banner tasarım önerileri hazırla."
    )
}

def bot_calistir(client, gorev, konu):
    mesaj = (
        "Türkçe yanıt ver.\n"
        + gorev
        + "\nKonu: "
        + konu
    )

    for deneme in range(3):
        try:
            yanit = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=mesaj
            )
            return yanit.text or "Boş yanıt geldi."

        except Exception as hata:
            hata_metni = str(hata)

            if (
                ("429" in hata_metni or
                 "503" in hata_metni)
                and deneme < 2
            ):
                time.sleep(10 * (deneme + 1))
            else:
                raise

def sonuc_goster(ad, gorev, konu, client):
    with st.spinner(f"{ad} çalışıyor..."):
        try:
            sonuc = bot_calistir(client, gorev, konu)
            st.subheader(ad)
            st.markdown(sonuc)
        except Exception as hata:
            st.error(f"{ad} çalıştırılamadı.")
            st.warning(
                "Gemini yoğun olabilir veya "
                "kullanım sınırına ulaşılmış olabilir."
            )
            with st.expander("Hata ayrıntısı"):
                st.code(str(hata))

st.header("🤖 Yapay Zeka Ekibim")

secim = st.selectbox("Bot seç", list(botlar.keys()))

konu = st.text_area(
    "Kanal veya video konusunu yaz",
    key="tek_konu"
)

if st.button("🤖 Botu Çalıştır"):
    if not konu.strip():
        st.warning("Önce bir konu yaz.")
    else:
        client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"]
        )
        sonuc_goster(
            secim, botlar[secim], konu, client
        )

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
            sonuc_goster(
                bot_adi,
                bot_gorevi,
                toplu_konu,
                client
            )
            time.sleep(5)

        st.success("Ekip çalışması tamamlandı.")

