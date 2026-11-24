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

from task_inbox import render_task_inbox
from free_policy import BILLING_SCOPES, FreeOnlyBlocked, require_free_generation
from free_studio import render_free_studio

st.set_page_config(page_title='VORTEX 360 | Yapay Zeka Ekibi', page_icon='🌀')
st.title('🌀 VORTEX 360')
st.caption('Bilinmeyenin Peşinde | İçerik ve YouTube yönetim paneli')

SCOPES = ['https://www.googleapis.com/auth/youtube']
REQUIRED = ['YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REDIRECT_URI']


def new_flow(purpose="youtube"):
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
    scopes=BILLING_SCOPES if purpose == "billing" else SCOPES,
    redirect_uri=redirect_uri,
    autogenerate_code_verifier=False,
    )


def oauth_signature(encoded):
    # HMAC state remains verifiable after Google's redirect starts a new Streamlit session.
    key = (st.secrets['YOUTUBE_CLIENT_SECRET'] + ':' + st.secrets['PANEL_PASSWORD']).encode()
    return hmac.new(key, encoded.encode(), hashlib.sha256).hexdigest()


def new_oauth_state(purpose="youtube"):
    payload = f'{int(time.time())}.{secrets.token_urlsafe(24)}.{purpose}'
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


def oauth_purpose(state):
    if not valid_oauth_state(state):
        return None
    encoded = state.rsplit('.', 1)[0]
    payload = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode()
    purpose = payload.split('.')[-1]
    return purpose if purpose in ('youtube', 'billing') else 'youtube'


# Handle both signed OAuth callbacks before the password gate.
code = st.query_params.get('code')
state = st.query_params.get('state')
if code:
    purpose = oauth_purpose(state) if state else None
    if any(not st.secrets.get(key) for key in REQUIRED) or purpose is None:
        st.query_params.clear()
        st.error('Google bağlantısı doğrulanamadı. Yeniden bağlanmayı deneyin.')
    else:
        try:
            flow = new_flow(purpose)
            flow.fetch_token(code=code)
            if purpose == 'billing':
                st.session_state['vortex_billing_credentials'] = flow.credentials
                st.session_state.pop('vortex_billing_auth_url', None)
            else:
                st.session_state['yt_credentials'] = flow.credentials
                st.session_state['yt_oauth_success'] = True
            st.query_params.clear()
        except Exception:
            st.query_params.clear()
            st.error('Google yetkilendirmesi tamamlanamadı. Bağlantıyı yeniden başlatın.')
elif st.query_params.get('error'):
    st.query_params.clear()
    st.warning('Google izni verilmedi. Üretim açılmadı.')

if not st.session_state.get('giris', False):
    password = st.text_input('Panel şifresi', type='password')
    if st.button('Giriş Yap'):
        if hmac.compare_digest(password.encode('utf-8'), st.secrets['PANEL_PASSWORD'].encode('utf-8')):
            st.session_state['giris'] = True
            st.rerun()
        st.error('Şifre yanlış.')
    st.stop()

if st.button('Çıkış Yap'):
    for key in list(st.session_state):
        if key not in ['giris', 'yt_credentials', 'yt_auth_url', 'yt_oauth_success'] and not key.startswith(('vortex_task_', 'vortex_free_', 'vortex_voice_', 'vortex_billing_')):
            continue
        st.session_state.pop(key, None)
    st.rerun()

st.subheader('Ücretsiz üretim bağlantısı')
st.caption('Gemini anahtarının projesi ve faturalandırması salt okunur kontrol edilir. '
           'Kart eklenmez, ödeme açılmaz. Her üretim öncesi yeniden kontrol edilir. '
           'Bu kontrol ücretsiz kota veya model erişimi garantisi değildir.')
if not st.session_state.get('vortex_billing_credentials'):
    st.info('Ses ve bot üretimi için bir defalık Google okuma izni gerekli. '
            'Bu oturum kapanırsa bağlantı yeniden istenir; izinler sunucuda kalıcı saklanmaz.')
    if not any(not st.secrets.get(key) for key in REQUIRED):
        if st.button('Google ücretsiz kullanım kontrolünü bağla'):
            try:
                flow = new_flow('billing')
                url, _ = flow.authorization_url(
                    access_type='offline', prompt='consent', state=new_oauth_state('billing'),
                )
                st.session_state['vortex_billing_auth_url'] = url
            except Exception:
                st.error('Bağlantı başlatılamadı. Google OAuth yapılandırmasını kontrol edin.')
        if st.session_state.get('vortex_billing_auth_url'):
            st.link_button('Salt okunur Google izin ekranını aç', st.session_state['vortex_billing_auth_url'])
    else:
        st.warning('Google OAuth bağlantı ayarları eksik. Üretim kapalı; yerel MP4 stüdyosu kullanılabilir.')
else:
    if st.button('Ücretsiz kullanım durumunu kontrol et'):
        try:
            project = require_free_generation()
            st.success(f'Proje: {project} · Bağlı faturalandırma hesabı yok. Üretim kontrolü geçti.')
        except FreeOnlyBlocked as exc:
            st.warning(str(exc))
    if st.button('Ücretsiz kontrol bağlantısını kapat'):
        st.session_state.pop('vortex_billing_credentials', None)
        st.session_state.pop('vortex_billing_auth_url', None)
        st.rerun()
st.divider()

botlar = {
    '💡 Fikir Üretici': '10 özgün YouTube video fikri üret. Bilimsel iddiaları doğrulanması gerekenler olarak işaretle.',
    '✍️ Senaryo Yazarı': 'Ortak görevdeki konu, hedef süre, format ve onaylı anlatıma göre senaryo hazırla. Süre belirtilmemişse tahminini açıkça belirt; sabit uzunluk dayatma.',
    '🎯 Başlık Uzmanı': '10 dikkat çekici ama yanıltıcı olmayan başlık öner.',
    '📝 Açıklama Uzmanı': 'YouTube açıklaması, bölüm zamanları için taslak, etiketler ve hashtagler üret.',
    '🎨 Kanal Tasarımcısı': 'VORTEX 360 için siyah, mor, elektrik mavisi görsel tasarım ve küçük resim önerileri üret.',
}


def bot_calistir(client, gorev, konu):
    require_free_generation()
    prompt = f'Türkçe yanıt ver. Kanal VORTEX 360, slogan Bilinmeyenin Peşinde.\nGörev: {gorev}\nKonu: {konu}'
    for attempt in range(3):
        try:
            require_free_generation()
            result = client.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt)
            return result.text or 'Boş yanıt geldi.'
        except Exception as exc:
            if attempt < 2 and '503' in str(exc):
                time.sleep(10 * (attempt + 1))
            else:
                raise


def make_generation_client():
    require_free_generation()
    return genai.Client(api_key=st.secrets['GEMINI_API_KEY'])


render_free_studio()
st.divider()
render_task_inbox(botlar, bot_calistir, make_generation_client)
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
            client = make_generation_client()
            selected = botlar.items() if run_all else [(secim, botlar[secim])]
            output = ['# VORTEX 360 İçerik Paketi', f'Konu: {konu}']
            for name, task in selected:
                with st.spinner(f'{name} çalışıyor...'):
                    try:
                        context = konu + ('\n\nÖnceki ekip çıktıları:\n' + '\n'.join(output[2:]) if len(output) > 2 else '')
                        result = bot_calistir(client, task, context)
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

st.caption('Ücretsiz stüdyo yüklenen medyadan MP4 oluşturur. YouTube OAuth oturumu geçicidir.')
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
    

