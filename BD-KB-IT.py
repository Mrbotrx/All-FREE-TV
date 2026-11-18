#!/usr/bin/env python3
"""
BD-KB-IT Playlist Builder — COMPLETE (single file)
==================================================
Features:
  • Full pagination (next_url / page / offset / cursor / total)
  • Deep 4-step stream validation (only working channels)
  • Auto logo resolve + HEAD validation
  • Smart group by keyword
  • Speed measurement (TTFB + segment kB/s) → fast first, slow last
  • Per-channel network-caching hint
  • Atomic file writes, non-zero exit if 0 channels
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
SPEED_FILE    = OUTPUT_DIR / "speed_report.json"

MAX_PAGES      = 10000
API_TIMEOUT    = 30
TIMEOUT        = 15
RETRY_COUNT    = 2
RETRY_DELAY    = 1.5

WORKERS        = 32
CACHE_TTL      = 6 * 3600
LOGO_CACHE_TTL = 24 * 3600
MIN_SEGMENT_BYTES = 64

SPEED_FAST_MS   = 800
SPEED_MEDIUM_MS = 2000
SPEED_SLOW_MS   = 4500

SORT_BY = os.environ.get("SORT_BY", "group_speed")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
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

IPTV_LOGO  = ("https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/"
              "refs/heads/main/IPTV_LINKS_LOGO.jpg")
IPTV_VIDEO = ("https://github.com/Mrbotrx/Mrbotrx/raw/"
              "refs/heads/main/IPTV_LINKS_VIDEO.mp4")


# ==========================================
# GROUPING RULES
# ==========================================

GROUP_RULES = [
    ("Sports", ["sport", "cricket", "football", "soccer", "tennis",
                "golf", "nba", "nfl", "fifa", "uefa", "f1", "formula",
                "euro", "star sports", "sony ten", "willow",
                "supersport", "espn", "bein", "sky sport", "bt sport",
                "eurosport"]),
    ("News", ["news", "khobor", "sangbad", "24x7", "cnn", "bbc",
              "aljazeera", "al jazeera", "reuters", "abp", "aaj tak",
              "zee news", "ndtv", "times now", "republic",
              "india today", "somoy", "jamuna", "independent",
              "ekattor", "dbc news", "rttv", "atn news", "btv",
              "shomoy"]),
    ("Movies", ["movie", "cinema", "films", "hbo", "star movie",
                "sony pix", "zee cinema", "star gold", "max",
                "action", "thriller", "cine", "picture"]),
    ("Kids", ["kids", "cartoon", "pogo", "nick", "disney",
              "cartoon network", "hungama", "baby", "chutti"]),
    ("Music", ["music", "song", "mtv", "vh1", "9xm", "b4u music",
               "sangeet", "beat", "hits"]),
    ("Religious", ["islam", "quran", "deen", "peace", "madani",
                   "islamic", "hindu", "dharm", "sanskar", "aastha",
                   "god", "bhakti", "christian", "gospel", "buddha",
                   "jain"]),
    ("Documentary", ["discovery", "national geographic", "nat geo",
                     "history", "animal planet", "docu", "wild",
                     "nature"]),
    ("Entertainment", ["entertainment", "comedy", "drama", "serial",
                       "star plus", "zee tv", "sony", "colors",
                       "star jalsha", "zee bangla", "sun tv", "vijay",
                       "asianet", "g tv", "star maa"]),
    ("Lifestyle", ["food", "travel", "cook", "home", "fashion",
                   "style", "tlc", "living", "fox life"]),
    ("Business", ["business", "cnbc", "bloomberg", "market", "money",
                  "economy", "finance", "stock"]),
    ("Education", ["education", "learn", "study", "school",
                   "university", "knowledge", "gyan"]),
    ("Local", ["bangla", "bangladesh", "deshi", "desi", "kolkata",
               "west bengal"]),
]

GROUP_ORDER = ["Sports", "News", "Movies", "Kids", "Music", "Religious",
               "Documentary", "Entertainment", "Lifestyle", "Business",
               "Education", "Local", "Other", "Uncategorized"]
GROUP_LOGOS = {}

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
COUNTRY_MAP = {"bn": "Bangladesh", "hi": "India", "ta": "India",
               "te": "India", "ur": "Pakistan", "ar": "Saudi Arabia",
               "en": "United States"}


def auto_group(title, api_group=""):
    t = (title or "").lower()
    for name, kws in GROUP_RULES:
        for kw in kws:
            if kw in t:
                return name
    if api_group and api_group.lower() not in ("uncategorized", "other", ""):
        return api_group
    return "Other"


def auto_language(title):
    t = (title or "").lower()
    for code, kws in LANG_RULES:
        for kw in kws:
            if kw in t:
                return code
    return ""


def auto_quality(title, url):
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

def http_request(url, headers, method="GET", read_bytes=0,
                 timeout=TIMEOUT):
    """Returns (status, ct, body, final_url, elapsed_ms)."""
    for attempt in range(1, RETRY_COUNT + 1):
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                if method == "HEAD":
                    body = b""
                elif read_bytes > 0:
                    body = resp.read(read_bytes)
                else:
                    body = resp.read()
                elapsed_ms = (time.perf_counter() - t0) * 1000
                return resp.status, ct, body, resp.geturl(), elapsed_ms
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if e.code == 405 and method == "HEAD":
                method = "GET"
                continue
            if e.code in (403, 404, 410):
                return e.code, "", b"", url, elapsed_ms
            if 400 <= e.code < 500 and e.code != 429:
                return e.code, "", b"", url, elapsed_ms
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY * attempt)
    return 0, "", b"", url, 0.0


# ==========================================
# API
# ==========================================

def get_api(url):
    st, _, body, _, _ = http_request(url, HEADERS, method="GET",
                                     timeout=API_TIMEOUT)
    if st != 200 or not body:
        raise RuntimeError(f"API failed: status={st} url={url}")
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


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
# ⭐ PAGINATION — universal
# ==========================================

def _find_pagination_dict(data):
    if not isinstance(data, dict):
        return None
    for key in ("blocks_pagination", "pagination", "meta", "metadata",
                "page_info", "paging", "info"):
        c = data.get(key)
        if isinstance(c, dict):
            if key in ("meta", "metadata", "info"):
                for inner in ("pagination", "page_info", "paging"):
                    s = c.get(inner)
                    if isinstance(s, dict):
                        return s
            return c
    inner = data.get("data")
    if isinstance(inner, dict):
        return _find_pagination_dict(inner)
    return None


def _extract_int(pag, *keys):
    for k in keys:
        v = pag.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def _build_page_url(base_url, page):
    p = urlparse(base_url)
    params = [kv for kv in (p.query.split("&") if p.query else [])
              if kv and kv.split("=", 1)[0] not in ("page", "offset")]
    params.append(f"page={page}")
    return p._replace(query="&".join(params)).geturl()


def _build_offset_url(base_url, offset, limit):
    p = urlparse(base_url)
    params = [kv for kv in (p.query.split("&") if p.query else [])
              if kv and kv.split("=", 1)[0] not in ("offset", "limit", "page")]
    params.append(f"offset={offset}")
    if limit:
        params.append(f"limit={limit}")
    return p._replace(query="&".join(params)).geturl()


def get_next_page(data, current_url, ctx):
    pag = _find_pagination_dict(data)

    if pag:
        # 1) explicit next_url
        nxt = pag.get("next_url") or pag.get("next") or pag.get("next_page_url")
        if isinstance(nxt, str) and nxt.strip():
            ctx["type"] = "next_url"
            full = urljoin(current_url, nxt.strip())
            p = urlparse(full)
            if p.scheme not in ("http", "https"):
                return None
            if p.hostname and "aynaott.com" not in p.hostname:
                print(f"[WARN] External next_url rejected: {full}")
                return None
            return full

        if pag.get("has_more") is False:
            return None

        # 2) cursor
        cursor = pag.get("next_cursor") or pag.get("cursor")
        if isinstance(cursor, str) and cursor:
            ctx["type"] = "cursor"
            p = urlparse(ctx["base_url"])
            params = [kv for kv in (p.query.split("&") if p.query else [])
                      if kv and kv.split("=", 1)[0] not in ("cursor", "next_cursor")]
            params.append(f"cursor={cursor}")
            return p._replace(query="&".join(params)).geturl()

        # 3) total + current_page / last_page
        total = _extract_int(pag, "total", "total_count", "count")
        last_page = _extract_int(pag, "last_page", "total_pages", "pages")
        current_page = _extract_int(pag, "current_page", "page", "page_number")
        per_page = _extract_int(pag, "per_page", "page_size", "limit")

        if last_page and current_page:
            ctx["type"] = "page"
            if current_page < last_page:
                return _build_page_url(ctx["base_url"], current_page + 1)
            return None

        if total and per_page:
            ctx["type"] = "page"
            pages = (total + per_page - 1) // per_page
            if current_page and current_page < pages:
                return _build_page_url(ctx["base_url"], current_page + 1)
            return None

        # 4) offset
        offset = _extract_int(pag, "offset", "start")
        limit = _extract_int(pag, "limit", "per_page", "page_size")
        if offset is not None and limit:
            if total and offset + limit >= total:
                return None
            ctx["type"] = "offset"
            return _build_offset_url(ctx["base_url"], offset + limit, limit)

    return None


# ==========================================
# LOGO
# ==========================================

def normalize_logo_url(url):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def find_logo_raw(ch):
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


def validate_logo(url, cache):
    if not url:
        return False
    c = cache_get(cache, url, LOGO_CACHE_TTL)
    if c is not None:
        return c["ok"]
    st, ct, _, _, _ = http_request(url, IMG_HEADERS, method="HEAD", timeout=8)
    if st == 405:
        st, ct, _, _, _ = http_request(url, IMG_HEADERS, method="GET",
                                       read_bytes=1024, timeout=8)
    ok = st in (200, 206) and ("image" in ct or not ct)
    cache[url] = {"ok": ok, "ts": time.time()}
    return ok


def resolve_logo(ch, group, logo_cache):
    raw = find_logo_raw(ch)
    if raw and validate_logo(raw, logo_cache):
        return raw
    return GROUP_LOGOS.get(group, IPTV_LOGO)


# ==========================================
# STREAM VALIDATION + SPEED
# ==========================================

def _has_extm3u(body):
    return b"#EXTM3U" in body[:2048]


def _parse_m3u8(body, base_url):
    text = body.decode("utf-8", errors="ignore")
    if "#EXTM3U" not in text:
        return "unknown", []
    is_master = "#EXT-X-STREAM-INF" in text
    is_media = "#EXTINF" in text or "#EXT-X-TARGETDURATION" in text
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


def speed_tier(ttfb_ms):
    if ttfb_ms <= 0:
        return "very_slow"
    if ttfb_ms < SPEED_FAST_MS:
        return "fast"
    if ttfb_ms < SPEED_MEDIUM_MS:
        return "medium"
    if ttfb_ms < SPEED_SLOW_MS:
        return "slow"
    return "very_slow"


def caching_hint(tier):
    return {"fast": 500, "medium": 1500, "slow": 3000,
            "very_slow": 5000}.get(tier, 2000)


def validate_stream(url, cache):
    cached = cache_get(cache, url, CACHE_TTL)
    if cached is not None:
        return cached

    result = {"ok": False, "reason": "unknown", "resolved": url,
              "kind": "unknown", "ts": time.time(),
              "ttfb_ms": 0, "seg_kbps": 0, "tier": "very_slow"}

    t0 = time.perf_counter()
    st, ct, body, final, _ = http_request(url, PLAY_HEADERS, method="GET",
                                          read_bytes=8192)
    ttfb_ms = (time.perf_counter() - t0) * 1000
    result["ttfb_ms"] = round(ttfb_ms, 1)

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
                          resolved=final, kind="video",
                          tier=speed_tier(ttfb_ms))
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
        st2, _, body2, final2, _ = http_request(variant, PLAY_HEADERS,
                                                method="GET", read_bytes=8192)
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

    seg_bytes = 64 * 1024
    t1 = time.perf_counter()
    st3, _, body3, _, _ = http_request(targets[0], PLAY_HEADERS,
                                       method="GET", read_bytes=seg_bytes,
                                       timeout=TIMEOUT)
    seg_dur = time.perf_counter() - t1
    if st3 not in (200, 206):
        result["reason"] = f"step3_segment_{st3 or 'err'}"
        cache[url] = result
        return result
    if len(body3) < 16:
        result["reason"] = "step4_empty_segment"
        cache[url] = result
        return result

    if seg_dur > 0:
        result["seg_kbps"] = round((len(body3) / 1024) / seg_dur, 1)

    result["tier"] = speed_tier(ttfb_ms)
    result.update(ok=True, reason="all_steps_ok", kind=kind)
    cache[url] = result
    return result


def validate_all(channels, cache):
    targets = [(stream_hash(get_stream_url(c)), get_stream_url(c),
                c.get("title") or "?")
               for c in channels if get_stream_url(c)]
    results = {}
    total = len(targets)
    done = 0
    print(f"\n[+] Validating + measuring speed for {total} streams...")

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(validate_stream, u, cache): (k, u, t)
                   for k, u, t in targets}
        for fut in as_completed(futures):
            key, url, title = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"ok": False, "reason": f"exc:{e}",
                     "resolved": url, "kind": "unknown",
                     "ts": time.time(), "ttfb_ms": 0,
                     "seg_kbps": 0, "tier": "very_slow"}
            results[key] = r
            done += 1
            flag = "✓" if r["ok"] else "✗"
            spd = (f"{r['ttfb_ms']:>5.0f}ms "
                   f"{r['seg_kbps']:>6.0f}KB/s [{r['tier']}]"
                   if r["ok"] else r["reason"])
            print(f"  [{done:>3}/{total}] {flag} {title[:28]:28} → {spd}")
    return results


def validate_logos(channels, logo_cache):
    unique = {find_logo_raw(ch) for ch in channels} - {""}
    print(f"\n[+] Validating {len(unique)} unique logos...")
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(validate_logo, u, logo_cache): u for u in unique}
        for f in as_completed(futs):
            try:
                f.result()
            except Exception:
                pass
            done += 1
    print(f"  [{done}/{len(unique)}] logos done")


# ==========================================
# HELPERS
# ==========================================

def stream_hash(url):
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


def _group_rank(g):
    try:
        return GROUP_ORDER.index(g)
    except ValueError:
        return len(GROUP_ORDER)


def _tier_rank(t):
    return {"fast": 0, "medium": 1, "slow": 2, "very_slow": 3}.get(t, 4)


def sort_key_for_channel(e):
    if SORT_BY == "speed":
        return (_tier_rank(e["tier"]), e["ttfb_ms"], e["title"].lower())
    if SORT_BY == "group":
        return (_group_rank(e["group"]), e["title"].lower())
    return (_group_rank(e["group"]), _tier_rank(e["tier"]),
            e["ttfb_ms"], e["title"].lower())


def save_playlist(channels, validation, logo_cache):
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
        tier = res.get("tier", "very_slow")

        enriched.append({
            "title": title, "group": group,
            "language": language, "quality": quality,
            "logo": logo, "stream": url, "key": key,
            "tier": tier, "ttfb_ms": res.get("ttfb_ms", 0),
            "seg_kbps": res.get("seg_kbps", 0),
            "caching": caching_hint(tier),
        })

    enriched.sort(key=sort_key_for_channel)
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
                    f'tvg-speed="{e["tier"]}"',
                ]
                if e["language"]:
                    parts.append(f'tvg-language="{e["language"]}"')
                    c = COUNTRY_MAP.get(e["language"], "")
                    if c:
                        parts.append(f'tvg-country="{c}"')
                if e["quality"]:
                    parts.append(f'tvg-quality="{e["quality"]}"')

                f.write(f'#EXTVLCOPT:network-caching={e["caching"]}\n')
                f.write(f'#EXTINF:-1 {" ".join(parts)},{e["title"]}\n')
                f.write(e["stream"] + "\n\n")

        tmp.replace(PLAYLIST_FILE)
    except Exception as ex:
        print(f"[FATAL] Playlist write failed: {ex}")
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
        res = validation.get(key, {"ok": False, "reason": "not_checked",
                                    "ttfb_ms": 0, "tier": "very_slow"})
        title = clean_text(ch.get("title") or "?")
        group = auto_group(title, clean_text(ch.get("_api_group") or ""))
        raw_logo = find_logo_raw(ch)
        logo_ok = validate_logo(raw_logo, logo_cache) if raw_logo else False
        report["channels"].append({
            "title": title, "group": group, "stream": url,
            "ok": res["ok"], "reason": res["reason"],
            "ttfb_ms": res.get("ttfb_ms", 0),
            "seg_kbps": res.get("seg_kbps", 0),
            "tier": res.get("tier", "very_slow"),
            "logo_raw": raw_logo, "logo_valid": logo_ok,
        })
        report["working" if res["ok"] else "dead"] += 1
    save_json(HEALTH_FILE, report)
    print(f"[OK] Health → {HEALTH_FILE}")


def save_speed_report(enriched):
    data = [{"title": e["title"], "group": e["group"],
             "tier": e["tier"], "ttfb_ms": e["ttfb_ms"],
             "seg_kbps": e["seg_kbps"], "stream": e["stream"]}
            for e in enriched]
    data.sort(key=lambda x: (x["ttfb_ms"], x["title"].lower()))
    save_json(SPEED_FILE, data)
    print(f"[OK] Speed  → {SPEED_FILE}  ({len(data)} entries)")


def save_groups_index(enriched):
    idx = {}
    for e in enriched:
        idx.setdefault(e["group"], []).append(e["title"])
    ordered = {g: idx[g] for g in sorted(idx, key=_group_rank)}
    save_json(GROUPS_FILE, ordered)
    print(f"[OK] Groups → {GROUPS_FILE}  ({len(idx)} groups)")


def save_dead_list(validation):
    dead = [{"stream": u, "reason": v["reason"]}
            for u, v in validation.items() if not v.get("ok")]
    save_json(DEAD_FILE, dead)
    print(f"[OK] Dead   → {DEAD_FILE}  ({len(dead)} urls)")


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 64)
    print("   BD-KB-IT  ·  FULL SCAN + VALIDATE + SPEED SORT")
    print("=" * 64)
    print(f"  API          : {API_URL}")
    print(f"  Max pages    : {MAX_PAGES}")
    print(f"  Sort         : {SORT_BY}")
    print(f"  Workers      : {WORKERS}")
    print("=" * 64)

    for old in OUTPUT_DIR.glob("page_*.json"):
        try:
            old.unlink()
        except OSError:
            pass

    stream_cache = load_json_cache(CACHE_FILE)
    logo_cache = load_json_cache(LOGO_CACHE)

    all_pages, all_channels = [], []
    visited_urls = set()
    seen_page_hashes = set()
    empty_streak = 0

    ctx = {"type": None, "page": 1, "offset": 0, "limit": None,
           "cursor": None, "base_url": API_URL, "last_page": None}

    current_url = API_URL
    page_number = 0
    stop_reason = "unknown"
    cumulative = 0

    while current_url and page_number < MAX_PAGES:
        page_number += 1

        if current_url in visited_urls:
            print(f"\n[STOP] URL loop at page {page_number}")
            stop_reason = "url_loop"
            break
        visited_urls.add(current_url)

        print(f"\n[+] Page {page_number:>3}: {current_url}")

        try:
            data = get_api(current_url)
        except Exception as e:
            print(f"[ERROR] Page {page_number}: {e}")
            if ctx["type"] == "page":
                current_url = _build_page_url(ctx["base_url"], page_number + 1)
                continue
            stop_reason = f"error:{e}"
            break

        try:
            ph = hashlib.sha256(
                json.dumps(data, sort_keys=True).encode()
            ).hexdigest()
        except Exception:
            ph = None
        if ph and ph in seen_page_hashes:
            print(f"\n[STOP] Duplicate page content at page {page_number}")
            stop_reason = "duplicate_content"
            break
        if ph:
            seen_page_hashes.add(ph)

        all_pages.append(data)
        chans = extract_channels(data)
        all_channels.extend(chans)
        cumulative += len(chans)

        save_json(OUTPUT_DIR / f"page_{page_number:03d}.json", data)
        print(f"    → {len(chans)} channels (cumulative: {cumulative})")

        if len(chans) == 0:
            empty_streak += 1
            if empty_streak >= 3:
                print(f"\n[STOP] {empty_streak} empty pages in a row")
                stop_reason = "empty_streak"
                break
        else:
            empty_streak = 0

        nxt = get_next_page(data, current_url, ctx)
        if not nxt:
            print("\n[+] No further pages")
            stop_reason = "no_next_url"
            break
        if nxt == current_url:
            print("\n[STOP] next_url == current_url")
            stop_reason = "self_reference"
            break

        current_url = nxt
        time.sleep(0.35)

    if page_number >= MAX_PAGES and current_url:
        stop_reason = "max_pages_reached"
        print(f"\n[WARN] Hit MAX_PAGES={MAX_PAGES}")

    # Pagination summary
    print("\n" + "─" * 64)
    print("[PAGINATION SUMMARY]")
    print(f"  Pages scanned   : {page_number}")
    print(f"  Pages saved     : {len(all_pages)}")
    print(f"  Total channels  : {len(all_channels)}")
    print(f"  Pagination type : {ctx['type'] or 'none'}")
    print(f"  Terminated by   : {stop_reason}")
    print("─" * 64)

    if len(all_pages) == 0:
        raise SystemExit("❌ No pages fetched — aborting")

    # Dedup
    unique, seen = [], set()
    for ch in all_channels:
        ident = channel_identifier(ch)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(ch)
    print(f"\n[OK] Unique channels after dedup: {len(unique)}")

    validation = validate_all(unique, stream_cache)
    validate_logos(unique, logo_cache)

    save_json_cache(CACHE_FILE, stream_cache)
    save_json_cache(LOGO_CACHE, logo_cache)

    save_json(CHANNEL_FILE, unique)
    save_json(RAW_FILE, all_pages)
    save_health(unique, validation, logo_cache)
    save_dead_list(validation)

    total, enriched = save_playlist(unique, validation, logo_cache)
    save_groups_index(enriched)
    save_speed_report(enriched)

    # Final summary
    print("\n" + "=" * 64)
    print("                  ✅ UPDATE COMPLETED")
    print("=" * 64)
    print(f"  Pages scanned  : {page_number}")
    print(f"  Total channels : {len(unique)}")
    print(f"  ✅ Working     : {total}")

    tier_count = {}
    for e in enriched:
        tier_count[e["tier"]] = tier_count.get(e["tier"], 0) + 1
    print("\n  ⚡ Speed distribution:")
    for tier in ("fast", "medium", "slow", "very_slow"):
        print(f"     {tier:10} : {tier_count.get(tier, 0)}")

    group_count = {}
    for e in enriched:
        group_count[e["group"]] = group_count.get(e["group"], 0) + 1
    print("\n  📁 Groups:")
    for g in sorted(group_count, key=_group_rank):
        print(f"     {g:20} : {group_count[g]}")

    if enriched:
        fst = min(enriched, key=lambda e: e["ttfb_ms"])
        slw = max(enriched, key=lambda e: e["ttfb_ms"])
        print(f"\n  🚀 Fastest : {fst['title']} ({fst['ttfb_ms']:.0f}ms)")
        print(f"  🐌 Slowest : {slw['title']} ({slw['ttfb_ms']:.0f}ms)")

    print(f"\n✅ Playlist → {PLAYLIST_FILE.resolve()}")
    if total == 0:
        raise SystemExit("⚠ 0 working channels.")


if __name__ == "__main__":
    main()
