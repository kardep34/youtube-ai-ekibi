"""Keyless, read-only catalog integrations. No paid fallback or media scraping."""
import html
import json
import re
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

NASA_POLICY = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
COMMONS_POLICY = "https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia"
CATALOGS = {
    "NASA": "https://images-api.nasa.gov/search",
    "Wikimedia Commons": "https://commons.wikimedia.org/w/api.php",
}


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))[:2000]


def public_url(value):
    parsed = urlparse(str(value or ""))
    return str(value) if parsed.scheme == "https" and parsed.hostname else ""


def read_catalog(provider, query):
    query = query.strip()
    if provider not in CATALOGS or not 1 <= len(query) <= 200:
        raise ValueError("Kaynak ve 1–200 karakterlik arama gerekli.")
    if provider == "NASA":
        params = {"q": query, "media_type": "image,video,audio", "page_size": 12}
    else:
        params = {
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 12,
            "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
        }
    request = Request(CATALOGS[provider] + "?" + urlencode(params), headers={
        "User-Agent": "VORTEX360-FreeStudio/1.0 (https://github.com/kardep34/youtube-ai-ekibi)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=15) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("Kaynak yanıtı sınırı aştı.")
    return parse_catalog(provider, json.loads(payload))


def parse_catalog(provider, payload):
    results = []
    if provider == "NASA":
        for item in payload.get("collection", {}).get("items", [])[:12]:
            data = (item.get("data") or [{}])[0]
            nasa_id = str(data.get("nasa_id", ""))
            from urllib.parse import quote
            results.append({
                "title": plain(data.get("title")), "provider": provider,
                "source_url": "https://images.nasa.gov/details/" + quote(nasa_id, safe=""),
                "creator": plain(data.get("photographer") or data.get("center") or "NASA"),
                "license": "NASA kullanım koşulları; üçüncü taraf haklarını kontrol edin",
                "license_url": NASA_POLICY, "media_type": plain(data.get("media_type")),
                "description": plain(data.get("description")),
            })
    elif provider == "Wikimedia Commons":
        for page in list(payload.get("query", {}).get("pages", {}).values())[:12]:
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            get = lambda key: plain(meta.get(key, {}).get("value"))
            results.append({
                "title": plain(page.get("title")), "provider": provider,
                "source_url": public_url(info.get("descriptionurl")),
                "creator": get("Artist"), "license": get("LicenseShortName") or "Lisansı doğrulayın",
                "license_url": public_url(get("LicenseUrl")) or COMMONS_POLICY,
                "media_type": plain(info.get("mime")), "description": get("ImageDescription"),
            })
    else:
        raise ValueError("Desteklenmeyen kaynak.")
    # A search result is never a license clearance. Selection records provenance only.
    return [dict(item, rights_checked=False, changes="") for item in results if item["source_url"]]
