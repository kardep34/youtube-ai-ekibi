import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

import streamlit as st
from google import genai
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from bot_runtime import bot_calistir, botlar
from queue_panel import render_queue_panel
from task_inbox import render_task_inbox

st.set_page_config(page_title='VORTEX 360 | Yapay Zeka Ekibi', page_icon='🌀')
st.title('🌀 VORTEX 360')
st.caption('Bilinmeyenin Peşinde | İçerik ve YouTube yönetim paneli')

SCOPES = ['https://www.googleapis.com/auth/youtube']
REQUIRED = ['YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REDIRECT_URI']


def new_flow():
    redirect_uri = st.secrets['YOUTUBE_REDIRECT_URI'].strip()
    if urlparse(redirect_uri).scheme != 'https':
        raise ValueError('YOUTUBE_REDIRECT_URI HTTPS olmalı.')
    config = {'web': {
        'client_id': st.secrets['YOUTUBE_CLIENT_ID'],
        'client_secret': st.secrets['YOUTUBE_CLIENT_SECRET'],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': [redirect_uri],
    }}
    return Flow.from_client_config(
    config,
    scopes=SCOPES,
    redirect_uri=redirect_uri,
    autogenerate_code_verifier=False,
    )


def oauth_signature(encoded):
    # HMAC state remains verifiable after Google's redirect starts a new Streamlit session.
    key = (st.secrets['YOUTUBE_CLIENT_SECRET'] + ':' + st.secrets['PANEL_PASSWORD']).encode()
    return hmac.new(key, encoded.encode(), hashlib.sha256).hexdigest()


def new_oauth_state():
    payload = f'{int(time.time())}.{secrets.token_urlsafe(24)}'
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
    return encoded + '.' + oauth_signature(encoded)


def valid_oauth_state(state):
    try:
        encoded, signature = state.rsplit('.', 1)
        if not hmac.compare_digest(oauth_signature(encoded), signature):
            return False
        payload = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode()
        issued = int(payload.split('.', 1)[0])
        return 0 <= time.time() - issued <= 600
    except (ValueError, UnicodeError):
        return False


# Handle the Google redirect BEFORE the password gate, which otherwise discards it.
code = st.query_params.get('code')
state = st.query_params.get('state')
if code and not st.session_state.get('yt_credentials'):
    if any(not st.secrets.get(key) for key in REQUIRED) or not state or not valid_oauth_state(state):
        st.query_params.clear()
        st.error('Google bağlantısı doğrulanamadı. Yeniden bağlanmayı deneyin.')
    else:
        try:
            flow = new_flow()
            flow.fetch_token(code=code)
            st.session_state['yt_credentials'] = flow.credentials
            st.session_state['yt_oauth_success'] = True
            st.query_params.clear()
        except Exception as exc:
            st.query_params.clear()
            st.error(f'Google yetkilendirmesi tamamlanamadı: {exc}')

if not st.session_state.get('giris', False):
    password = st.text_input('Panel şifresi', type='password')
    if st.button('Giriş Yap'):
        if hmac.compare_digest(password, st.secrets['PANEL_PASSWORD']):
            st.session_state['giris'] = True
            st.rerun()
        st.error('Şifre yanlış.')
    st.stop()

if st.button('Çıkış Yap'):
    for key in list(st.session_state):
        if key not in ['giris', 'yt_credentials', 'yt_auth_url', 'yt_oauth_success'] and not key.startswith('vortex_task_'):
            continue
        st.session_state.pop(key, None)
    st.rerun()

render_task_inbox(botlar, bot_calistir, lambda: genai.Client(api_key=st.secrets['GEMINI_API_KEY']))
render_queue_panel(st.secrets.get('VORTEX_QUEUE_URL'), st.secrets.get('VORTEX_QUEUE_TOKEN'))
st.divider()

st.header('🤖 Beş Bot Tek Panelde')
konu = st.text_area('Video konusu', value='Mariana Çukuru: Okyanusun en derin noktasında neler var?')
secim = st.selectbox('Bot seç', list(botlar))
col1, col2 = st.columns(2)
run_one = col1.button('🤖 Seçili Botu Çalıştır')
run_all = col2.button('🚀 Tüm Ekibi Çalıştır')
if run_one or run_all:
    if not konu.strip():
        st.warning('Önce bir konu gir.')
    else:
        try:
            client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
            selected = botlar.items() if run_all else [(secim, botlar[secim])]
            output = ['# VORTEX 360 İçerik Paketi', f'Konu: {konu}']
            for name, task in selected:
                with st.spinner(f'{name} çalışıyor...'):
                    try:
                        result = bot_calistir(client, task, konu)
                        st.subheader(name)
                        st.markdown(result)
                        output.append(f'\n## {name}\n{result}')
                    except Exception as exc:
                        st.error(f'{name} çalışmadı: {exc}')
            st.session_state['icerik_paketi'] = '\n'.join(output)
        except Exception as exc:
            st.error(f'Gemini bağlantısı başarısız: {exc}')
if st.session_state.get('icerik_paketi'):
    st.download_button('📥 İçerik paketini indir', st.session_state['icerik_paketi'], 'VORTEX360_icerik_paketi.md', 'text/markdown')

st.divider()
st.header('🔗 YouTube Resmi Bağlantısı')
st.caption('Google OAuth kullanılır. Google şifreniz bu uygulamaya verilmez. Kanal değişiklikleri yalnızca onayınızla yapılır.')
missing = [key for key in REQUIRED if not st.secrets.get(key)]
if missing:
    st.info('YouTube bağlantısı için eksik Streamlit Secrets: ' + ', '.join(missing))
else:
    if st.session_state.pop('yt_oauth_success', False):
        st.success('Google yetkilendirmesi tamamlandı.')
    if st.button('🔐 Google ile YouTube Bağla'):
        try:
            flow = new_flow()
            url, _ = flow.authorization_url(
                access_type='offline', include_granted_scopes='true',
                prompt='consent', state=new_oauth_state(),
            )
            st.session_state['yt_auth_url'] = url
        except Exception as exc:
            st.error(f'Bağlantı başlatılamadı: {exc}')
    if st.session_state.get('yt_auth_url'):
        st.link_button('Google izin ekranını aç', st.session_state['yt_auth_url'])

    creds = st.session_state.get('yt_credentials')
    if creds:
        try:
            youtube = build('youtube', 'v3', credentials=creds, cache_discovery=False)
            result = youtube.channels().list(part='snippet,brandingSettings', mine=True).execute()
            items = result.get('items', [])
            if not items:
                st.warning('Bu Google hesabına bağlı YouTube kanalı bulunamadı.')
            else:
                channel = items[0]
                channel_id = channel['id']
                title = channel['snippet'].get('title', '')
                st.success(f'Bağlı kanal: {title} ({channel_id})')
                st.write('Kanal adı ve görsel değişiklikleri için YouTube Studio gerekebilir. API işlemleri garanti değildir.')
                new_description = st.text_area('Yeni kanal açıklaması', value=channel['snippet'].get('description', '') or 'VORTEX 360 | Bilinmeyenin Peşinde. Gizemli olaylar, şaşırtıcı gerçekler, uzay, okyanuslar ve tarihin bilinmeyenleri.')
                confirm = st.checkbox('Bu kanalın açıklamasını değiştirmeyi onaylıyorum.')
                if st.button('📝 Kanal açıklamasını kaydet', disabled=not confirm):
                    settings = channel.get('brandingSettings', {})
                    channel_settings = dict(settings.get('channel', {}))
                    channel_settings['description'] = new_description
                    body = {'id': channel_id, 'brandingSettings': {'channel': channel_settings}}
                    youtube.channels().update(part='brandingSettings', body=body).execute()
                    st.success('Açıklama güncellemesi YouTube tarafından kabul edildi.')
        except HttpError as exc:
            st.error(f'YouTube API işlemi başarısız: {exc}')
        except Exception as exc:
            st.error(f'YouTube bağlantı hatası: {exc}')
        if st.button('🔒 YouTube oturumunu kapat'):
            st.session_state.pop('yt_credentials', None)
            st.rerun()

st.caption('Not: Bu panel henüz video dosyası üretmez, YouTube kanal adını veya kapağını otomatik değiştirmez. OAuth oturumu geçicidir.')
st.divider()
st.header("📤 Botların Hazırladığı Videoyu YouTube'a Yükle")

video = st.file_uploader("MP4 video seç", type=["mp4"])
baslik = st.text_input("Video başlığı", max_chars=100, key="video_baslik")
aciklama = st.text_area("Video açıklaması", key="video_aciklama")
onay = st.checkbox("Videonun gizli olarak yüklenmesini onaylıyorum")

if st.button("🚀 YouTube'a Yükle", disabled=not onay):
    if not video or not baslik.strip():
        st.warning("Video ve başlık gerekli.")
    elif not st.session_state.get("yt_credentials"):
        st.error("Önce YouTube hesabını bağla.")
    else:
        import tempfile
        from googleapiclient.http import MediaFileUpload

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(video.getvalue())
            dosya_yolu = f.name

        try:
            yt = build(
                "youtube", "v3",
                credentials=st.session_state["yt_credentials"],
                cache_discovery=False,
            )
            sonuc = yt.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": baslik,
                        "description": aciklama,
                        "categoryId": "27",
                    },
                    "status": {"privacyStatus": "private"},
                },
                media_body=MediaFileUpload(
                    dosya_yolu, mimetype="video/mp4", resumable=True
                ),
            ).execute()
            st.success("Video gizli yüklendi: " + sonuc["id"])
        except Exception as hata:
            st.error(f"Yükleme başarısız: {hata}")
        finally:
            import os
            os.unlink(dosya_yolu)
            st.divider()

st.subheader("🤖 Bot İçeriğini Video Alanına Aktar")

if st.button("📋 Bot Sonuçlarını Aktar"):
    paket = st.session_state.get("icerik_paketi", "")
    if not paket:
        st.warning("Önce Tüm Ekibi Çalıştır.")
    else:
        st.session_state["aktarilan_icerik"] = paket
        st.success("İçerik hazır. Aşağıdan kopyalayabilirsin.")

if st.session_state.get("aktarilan_icerik"):
    st.text_area(
        "Hazırlanan açıklama",
        value=st.session_state["aktarilan_icerik"],
        height=250
    )
    
