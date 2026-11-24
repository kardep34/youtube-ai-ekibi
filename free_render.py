"""Local FFmpeg rendering and timed subtitles."""
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import textwrap

FORMATS = {"Dikey 9:16": (1080, 1920), "Yatay 16:9": (1920, 1080), "Kare 1:1": (1080, 1080)}


def run(args, timeout=120):
    result = subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError("Yerel medya işlemi tamamlanamadı; dosya biçimini ve araç kurulumunu kontrol edin.")
    return result.stdout


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def duration(path):
    value = float(probe(path).get("format", {}).get("duration", 0))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Dosya süresi ölçülemedi.")
    return value


def check_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ValueError("1–200 sahne gerekli.")
    clean = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Her sahne bir nesne olmalı.")
        seconds = float(row.get("seconds", 0))
        media = str(row.get("media", ""))
        caption = str(row.get("caption") or "")
        if not math.isfinite(seconds) or not 0.25 <= seconds <= 3600:
            raise ValueError("Sahne süresi 0,25–3600 saniye olmalı.")
        if not media or media != Path(media).name or "\\" in media:
            raise ValueError("Sahne yalnızca yüklenen dosyanın adını içermeli.")
        if len(caption) > 160:
            raise ValueError("Sahne altyazısı en fazla 160 karakter olabilir; uzun metni sahnelere bölün.")
        clean.append({"media": media, "seconds": seconds, "caption": caption})
    return clean


def subtitles(rows):
    def clock(value):
        millis = round(value * 1000)
        secs, ms = divmod(millis, 1000)
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02}:{mins:02}:{secs:02},{ms:03}"
    parts, cursor = [], 0.0
    for row in check_rows(rows):
        end = cursor + row["seconds"]
        caption = re.sub(r"[<>\r\n]", " ", row["caption"]).strip()
        if caption:
            parts.append(f"{len(parts)+1}\n{clock(cursor)} --> {clock(end)}\n" + textwrap.fill(caption, 38) + "\n")
        cursor = end
    return "\n".join(parts)


def quality_report(path):
    metadata = probe(path)
    video = next((s for s in metadata.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in metadata.get("streams", []) if s.get("codec_type") == "audio"), {})
    return {
        "duration_seconds": float(metadata.get("format", {}).get("duration", 0)),
        "width": video.get("width"), "height": video.get("height"),
        "video_codec": video.get("codec_name"), "frame_rate": video.get("avg_frame_rate"),
        "video_bitrate": video.get("bit_rate"), "audio_codec": audio.get("codec_name"),
        "review_required": ["Görsel tutarlılık ve yapay üretim kusurları", "Telaffuz ve anlatım tonu",
                            "Altyazı zamanlaması ve okunurluk", "Müzik dengesi ve kurgu ritmi",
                            "Olgusal doğruluk ve kaynak koşulları"],
        "professional_quality_certified": False,
    }


def render(rows, files, output_dir, *, format_name="Dikey 9:16", narration=None, music=None, preview=True, burn_subtitles=True):
    rows = check_rows(rows)
    if format_name not in FORMATS:
        raise ValueError("Desteklenmeyen format.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("FFmpeg ve ffprobe kurulmalı.")
    if any(row["media"] not in files for row in rows):
        raise ValueError("Sahne dosyalarından biri yüklenmemiş.")
    total = sum(r["seconds"] for r in rows)
    if narration and abs(duration(narration) - total) > 0.75:
        raise ValueError("Ses ile sahne toplamı uyuşmuyor. Sahne sürelerini ses süresine göre düzenleyin.")
    width, height = FORMATS[format_name]
    if preview:
        width, height = width // 2, height // 2
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Segments are serial to keep memory use bounded on free hosting.
    for index, row in enumerate(rows):
        source = Path(files[row["media"]])
        metadata = probe(source)
        if not any(s.get("codec_type") == "video" for s in metadata.get("streams", [])):
            raise ValueError("Sahne dosyası görüntü veya video olmalı.")
        still = source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        args = ["ffmpeg", "-v", "error", "-y", "-threads", "1"]
        args += ["-loop", "1"] if still else ["-stream_loop", "-1"]
        args += ["-i", str(source), "-t", str(row["seconds"]), "-an", "-vf",
                 f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101a16,setsar=1,fps=24,format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if preview else "18",
                 "-threads", "1", str(output_dir / f"scene{index:03}.mp4")]
        run(args, timeout=max(120, int(row["seconds"] * 10)))
    listing = output_dir / "segments.txt"
    listing.write_text("\n".join(f"file 'scene{i:03}.mp4'" for i in range(len(rows))))
    joined = output_dir / "joined.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", str(listing), "-c", "copy", str(joined)], timeout=300)
    srt = output_dir / "captions.srt"
    srt.write_text(subtitles(rows), encoding="utf-8")
    output = output_dir / "vortex360.mp4"
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(joined)]
    if narration:
        args += ["-i", str(narration)]
    if music:
        args += ["-stream_loop", "-1", "-i", str(music)]
    if narration and music:
        args += ["-filter_complex", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[n];[2:a]volume=0.10[m];[n][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]", "-map", "0:v:0", "-map", "[a]"]
    elif narration or music:
        args += ["-map", "0:v:0", "-map", "1:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11" if narration else "volume=0.10"]
    else:
        args += ["-an"]
    if burn_subtitles and srt.stat().st_size:
        # Path is generated internally. Do not interpolate user text into filters.
        escaped = str(srt.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "'\\''")
        args += ["-vf", f"subtitles=filename='{escaped}':force_style='FontName=DejaVu Sans,FontSize=18,Outline=2,MarginV=40'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23" if preview else "18", "-threads", "1"]
    else:
        args += ["-c:v", "copy"]
    args += ["-c:a", "aac", "-b:a", "192k", "-t", str(total), "-movflags", "+faststart", str(output)]
    run(args, timeout=max(300, int(total * 10)))
    return output, srt
