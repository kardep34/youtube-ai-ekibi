"""Free production workspace: variable topics, lengths and aspect ratios."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
from zipfile import ZipFile

import streamlit as st

from free_media import read_catalog
from free_render import FORMATS, check_rows, duration, quality_report, render, subtitles


def load_project(raw):
    if len(raw) > 500_000:
        raise ValueError("Proje dosyası çok büyük.")
    project = json.loads(raw)
    if not isinstance(project, dict) or project.get("version") != 1:
        raise ValueError("Desteklenmeyen proje dosyası.")
    for key in ("topic", "script"):
        if not isinstance(project.get(key), str) or len(project[key]) > 30000:
            raise ValueError("Proje metni geçersiz.")
    if project.get("format") not in FORMATS:
        raise ValueError("Geçersiz format.")
    check_rows(project.get("scenes"))
    sources = project.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 200 or any(not isinstance(s, dict) for s in sources):
        raise ValueError("Kaynak listesi geçersiz.")
    return project


def credit_text(sources):
    parts = []
    for item in sources:
        parts.append("\n".join(str(item.get(key, "")) for key in
                               ("title", "creator", "source_url", "license", "license_url", "changes")))
    return "\n\n".join(parts)


def team_brief(topic, script, format_name, rows):
    total = sum(row["seconds"] for row in rows)
    return (
        f"VORTEX 360 ortak üretim görevi\nKonu: {topic}\nFormat: {format_name}\n"
        f"Planlanan süre: {total:.2f} saniye. Konuya veya süreye yeni bir sabit sınır koyma.\n"
        "Yalnızca ücretsiz kaynaklar ve mevcut kullanıcı dosyalarını kullan. Ücretli API, deneme kredisi, "
        "abonelik veya satın alma önerme.\n"
        "Tüm rolleri aşağıdaki tek onaylı anlatım ve sahne planına göre çalıştır. "
        "Onaylı metin varsa yeni bir hikâye uydurma. Belirsiz olguları doğrulanacak olarak işaretle; "
        "kaynakta görmediğin bağlantıyı veya iddiayı doğrulanmış diye yazma.\n"
        "1. Fikir: konunun izleyiciye vaadini ve güçlü açılışını değerlendir.\n"
        "2. Senaryo: metin yoksa hedef süreye uygun bir taslak öner; varsa sahnelere uygunluğunu kontrol et.\n"
        "3. Başlık: anlatımla uyumlu, yanıltıcı olmayan başlıklar öner.\n"
        "4. Açıklama: yalnızca anlatılan içeriğe göre açıklama ve kaynak/atıf alanları hazırla.\n"
        "5. Tasarım: görsel süreklilik, tek altyazı alanı, güvenli boşluklar ve okunurluğu planla.\n"
        "Ardından kaynak editörü olarak doğrulanmamış iddiaları ve atıf gereksinimlerini listele.\n"
        "Görsel yönetmen olarak her sahnenin görsel ihtiyacını, kadrajını ve eksik dosyaları belirle.\n"
        "Ses yönetmeni olarak bu konuya uygun anlatım tonunu, telaffuzları ve müzik yönünü tanımla; her projede aynı sesi dayatma.\n"
        "Son editör olarak çelişki, tekrar, gereksiz uzatma ve anlaşılmaz bölümleri bul. "
        "Görmediğin videonun hareketini veya dinlemediğin sesin kalitesini onaylama. "
        "Sırf ücretsiz olduğu için düşük kaliteli bir malzemeyi uygun kabul etme.\n\n"
        f"Onaylı anlatım:\n{script or '(Henüz girilmedi)'}\n\n"
        + "Sahne planı:\n" + json.dumps(rows, ensure_ascii=False, indent=2)
    )


@st.cache_data(ttl=3600, show_spinner=False)
def cached_search(provider, query):
    return read_catalog(provider, query)


def render_free_studio():
    st.header("🎬 Ücretsiz Üretim Stüdyosu")
    st.info("Ücretli API çağrısı yapılmaz. Gemini üretimi, faturalandırma durumu doğrulanamadığı için kapalıdır. "
            "Konu, süre ve format her projede değişebilir. Hazır metin, görsel, video ve seslerinizi kullanın.")
    state = st.session_state
    state.setdefault("vortex_free_topic", "")
    state.setdefault("vortex_free_script", "")
    state.setdefault("vortex_free_format", "Dikey 9:16")
    state.setdefault("vortex_free_scenes", json.dumps([
        {"media": "sahne1.jpg", "seconds": 5, "caption": "İlk sahnenin altyazısı"}
    ], ensure_ascii=False, indent=2))
    state.setdefault("vortex_free_sources", [])
    st.caption("Projeyi indirip sonra geri yükleyebilirsiniz. Sunucu oturumu kalıcı arşiv değildir; medya dosyaları projeye gömülmez.")
    imported = st.file_uploader("Kaydedilmiş projeyi aç (JSON)", type=["json"], key="vortex_free_import")
    if st.button("Projeyi aç", disabled=imported is None):
        try:
            project = load_project(imported.getvalue())
            for key in ("topic", "script", "format"):
                state["vortex_free_" + key] = project[key]
            state["vortex_free_scenes"] = json.dumps(project["scenes"], ensure_ascii=False, indent=2)
            state["vortex_free_sources"] = project.get("sources", [])
            state["vortex_free_scene_revision"] = state.get("vortex_free_scene_revision", 0) + 1
            state.pop("vortex_free_result", None)
            state.pop("vortex_free_team_brief", None)
        except (ValueError, TypeError):
            st.error("Proje açılamadı. Geçerli bir stüdyo JSON dosyası seçin.")
    topic = st.text_input("Proje konusu", key="vortex_free_topic", max_chars=1000)
    script = st.text_area("Onaylanmış anlatım metni", key="vortex_free_script", max_chars=30000)
    format_name = st.selectbox("Görüntü formatı", list(FORMATS), key="vortex_free_format")
    st.caption(f"Metin yaklaşık {len(script.split())} kelime. Gerçek süre seçilen ses dosyası üzerinden ölçülür.")
    st.subheader("Sahne planı")
    st.caption("Dosya adını yüklediğiniz dosyayla aynı yazın. Satır ekleyerek istediğiniz uzunlukta planlayın.")
    edited = st.data_editor(
        json.loads(state["vortex_free_scenes"]), num_rows="dynamic", hide_index=True,
        column_config={
            "media": st.column_config.TextColumn("Dosya adı", required=True),
            "seconds": st.column_config.NumberColumn("Süre (saniye)", min_value=0.25, max_value=3600, step=0.25, required=True),
            "caption": st.column_config.TextColumn("Altyazı", max_chars=160),
        }, key=f"vortex_free_scene_editor_{state.get('vortex_free_scene_revision', 0)}",
    )
    scenes_raw = json.dumps(edited, ensure_ascii=False)
    # Preserve the editor's original data while it applies deltas. Import changes its key.
    rows = None
    try:
        rows = check_rows(json.loads(scenes_raw))
        total = sum(r["seconds"] for r in rows)
        st.write(f"{len(rows)} sahne · toplam {total:.2f} saniye")
        warnings = []
        for i, row in enumerate(rows, 1):
            cps = len(row["caption"]) / row["seconds"]
            if cps > 20:
                warnings.append(f"{i}. sahnede altyazı hızlı: {cps:.0f} karakter/saniye.")
            if len(row["caption"]) > 76:
                warnings.append(f"{i}. sahnenin altyazısını daha kısa parçalara bölün.")
        for warning in warnings:
            st.warning(warning)
    except (ValueError, TypeError, KeyError):
        st.warning('Sahne tablosuna dosya adı ve geçerli süre girin; altyazı isteğe bağlıdır.')
    if rows:
        project = {"version": 1, "topic": topic, "script": script, "format": format_name,
                   "scenes": rows, "sources": state["vortex_free_sources"]}
        st.download_button("Projeyi indir", json.dumps(project, ensure_ascii=False, indent=2),
                           "vortex360-proje.json", "application/json")
        st.download_button("Zamanlı altyazıyı indir", subtitles(rows), "vortex360.srt", "text/plain")
        if st.button("Beş bot için ortak görev hazırla"):
            state["vortex_free_team_brief"] = team_brief(topic, script, format_name, rows)
        if state.get("vortex_free_team_brief"):
            st.caption("Bu görev metnini ChatGPT'de kullanın. Hazırlamak API çağrısı yapmaz ve botları otomatik çalıştırmaz.")
            st.text_area("Ortak üretim görevi", value=state["vortex_free_team_brief"], height=200, disabled=True)
            st.download_button("Ortak görevi indir", state["vortex_free_team_brief"], "vortex360-ortak-gorev.txt")

    with st.expander("Ücretsiz kaynaklarda ara"):
        provider = st.selectbox("Kaynak", ["Wikimedia Commons", "NASA"], key="vortex_free_provider")
        query = st.text_input("Arama sözcükleri", max_chars=200, key="vortex_free_query")
        st.caption("NASA uzay ve bilim; Commons tarih, doğa ve başka konular içindir. İngilizce sözcükler de deneyebilirsiniz.")
        if st.button("Kaynaklarda ara", disabled=not query.strip()):
            try:
                with st.spinner("Kaynaklar aranıyor…"):
                    state["vortex_free_search"] = cached_search(provider, query)
            except Exception:
                state["vortex_free_search"] = []
                st.warning("Kaynağa ulaşılamadı veya istek sınırına ulaşıldı. Ücretli alternatif kullanılmadı.")
        for i, item in enumerate(state.get("vortex_free_search", [])):
            st.write(item["title"])
            st.caption(f"{item['creator']} · {item['license']}")
            st.link_button("Kaynak dosyasını incele", item["source_url"])
            st.link_button(f"Kullanım koşulları · {i+1}", item["license_url"])
            if st.button("Proje kaynaklarına ekle", key=f"vortex_free_add_{i}"):
                if item["source_url"] not in [s.get("source_url") for s in state["vortex_free_sources"]]:
                    state["vortex_free_sources"].append(item.copy())
                    st.rerun()
        st.caption("Kaynağa eklemek kullanım iznini doğrulamaz. Dosyayı kaynak sayfasından indirip aşağıya yükleyin.")
        st.link_button("Pexels ücretsiz videolar — elle seçim", "https://www.pexels.com/videos/")
        st.link_button("YouTube Ses Kitaplığı", "https://www.youtube.com/audiolibrary")
    if state["vortex_free_sources"]:
        st.subheader("Kaynak ve atıf kaydı")
        st.text(credit_text(state["vortex_free_sources"]))
        st.download_button("Atıfları indir", credit_text(state["vortex_free_sources"]), "kaynaklar.txt")

    st.subheader("Ses seçimi ve kurgu")
    st.caption("Her proje için uygun anlatım dosyasını seçin. Ses, konuya ve hedef süreye göre değişebilir.")
    uploads = st.file_uploader("Sahne dosyaları", type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "webm"],
                               accept_multiple_files=True, key="vortex_free_media")
    narration = st.file_uploader("Anlatım sesi", type=["wav", "mp3", "m4a"], key="vortex_free_narration")
    generated = st.session_state.get("vortex_task_audio")
    if generated and st.checkbox("Panelde üretilen son ses kaydını kullan", key="vortex_free_use_generated"):
        narration = BytesIO(generated[0])
        narration.name = "panel-anlatim.wav"
        voice = st.session_state.get("vortex_task_audio_voice", "")
        st.caption(f"Panelden aktarıldı · {voice} · {generated[1]:.1f} saniye. İndirip yeniden yüklemeniz gerekmez.")

    music = st.file_uploader("Kullanım hakkınız olan müzik (isteğe bağlı)", type=["wav", "mp3", "m4a"], key="vortex_free_music")
    if narration is not None:
        st.audio(narration.getvalue())
        from hashlib import sha256
        voice_key = sha256(narration.getvalue()).hexdigest()[:16]
        voice_approved = st.checkbox("Bu ses kaydını dinledim; telaffuz, ton ve anlaşılabilirliğini onaylıyorum.",
                                     key=f"vortex_free_voice_ok_{voice_key}")
    else:
        voice_approved = st.checkbox("Bu projede anlatım sesi kullanılmayacak.", key="vortex_free_no_narration")
    rights = st.checkbox("Yüklediğim dosyaların kullanım koşullarını ve gereken atıfları kontrol ettim.")
    preview = st.checkbox("Önizleme çözünürlüğü (daha hızlı)", value=True)
    burn = st.checkbox("Sahne altyazılarını videoya işle", value=True)
    st.caption("Sahnelerin özgün sesi kapatılır. Kısa klipler sahne süresince döngüye alınır. "
               "Ücretsiz sunucunun belleği ve işlem süresi sınırlıdır; uzun projeleri bilgisayarınızda çalıştırabilirsiniz.")
    if st.button("Ücretsiz MP4 oluştur", disabled=not rows or not uploads or not rights or not voice_approved):
        state.pop("vortex_free_result", None)
        try:
            names = [f.name for f in uploads]
            all_uploads = list(uploads) + [f for f in (narration, music) if f is not None]
            if len(names) != len(set(names)):
                raise ValueError("Sahne dosyalarının adları benzersiz olmalı.")
            if sum(f.size for f in all_uploads) > 200_000_000:
                raise ValueError("Bu sunucuda yüklemelerin toplam sınırı 200 MB. Büyük projeyi yerelde çalıştırın.")
            with st.spinner("MP4 yerel araçlarla oluşturuluyor…"), tempfile.TemporaryDirectory(prefix="vortex_render_") as temp:
                root = Path(temp)
                files = {}
                for i, upload in enumerate(uploads):
                    path = root / f"input{i}{Path(upload.name).suffix.lower()}"
                    path.write_bytes(upload.getvalue())
                    files[upload.name] = path
                audio_paths = []
                for i, upload in enumerate((narration, music)):
                    if upload is not None:
                        path = root / f"audio{i}{Path(upload.name).suffix.lower()}"
                        path.write_bytes(upload.getvalue())
                    else:
                        path = None
                    audio_paths.append(path)
                if audio_paths[0]:
                    st.write(f"Anlatım süresi: {duration(audio_paths[0]):.2f} saniye")
                output, srt = render(rows, files, root / "render", format_name=format_name,
                                     narration=audio_paths[0], music=audio_paths[1], preview=preview, burn_subtitles=burn)
                report = quality_report(output)
                package = BytesIO()
                with ZipFile(package, "w") as archive:
                    archive.write(output, "vortex360.mp4")
                    archive.write(srt, "vortex360.srt")
                    archive.writestr("kaynaklar.txt", credit_text(state["vortex_free_sources"]))
                    archive.writestr("proje.json", json.dumps(project, ensure_ascii=False, indent=2))
                    archive.writestr("teknik-kontrol.json", json.dumps(report, ensure_ascii=False, indent=2))
                state["vortex_free_result"] = (output.read_bytes(), package.getvalue())
        except Exception as exc:
            # Provider bodies and local paths are never echoed.
            st.error(str(exc) if isinstance(exc, ValueError) else "Kurgu tamamlanamadı; dosyaları ve sunucu kaynaklarını kontrol edin.")
    if state.get("vortex_free_result"):
        st.caption("İnceleme çıktısı: hareket, görsel tutarlılık, telaffuz ve kurgu ritmini izleyerek değerlendirin. Teknik kontrol profesyonel kaliteyi garanti etmez. Projeyi değiştirdiyseniz yeniden oluşturun.")
        video, package = state["vortex_free_result"]
        st.video(video)
        st.download_button("İnceleme MP4 dosyasını indir", video, "vortex360.mp4", "video/mp4")
        st.download_button("Video ve proje paketini indir", package, "vortex360-paket.zip", "application/zip")
    with st.expander("Ücretsiz tamamlayıcı uygulamalar"):
        st.link_button("Shotcut — bilgisayarda kurgu", "https://shotcut.org/")
        st.link_button("Audacity — kendi sesinizi kaydetme ve düzenleme", "https://www.audacityteam.org/")
        st.caption("Bunlar indirme bağlantılarıdır; bilgisayarınıza kurulmuş veya ChatGPT'ye bağlanmış değillerdir.")
