#!/usr/bin/env python3
"""
BD-KB-IT Playlist Builder — ADVANCED
====================================
- Deep stream validation (only working channels)
- Auto logo resolution + validation
- Smart auto-grouping by keyword
- Language / country / quality detection
- Priority-ordered groups
"""

import os
import re
import json
import time
import hashlib
import urllib.request
import urllib.error

from urllib.parse import urljoin, urlparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


# ==========================================
# CONFIG
# ==========================================

BASE_URL = "https://web.aynaott.com"
DEFAULT_API_URL = "https://web.aynaott.com/api/v5/pages/live-tvs/"
API_URL = os.environ.get("BD_KB_IT_API_URL", DEFAULT_API_URL)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PLAYLIST_FILE = OUTPUT_DIR / "BD-KB-IT.m3u8"
CHANNEL_FILE  = OUTPUT_DIR / "ALL_CHANNEL_DATA.json"
RAW_FILE      = OUTPUT_DIR / "ALL_API_RESPONSES.json"
HEALTH_FILE   = OUTPUT_DIR / "health_report.json"
CACHE_FILE    = OUTPUT_DIR / "validation_cache.json"
DEAD_FILE     = OUTPUT_DIR / "dead_channels.json"
LOGO_CACHE    = OUTPUT_DIR / "logo_cache.json"
GROUPS_FILE   = OUTPUT_DIR / "groups_index.json"

MAX_PAGES     = 10000
API_TIMEOUT   = 30
TIMEOUT       = 15
RETRY_COUNT   = 2
RETRY_DELAY   = 1.5

WORKERS       = 32
CACHE_TTL     = 6 * 3600
LOGO_CACHE_TTL = 24 * 3600
MIN_SEGMENT_BYTES = 64

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# Optional EPG source (leave empty to skip)
EPG_URL = os.environ.get("EPG_URL", "").strip()

STREAM_KEYS = {"stream_url", "play_url", "m3u8_url", "playlist_url",
               "url", "stream", "src", "link"}
LOGO_KEYS = ("logo", "logo_url", "image", "image_url",
             "thumbnail", "thumbnail_url", "icon")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://web.aynaott.com/live-tvs",
    "Origin": "https://web.aynaott.com",
}

PLAY_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
    "Referer": "https://web.aynaott.com/",
    "Origin": "https://web.aynaott.com",
}

IMG_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "image/*,*/*;q=0.8",
}

IPTV_LOGO = ("https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/"
             "refs/heads/main/IPTV_LINKS_LOGO.jpg")
IPTV_VIDEO = ("https://github.com/Mrbotrx/Mrbotrx/raw/"
              "refs/heads/main/IPTV_LINKS_VIDEO.mp4")


# ==========================================
# ⭐ SMART GROUPING — keyword → category
# ==========================================

# Order matters: earlier match wins
GROUP_RULES = [
    ("Sports", [
        "sport", "cricket", "football", "soccer", "tennis", "golf",
        "nba", "nfl", "fifa", "uefa", "f1", "formula", "euro",
        "star sports", "sony ten", "willow", "supersport", "espn",
        "beIN", "sky sport", "bt sport", "eurosport",
    ]),
    ("News", [
        "news", "khobor", "sangbad", "24", "24x7", "cnn", "bbc",
        "aljazeera", "al jazeera", "reuters", "abp", "aaj tak",
        "zee news", "ndtv", "times now", "republic", "india today",
        "somoy", "channel 24", "jamuna", "independent", "ekattor",
        "dbc news", "rttv", "atn news", "btv", "shomoy",
    ]),
    ("Movies", [
        "movie", "cinema", "films", "hbo", "star movie", "sony pix",
        "zee cinema", "star gold", "max", "action", "thriller",
        "cine", "picture",
    ]),
    ("Kids", [
        "kids", "cartoon", "pogo", "nick", "disney", "cn ",
        "cartoon network", "hungama", "baby", "chutti",
    ]),
    ("Music", [
        "music", "song", "mtv", "vh1", "9xm", "b4u music",
        "sangeet", "beat", "hits",
    ]),
    ("Religious", [
        "islam", "quran", "deen", "peace", "madani", "islamic",
        "hindu", "dharm", "sanskar", "aastha", "god", "bhakti",
        "christian", "gospel", "buddha", "jain",
    ]),
    ("Documentary", [
        "discovery", "national geographic", "nat geo", "history",
        "animal planet", "docu", "wild", "nature",
    ]),
    ("Entertainment", [
        "entertainment", "comedy", "drama", "serial", "star plus",
        "zee tv", "sony", "colors", "star jalsha", "zee bangla",
        "sun tv", "vijay", "asianet", "g tv", "star maa",
    ]),
    ("Lifestyle", [
        "food", "travel", "cook", "home", "fashion", "style",
        "tlc", "living", "fox life",
    ]),
    ("Business", [
        "business", "cnbc", "bloomberg", "market", "money",
        "economy", "finance", "stock",
    ]),
    ("Education", [
        "education", "learn", "study", "school", "university",
        "knowledge", "gyan",
    ]),
    ("Local", [
        "bangla", "bangladesh", "bd ", "deshi", "desi",
        "kolkata", "west bengal",
    ]),
]

# Group display order in playlist
GROUP_ORDER = [
    "Sports", "News", "Movies", "Kids", "Music", "Religious",
    "Documentary", "Entertainment", "Lifestyle", "Business",
    "Education", "Local", "Other", "Uncategorized",
]

# Per-group fallback logos (override IPTV_LOGO if you want)
GROUP_LOGOS = {
    "Sports": IPTV_LOGO,
    "News": IPTV_LOGO,
    "Movies": IPTV_LOGO,
    "Kids": IPTV_LOGO,
    "Music": IPTV_LOGO,
    "Religious": IPTV_LOGO,
    # … all fall back to IPTV_LOGO
}


# ==========================================
# ⭐ LANGUAGE / COUNTRY DETECTION
# ==========================================

LANG_RULES = [
    ("bn", ["bangla", "bangladesh", "bengali", "somoy", "jamuna",
            "channel 24", "ekattor", "dbc", "atn", "rttv", "btv",
            "star jalsha", "zee bangla", "colors bangla"]),
    ("hi", ["hindi", "india", "star plus", "zee tv", "sony",
            "colors", "aaj tak", "abp", "ndtv", "star gold"]),
    ("ta", ["tamil", "sun tv", "vijay", "kalaignar", "raj tv"]),
    ("te", ["telugu", "star maa", "gemini", "zee telugu"]),
    ("ur", ["urdu", "pakistan", "geo news", "ary", "hum tv"]),
    ("ar", ["arabic", "al jazeera", "aljazeera", "mbc", "rotana"]),
    ("en", ["english", "bbc", "cnn", "sky news", "discovery",
            "national geographic", "hbo"]),
]

COUNTRY_MAP = {
    "bn": "Bangladesh", "hi": "India", "ta": "India",
    "te": "India", "ur": "Pakistan", "ar": "Saudi Arabia",
    "en": "United States",
}


def auto_group(title: str, api_group: str = "") -> str:
    """Determine smart group from title (fallback to api_group)."""
    t = (title or "").lower()

    for group_name, keywords in GROUP_RULES:
        for kw in keywords:
            if kw.lower() in t:
                return group_name

    # If API group exists and looks reasonable, use it
    if api_group and api_group.lower() not in ("uncategorized", "other", ""):
        return api_group

    return "Other"


def auto_language(title: str) -> str:
    t = (title or "").lower()
    for code, keywords in LANG_RULES:
        for kw in keywords:
            if kw.lower() in t:
                return code
    return ""


def auto_quality(title: str, url: str) -> str:
    """Detect quality tag from title or URL."""
    t = (title or "").lower()
    u = (url or "").lower()
    for tag in ("2160p", "1440p", "1080p", "720p", "576p", "480p", "360p"):
        if tag in t or tag in u:
            return tag
    for tag in ("uhd", "fhd", "hd", "sd"):
        if re.search(rf"\b{tag}\b", t):
            return tag.upper()
    return ""


# ==========================================
# CACHE
# ==========================================

def load_json_cache(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json_cache(path, cache):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[WARN] cache save:", e)


def cache_get(cache, key, ttl):
    e = cache.get(key)
    if not e:
        return None
    if time.time() - e.get("ts", 0) > ttl:
        return None
    return e


# ==========================================
# HTTP
# ==========================================

def http_request(url, headers, method="GET", read_bytes=0, timeout=TIMEOUT):
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                body = resp.read(read_bytes) if read_bytes > 0 else resp.read()
                return resp.status, ct, body, resp.geturl()
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                method = "GET"
                continue
            if e.code in (403, 404, 410):
                return e.code, "", b"", url
            if 400 <= e.code < 500 and e.code != 429:
                return e.code, "", b"", url
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY * attempt)
    return 0, "", b"", url


# ==========================================
# ⭐ LOGO RESOLVER  (multi-source + validate)
# ==========================================

def normalize_logo_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def find_logo_raw(ch) -> str:
    """Pull logo from any known key (no validation)."""
    for k in LOGO_KEYS:
        v = ch.get(k)
        if isinstance(v, str) and v.strip():
            u = normalize_logo_url(v.strip())
            if u.startswith("http"):
                return u
    images = ch.get("images")
    if isinstance(images, dict):
        for v in images.values():
            if isinstance(v, str) and v.strip():
                u = normalize_logo_url(v.strip())
                if u.startswith("http"):
                    return u
            if isinstance(v, dict):
                iu = v.get("url") or v.get("original") or v.get("src")
                if isinstance(iu, str) and iu.strip():
                    u = normalize_logo_url(iu.strip())
                    if u.startswith("http"):
                        return u
    return ""


def validate_logo(url: str, cache: dict) -> bool:
    """HEAD-request logo to confirm it exists and is an image."""
    if not url:
        return False
    c = cache_get(cache, url, LOGO_CACHE_TTL)
    if c is not None:
        return c["ok"]

    st, ct, _, _ = http_request(url, IMG_HEADERS,
                                method="HEAD", read_bytes=0, timeout=8)
    if st == 405:  # HEAD not allowed → GET tiny
        st, ct, _, _ = http_request(url, IMG_HEADERS,
                                    method="GET", read_bytes=1024, timeout=8)
    ok = st in (200, 206) and ("image" in ct or not ct)
    cache[url] = {"ok": ok, "ts": time.time()}
    return ok


def resolve_logo(ch, group: str, logo_cache: dict) -> str:
    """Return a verified logo URL, or fallback."""
    raw = find_logo_raw(ch)
    if raw and validate_logo(raw, logo_cache):
        return raw
    # Group fallback
    return GROUP_LOGOS.get(group, IPTV_LOGO)


# ==========================================
# VALIDATION (stream) — same as before
# ==========================================

def _has_extm3u(body: bytes) -> bool:
    return b"#EXTM3U" in body[:2048]


def _parse_m3u8(body: bytes, base_url: str):
    text = body.decode("utf-8", errors="ignore")
    if "#EXTM3U" not in text:
        return "unknown", []
    is_master = "#EXT-X-STREAM-INF" in text
    is_media  = "#EXTINF" in text or "#EXT-X-TARGETDURATION" in text
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                urls.append(urljoin(base_url, m.group(1)))
            continue
        urls.append(urljoin(base_url, line))
    if is_master:
        return "master", urls
    if is_media:
        return "media", urls
    return "unknown", urls


def validate_stream(url, cache):
    cached = cache_get(cache, url, CACHE_TTL)
    if cached is not None:
        return cached

    result = {"ok": False, "reason": "unknown", "resolved": url,
              "kind": "unknown", "ts": time.time()}

    st, ct, body, final = http_request(url, PLAY_HEADERS, method="GET", read_bytes=8192)
    if st not in (200, 206):
        result["reason"] = f"step1_http_{st or 'err'}"
        cache[url] = result
        return result

    looks_m3u8 = ("mpegurl" in ct or "m3u" in ct
                  or _has_extm3u(body)
                  or url.split("?")[0].endswith(".m3u8"))
    if not looks_m3u8:
        if any(t in ct for t in ("video", "mp4", "mpeg", "octet-stream")):
            result.update(ok=True, reason="direct_video_ok",
                          resolved=final, kind="video")
        else:
            result["reason"] = f"step1_bad_ct:{ct.split(';')[0]}"
        cache[url] = result
        return result

    if not _has_extm3u(body):
        result["reason"] = "step1_no_extm3u"
        cache[url] = result
        return result

    kind, targets = _parse_m3u8(body, final)
    if kind == "unknown" or not targets:
        result["reason"] = f"step1_parse_{kind}"
        cache[url] = result
        return result

    if kind == "master":
        variant = targets[0]
        st2, _, body2, final2 = http_request(variant, PLAY_HEADERS, method="GET", read_bytes=8192)
        if st2 not in (200, 206) or not _has_extm3u(body2):
            result["reason"] = f"step2_variant_{st2 or 'err'}"
            cache[url] = result
            return result
        k2, segs = _parse_m3u8(body2, final2)
        if k2 != "media" or not segs:
            result["reason"] = f"step2_variant_parse_{k2}"
            cache[url] = result
            return result
        targets, kind = segs, "media"

    st3, _, body3, _ = http_request(targets[0], PLAY_HEADERS,
                                    method="GET", read_bytes=MIN_SEGMENT_BYTES)
    if st3 not in (200, 206):
        result["reason"] = f"step3_segment_{st3 or 'err'}"
        cache[url] = result
        return result

    if len(body3) < 16:
        result["reason"] = "step4_empty_segment"
        cache[url] = result
        return result

    result.update(ok=True, reason="all_steps_ok", kind=kind)
    cache[url] = result
    return result


# ==========================================
# HELPERS
# ==========================================

def stream_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def clean_text(v):
    if v is None:
        return ""
    return re.sub(r'[\r\n"]+', " ", str(v)).strip()


def channel_identifier(ch):
    for k in ("id", "slug", "title"):
        v = ch.get(k)
        if v is not None and str(v).strip() != "":
            return f"{k}:{v}"
    return "raw:" + json.dumps(ch, sort_keys=True, ensure_ascii=False)


# ==========================================
# API
# ==========================================

def get_api(url):
    st, _, body, _ = http_request(url, HEADERS, method="GET", timeout=API_TIMEOUT)
    if st != 200 or not body:
        raise RuntimeError(f"API failed: status={st}")
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def get_next_page(data, current_url):
    if not isinstance(data, dict):
        return None
    pag = data.get("blocks_pagination")
    if not isinstance(pag, dict):
        pag = data.get("pagination", {})
    if not isinstance(pag, dict) or not pag.get("has_more"):
        return None
    nxt = pag.get("next_url")
    if not nxt:
        return None
    nxt = urljoin(current_url, nxt)
    p = urlparse(nxt)
    if p.scheme != "https" or p.hostname != "web.aynaott.com":
        raise ValueError(f"Rejected pagination URL: {nxt}")
    return nxt


def extract_channels(data):
    out = []
    if not isinstance(data, dict):
        return out
    for block in data.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        grp = block.get("title") or ""
        for item in block.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            c = dict(item)
            c["_api_group"] = grp
            out.append(c)
    return out


def get_stream_url(ch):
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in STREAM_KEYS:
                    if isinstance(v, str) and v.startswith(("http://", "https://")):
                        return v
                if isinstance(v, (dict, list)):
                    r = walk(v)
                    if r:
                        return r
        elif isinstance(obj, list):
            for it in obj:
                r = walk(it)
                if r:
                    return r
        return None
    return walk(ch)


# ==========================================
# VALIDATION RUNNER
# ==========================================

def validate_all(channels, cache):
    targets = [(stream_hash(get_stream_url(c)), get_stream_url(c),
                c.get("title") or "?")
               for c in channels if get_stream_url(c)]
    results = {}
    total = len(targets)
    done = 0
    print(f"\n[+] Deep-validating {total} streams ({WORKERS} workers)...")

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(validate_stream, u, cache): (k, u, t)
                   for k, u, t in targets}
        for fut in as_completed(futures):
            key, url, title = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"ok": False, "reason": f"exc:{e}",
                     "resolved": url, "kind": "unknown", "ts": time.time()}
            results[key] = r
            done += 1
            flag = "✓" if r["ok"] else "✗"
            print(f"  [{done:>3}/{total}] {flag} {title[:32]:32} → {r['reason']}")
    return results


def validate_logos(channels, group_map, logo_cache):
    """Parallel logo validation."""
    unique_urls = set()
    for ch in channels:
        raw = find_logo_raw(ch)
        if raw:
            unique_urls.add(raw)

    print(f"\n[+] Validating {len(unique_urls)} unique logos "
          f"({WORKERS} workers)...")
    done = 0
    total = len(unique_urls)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(validate_logo, u, logo_cache): u
                   for u in unique_urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                fut.result()
            except Exception:
                pass
            done += 1
            if done % 10 == 0 or done == total:
                print(f"  [{done:>3}/{total}] logos checked")


# ==========================================
# WRITERS
# ==========================================

def save_json(path, data):
    if DRY_RUN:
        print(f"[DRY] skip write: {path}")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    tmp.replace(path)


def _sort_key_for_group(g: str) -> int:
    try:
        return GROUP_ORDER.index(g)
    except ValueError:
        return len(GROUP_ORDER)


def save_playlist(channels, validation, logo_cache):
    """Write only working channels, sorted by group + name."""
    # Enrich + filter
    enriched = []
    seen_streams = set()

    for ch in channels:
        url = get_stream_url(ch)
        if not url:
            continue
        key = stream_hash(url)
        res = validation.get(key)
        if not res or not res.get("ok"):
            continue
        if key in seen_streams:
            continue
        seen_streams.add(key)

        title = clean_text(ch.get("title") or "Unknown Channel")
        api_group = clean_text(ch.get("_api_group") or "")
        group = auto_group(title, api_group)
        language = auto_language(title)
        quality = auto_quality(title, url)
        logo = resolve_logo(ch, group, logo_cache)

        enriched.append({
            "title": title,
            "group": group,
            "language": language,
            "quality": quality,
            "logo": logo,
            "stream": url,
            "key": key,
        })

    # Sort: group priority → name
    enriched.sort(key=lambda x: (_sort_key_for_group(x["group"]),
                                 x["title"].lower()))

    # Group counter for chno
    total = len(enriched)
    tmp = PLAYLIST_FILE.with_suffix(".m3u8.tmp")

    header_attrs = ['#EXTM3U']
    if EPG_URL:
        header_attrs.append(f'x-tvg-url="{EPG_URL}"')
        header_attrs.append(f'url-tvg="{EPG_URL}"')
    header_line = " ".join(header_attrs) + "\n\n"

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(header_line)

            # Fixed first entry
            f.write(
                f'#EXTINF:-1 tvg-id="iptv-links" tvg-name="IPTV LINKS" '
                f'tvg-logo="{IPTV_LOGO}" group-title="KB PRO TV",IPTV LINKS\n'
            )
            f.write(IPTV_VIDEO + "\n\n")

            for idx, e in enumerate(enriched, 1):
                parts = [
                    f'tvg-id="{e["key"]}"',
                    f'tvg-name="{e["title"]}"',
                    f'tvg-logo="{e["logo"]}"',
                    f'group-title="{e["group"]}"',
                    f'tvg-chno="{idx}"',
                ]
                if e["language"]:
                    parts.append(f'tvg-language="{e["language"]}"')
                    country = COUNTRY_MAP.get(e["language"], "")
                    if country:
                        parts.append(f'tvg-country="{country}"')
                if e["quality"]:
                    parts.append(f'tvg-quality="{e["quality"]}"')

                f.write(f'#EXTINF:-1 {" ".join(parts)},{e["title"]}\n')
                f.write(e["stream"] + "\n\n")

        tmp.replace(PLAYLIST_FILE)
    except Exception as e:
        print(f"[FATAL] Playlist write failed: {e}")
        if tmp.exists():
            tmp.unlink()
        raise

    size = PLAYLIST_FILE.stat().st_size
    print(f"\n[OK] Playlist → {PLAYLIST_FILE.resolve()}")
    print(f"[OK] Size     : {size:,} bytes")
    print(f"[OK] Channels : {total}")
    return total, enriched


def save_health(channels, validation, logo_cache):
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "working": 0, "dead": 0, "channels": []}
    for ch in channels:
        url = get_stream_url(ch)
        if not url:
            continue
        key = stream_hash(url)
        res = validation.get(key, {"ok": False, "reason": "not_checked"})
        title = clean_text(ch.get("title") or "?")
        group = auto_group(title, clean_text(ch.get("_api_group") or ""))
        raw_logo = find_logo_raw(ch)
        logo_ok = validate_logo(raw_logo, logo_cache) if raw_logo else False
        report["channels"].append({
            "title": title,
            "group": group,
            "stream": url,
            "ok": res["ok"],
            "reason": res["reason"],
            "logo_raw": raw_logo,
            "logo_valid": logo_ok,
        })
        report["working" if res["ok"] else "dead"] += 1
    save_json(HEALTH_FILE, report)
    print(f"[OK] Health → {HEALTH_FILE}  "
          f"(working={report['working']}, dead={report['dead']})")


def save_groups_index(enriched):
    idx = {}
    for e in enriched:
        idx.setdefault(e["group"], []).append(e["title"])
    # Order by GROUP_ORDER
    ordered = {g: idx[g] for g in sorted(idx, key=_sort_key_for_group)}
    save_json(GROUPS_FILE, ordered)
    print(f"[OK] Groups → {GROUPS_FILE}  ({len(idx)} groups)")


def save_dead_list(validation):
    dead = [{"stream": u, "reason": v["reason"]}
            for u, v in validation.items() if not v.get("ok")]
    save_json(DEAD_FILE, dead)
    print(f"[OK] Dead → {DEAD_FILE}  ({len(dead)} urls)")


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 62)
    print("   BD-KB-IT  ·  ADVANCED  ·  AUTO LOGO + SMART GROUPS")
    print("=" * 62)
    print(f"  Script dir  : {SCRIPT_DIR}")
    print(f"  Output dir  : {OUTPUT_DIR}")
    print(f"  Workers     : {WORKERS}")
    print(f"  EPG URL     : {EPG_URL or '(none)'}")
    print(f"  DRY_RUN     : {DRY_RUN}")
    print("=" * 62)

    for old in OUTPUT_DIR.glob("page_*.json"):
        try:
            old.unlink()
        except OSError:
            pass

    stream_cache = load_json_cache(CACHE_FILE)
    logo_cache   = load_json_cache(LOGO_CACHE)

    all_pages, all_channels = [], []
    visited, current_url, page_number = set(), API_URL, 0

    while current_url and page_number < MAX_PAGES:
        page_number += 1
        if current_url in visited:
            print("[WARN] Pagination loop.")
            break
        visited.add(current_url)

        print(f"\n[+] Page {page_number}: {current_url}")
        data = get_api(current_url)
        all_pages.append(data)
        chans = extract_channels(data)
        all_channels.extend(chans)
        save_json(OUTPUT_DIR / f"page_{page_number:03d}.json", data)
        print(f"    → {len(chans)} channels")

        nxt = get_next_page(data, current_url)
        if not nxt:
            break
        current_url = nxt
        time.sleep(0.4)

    # Dedup
    unique, seen = [], set()
    for ch in all_channels:
        ident = channel_identifier(ch)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(ch)
    print(f"\n[OK] Unique channels: {len(unique)}")

    # Validate streams
    validation = validate_all(unique, stream_cache)

    # Validate logos (parallel)
    validate_logos(unique, None, logo_cache)

    # Save caches
    save_json_cache(CACHE_FILE, stream_cache)
    save_json_cache(LOGO_CACHE, logo_cache)

    # Save data
    save_json(CHANNEL_FILE, unique)
    save_json(RAW_FILE, all_pages)
    save_health(unique, validation, logo_cache)
    save_dead_list(validation)

    # Playlist
    total, enriched = save_playlist(unique, validation, logo_cache)
    save_groups_index(enriched)

    # Summary
    print("\n" + "=" * 62)
    print("                  ✅ UPDATE COMPLETED")
    print("=" * 62)
    print(f"  Pages          : {len(all_pages)}")
    print(f"  Total channels : {len(unique)}")
    print(f"  ✅ Working     : {total}")
    print(f"  ❌ Dead        : {len(unique) - total}")

    # Group summary
    group_count = {}
    for e in enriched:
        group_count[e["group"]] = group_count.get(e["group"], 0) + 1
    print("\n  📁 Groups:")
    for g in sorted(group_count, key=_sort_key_for_group):
        print(f"     {g:20} : {group_count[g]}")

    print("\n[FILES]")
    for f in (PLAYLIST_FILE, CHANNEL_FILE, RAW_FILE, HEALTH_FILE,
              DEAD_FILE, GROUPS_FILE, CACHE_FILE, LOGO_CACHE):
        if f.exists():
            print(f"  ✓ {f}  ({f.stat().st_size:,} bytes)")
        else:
            print(f"  ✗ {f}")

    if not PLAYLIST_FILE.exists():
        raise SystemExit(f"❌ Playlist NOT created: {PLAYLIST_FILE}")
    if total == 0:
        raise SystemExit("⚠ Playlist created but 0 working channels.")

    print(f"\n✅ Main playlist ready → {PLAYLIST_FILE.resolve()}")


if __name__ == "__main__":
    main()
