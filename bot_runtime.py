import time


botlar = {
    '💡 Fikir Üretici': '10 özgün YouTube video fikri üret. Bilimsel iddiaları doğrulanması gerekenler olarak işaretle.',
    '✍️ Senaryo Yazarı': '6-8 dakikalık uzun video senaryosu ve 3 farklı 30-45 saniyelik Shorts senaryosu yaz.',
    '🎯 Başlık Uzmanı': '10 dikkat çekici ama yanıltıcı olmayan başlık öner.',
    '📝 Açıklama Uzmanı': 'YouTube açıklaması, bölüm zamanları için taslak, etiketler ve hashtagler üret.',
    '🎨 Kanal Tasarımcısı': 'VORTEX 360 için siyah, mor, elektrik mavisi görsel tasarım ve küçük resim önerileri üret.',
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
