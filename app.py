import hmac
import time
import secrets
from urllib.parse import urlparse

import streamlit as st
from google import genai
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

st.set_page_config(page_title='VORTEX 360 | Yapay Zeka Ekibi', page_icon='🌀')
st.title('🌀 VORTEX 360')
st.caption('Bilinmeyenin Peşinde | İçerik ve YouTube yönetim paneli')

if not st.session_state.get('giris', False):
    password = st.text_input('Panel şifresi', type='password')
    if st.button('Giriş Yap'):
        if hmac.compare_digest(password, st.secrets['PANEL_PASSWORD']):
            st.session_state['giris'] = True
            st.rerun()
        st.error('Şifre yanlış.')
    st.stop()

if st.button('Çıkış Yap'):
    for key in ['giris', 'yt_credentials', 'yt_oauth_state', 'yt_oauth_verifier']:
        st.session_state.pop(key, None)
    st.rerun()

botlar = {
    '💡 Fikir Üretici': '10 özgün YouTube video fikri üret. Bilimsel iddiaları doğrulanması gerekenler olarak işaretle.',
    '✍️ Senaryo Yazarı': '6-8 dakikalık uzun video senaryosu ve 3 farklı 30-45 saniyelik Shorts senaryosu yaz.',
    '🎯 Başlık Uzmanı': '10 dikkat çekici ama yanıltıcı olmayan başlık öner.',
    '📝 Açıklama Uzmanı': 'YouTube açıklaması, bölüm zamanları için taslak, etiketler ve hashtagler üret.',
    '🎨 Kanal Tasarımcısı': 'VORTEX 360 için siyah, mor, elektrik mavisi görsel tasarım ve küçük resim önerileri üret.'
}

def bot_calistir(client, gorev, konu):
    prompt = f'Türkçe yanıt ver. Kanal VORTEX 360, slogan Bilinmeyenin Peşinde.\nGörev: {gorev}\nKonu: {konu}'
    for attempt in range(3):
        try:
            result = client.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt)
            return result.text or 'Boş yanıt geldi.'
        except Exception as exc:
            if attempt < 2 and any(code in str(exc) for code in ('429', '503')):
                time.sleep(10 * (attempt + 1))
            else:
                raise

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

SCOPES = ['https://www.googleapis.com/auth/youtube']
REQUIRED = ['YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REDIRECT_URI']
missing = [key for key in REQUIRED if not st.secrets.get(key)]

def new_flow():
    redirect_uri = st.secrets['YOUTUBE_REDIRECT_URI'].strip()
    if urlparse(redirect_uri).scheme != 'https':
        raise ValueError('YOUTUBE_REDIRECT_URI HTTPS olmalı.')
    config = {'web': {'client_id': st.secrets['YOUTUBE_CLIENT_ID'],
                      'client_secret': st.secrets['YOUTUBE_CLIENT_SECRET'],
                      'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                      'token_uri': 'https://oauth2.googleapis.com/token',
                      'redirect_uris': [redirect_uri]}}
    return Flow.from_client_config(config, scopes=SCOPES, redirect_uri=redirect_uri)

if missing:
    st.info('YouTube bağlantısı için Google Cloud OAuth bilgileri Streamlit Secrets bölümüne eklenmeli: ' + ', '.join(missing))
else:
    if st.button('🔐 Google ile YouTube Bağla'):
        try:
            flow = new_flow()
            state = secrets.token_urlsafe(32)
            url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent', state=state)
            st.session_state['yt_oauth_state'] = state
            st.session_state['yt_oauth_verifier'] = flow.code_verifier
            st.link_button('Google izin ekranını aç', url)
            st.session_state['yt_auth_url'] = url
        except Exception as exc:
            st.error(f'Bağlantı başlatılamadı: {exc}')
    if st.session_state.get('yt_auth_url'):
        st.link_button('Google izin ekranını aç', st.session_state['yt_auth_url'])

    code = st.query_params.get('code')
    state = st.query_params.get('state')
    if code and not st.session_state.get('yt_credentials'):
        if not state or not hmac.compare_digest(state, st.session_state.get('yt_oauth_state', '')):
            st.error('Güvenlik doğrulaması başarısız. Bağlantıyı yeniden başlatın.')
        else:
            try:
                flow = new_flow()
                flow.code_verifier = st.session_state.get('yt_oauth_verifier')
                flow.fetch_token(code=code)
                st.session_state['yt_credentials'] = flow.credentials
                st.query_params.clear()
                st.success('Google yetkilendirmesi tamamlandı.')
                st.rerun()
            except Exception as exc:
                st.error(f'Google yetkilendirmesi tamamlanamadı: {exc}')

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
