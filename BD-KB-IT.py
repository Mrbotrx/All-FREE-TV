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

OUTPUT_DIR = Path("output")
PLAYLIST_FILE = OUTPUT_DIR / "BD-KB-IT.m3u8"
CHANNEL_FILE = OUTPUT_DIR / "ALL_CHANNEL_DATA.json"
RAW_FILE = OUTPUT_DIR / "ALL_API_RESPONSES.json"
HEALTH_FILE = OUTPUT_DIR / "health_report.json"
CACHE_FILE = OUTPUT_DIR / "validation_cache.json"

MAX_PAGES = 10000
TIMEOUT = 30
RETRY_COUNT = 2
RETRY_DELAY = 2

# Concurrency
WORKERS = 24
VALIDATE_STREAM = True
VALIDATE_SEGMENTS = True      # deeper check — first byte of first segment
CACHE_TTL = 6 * 3600          # 6 hours

ONLY_WORKING = os.environ.get("ONLY_WORKING", "1") == "1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0 Safari/537.36",
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

IPTV_LOGO = ("https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/"
             "refs/heads/main/IPTV_LINKS_LOGO.jpg")
IPTV_VIDEO = ("https://github.com/Mrbotrx/Mrbotrx/raw/"
              "refs/heads/main/IPTV_LINKS_VIDEO.mp4")

STREAM_KEYS = {"stream_url", "play_url", "m3u8_url", "playlist_url"}
LOGO_KEYS = ("logo", "logo_url", "image", "image_url",
             "thumbnail", "thumbnail_url", "icon")

VALID_CT_FRAGMENTS = ("mpegurl", "m3u", "mp2t", "mp4", "octet-stream", "video")


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# CACHE
# ==========================================

def load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[WARNING] Cache save failed:", e)


def cache_get(cache, url):
    entry = cache.get(url)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > CACHE_TTL:
        return None
    return entry


# ==========================================
# HTTP HELPERS
# ==========================================

def http_request(url, headers, method="GET", read_bytes=0, timeout=TIMEOUT):
    """
    Returns (status, content_type, body_snippet, final_url).
    Retries network / 5xx / 429.
    """
    last_error = None

    for attempt in range(1, RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                ct = (resp.headers.get("Content-Type") or "").lower()
                body = b""
                if read_bytes > 0:
                    body = resp.read(read_bytes)
                else:
                    body = resp.read()
                return status, ct, body, resp.geturl()

        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 405 and method == "HEAD":
                # Some servers reject HEAD → retry with GET
                method = "GET"
                continue
            if 400 <= e.code < 500 and e.code != 429:
                return e.code, "", b"", url
            print(f"[WARN] HTTP {e.code} {url} (try {attempt}/{RETRY_COUNT})")

        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            print(f"[WARN] Net err {url}: {e} (try {attempt}/{RETRY_COUNT})")

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY * attempt)

    return 0, "", b"", url


# ==========================================
# API
# ==========================================

def get_api(url):
    status, _, body, _ = http_request(url, HEADERS, method="GET", read_bytes=0)
    if status != 200 or not body:
        raise RuntimeError(f"API failed: status={status} url={url}")
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from {url}: {e}")


def get_next_page(data, current_url):
    if not isinstance(data, dict):
        return None
    pagination = data.get("blocks_pagination")
    if not isinstance(pagination, dict):
        pagination = data.get("pagination", {})
    if not isinstance(pagination, dict):
        return None
    if not pagination.get("has_more", False):
        return None
    next_url = pagination.get("next_url")
    if not next_url:
        print("[WARNING] has_more=True but no next_url.")
        return None
    next_url = urljoin(current_url, next_url)
    p = urlparse(next_url)
    if p.scheme != "https" or p.hostname != "web.aynaott.com":
        raise ValueError(f"Rejected pagination URL: {next_url}")
    return next_url


def extract_channels(data):
    channels = []
    if not isinstance(data, dict):
        return channels
    for block in data.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        group = block.get("title") or "Uncategorized"
        for item in block.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            c = dict(item)
            c["_group"] = group
            channels.append(c)
    return channels


# ==========================================
# LOGO / STREAM URL EXTRACTION
# ==========================================

def get_logo(channel):
    for key in LOGO_KEYS:
        v = channel.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    images = channel.get("images")
    if isinstance(images, dict):
        for v in images.values():
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, dict):
                iu = v.get("url") or v.get("original") or v.get("src")
                if isinstance(iu, str) and iu.startswith("http"):
                    return iu
    return ""


def get_stream_url(channel):
    def search(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in STREAM_KEYS:
                    if isinstance(v, str) and v.startswith(("http://", "https://")):
                        return v
                if isinstance(v, (dict, list)):
                    r = search(v)
                    if r:
                        return r
        elif isinstance(obj, list):
            for it in obj:
                r = search(it)
                if r:
                    return r
        return None
    return search(channel)


# ==========================================
# STREAM VALIDATION  ⭐ (core of "working channel")
# ==========================================

def _looks_like_m3u8(body: bytes) -> bool:
    try:
        text = body.decode("utf-8", errors="ignore")
    except Exception:
        return False
    return "#EXTM3U" in text


def _first_sub_playlist(body: bytes, base_url: str) -> str | None:
    """Return first variant playlist or segment URL found inside an m3u8."""
    text = body.decode("utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            # allow absolute URI inside #EXT-X-MEDIA / #EXT-X-KEY
            m = re.search(r'URI="([^"]+)"', line)
            if m:
                return urljoin(base_url, m.group(1))
            continue
        return urljoin(base_url, line)
    return None


def validate_stream(url, cache):
    """
    Returns dict:
      {ok: bool, reason: str, resolved: url, checked_at: ts}
    Checks:
      1. GET first ~4KB — status 200/206
      2. If m3u8 → parse, maybe follow one sub-playlist and probe first segment
      3. If video content-type → OK
    """
    cached = cache_get(cache, url)
    if cached is not None:
        return cached

    result = {"ok": False, "reason": "unknown", "resolved": url,
              "ts": time.time()}

    status, ct, body, final = http_request(
        url, PLAY_HEADERS, method="GET", read_bytes=4096
    )

    if status not in (200, 206):
        result["reason"] = f"http_{status}"
        cache[url] = result
        return result

    is_m3u8 = (
        "mpegurl" in ct
        or "m3u" in ct
        or _looks_like_m3u8(body)
        or url.split("?")[0].endswith(".m3u8")
    )

    if is_m3u8:
        if not _looks_like_m3u8(body):
            result["reason"] = "m3u8_header_missing"
            cache[url] = result
            return result

        result["ok"] = True
        result["reason"] = "m3u8_ok"
        result["resolved"] = final

        # Deep probe: follow one sub-playlist/segment.
        if VALIDATE_SEGMENTS:
            sub = _first_sub_playlist(body, final)
            if sub:
                s2, ct2, body2, f2 = http_request(
                    sub, PLAY_HEADERS, method="GET", read_bytes=2048
                )
                if s2 not in (200, 206) or not body2:
                    result["ok"] = False
                    result["reason"] = f"segment_{s2 or 'err'}"
        cache[url] = result
        return result

    # Non-m3u8 — accept only if content-type hints at video.
    if any(frag in ct for frag in VALID_CT_FRAGMENTS):
        result["ok"] = True
        result["reason"] = f"video_ok:{ct.split(';')[0]}"
        result["resolved"] = final
        cache[url] = result
        return result

    result["reason"] = f"bad_ct:{ct.split(';')[0] or 'none'}"
    cache[url] = result
    return result


def validate_all(channels, cache):
    """Parallel validation, returns {channel_key: result}."""
    targets = []
    for ch in channels:
        url = get_stream_url(ch)
        if not url:
            continue
        key = stream_hash(url)
        targets.append((key, url, ch.get("title") or "?"))

    results = {}
    total = len(targets)
    done = 0
    print(f"\n[+] Validating {total} streams with {WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(validate_stream, u, cache): (k, u, t)
                   for k, u, t in targets}
        for fut in as_completed(futures):
            key, url, title = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"ok": False, "reason": f"exc:{e}",
                       "resolved": url, "ts": time.time()}
            results[key] = res
            done += 1
            flag = "✓" if res["ok"] else "✗"
            print(f"  [{done}/{total}] {flag} {title[:30]:30} "
                  f"({res['reason']})")
    return results


# ==========================================
# HELPERS
# ==========================================

def stream_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


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
# OUTPUT
# ==========================================

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def save_playlist(channels, validation):
    total = 0
    seen_streams = set()

    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        f.write(
            f'#EXTINF:-1 tvg-id="" tvg-name="IPTV LINKS" '
            f'tvg-logo="{IPTV_LOGO}" group-title="KB PRO TV",IPTV LINKS\n'
        )
        f.write(IPTV_VIDEO + "\n\n")

        for ch in channels:
            url = get_stream_url(ch)
            if not url:
                continue

            key = stream_hash(url)
            res = validation.get(key)

            if ONLY_WORKING:
                if not res or not res.get("ok"):
                    continue

            if key in seen_streams:
                continue
            seen_streams.add(key)

            title = clean_text(ch.get("title") or "Unknown Channel")
            group = clean_text(ch.get("_group") or "Uncategorized")
            logo = clean_text(get_logo(ch))
            tvg_id = key

            f.write(
                f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{title}" '
                f'tvg-logo="{logo}" group-title="{group}",{title}\n'
            )
            f.write(url + "\n\n")
            total += 1

    print(f"[OK] Playlist: {PLAYLIST_FILE}")
    print(f"[OK] Included channels: {total}")
    if total == 0:
        print("[WARNING] No working channels — playlist is empty (only header).")
    return total


def save_health(channels, validation):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "only_working": ONLY_WORKING,
        "channels": [],
    }
    for ch in channels:
        url = get_stream_url(ch)
        if not url:
            continue
        key = stream_hash(url)
        res = validation.get(key, {"ok": False, "reason": "not_checked"})
        report["channels"].append({
            "title": ch.get("title"),
            "group": ch.get("_group"),
            "stream": url,
            "ok": res["ok"],
            "reason": res["reason"],
        })
    save_json(HEALTH_FILE, report)
    print(f"[OK] Health report: {HEALTH_FILE}")


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 55)
    print("        BD-KB-IT PLAYLIST BUILDER (ADVANCED)")
    print("=" * 55)
    print(f"  Validate streams : {VALIDATE_STREAM}")
    print(f"  Deep segment probe: {VALIDATE_SEGMENTS}")
    print(f"  Only working      : {ONLY_WORKING}")
    print(f"  Workers           : {WORKERS}")
    print("=" * 55)

    for old in OUTPUT_DIR.glob("page_*.json"):
        try:
            old.unlink()
        except OSError:
            pass

    cache = load_cache()
    all_pages, all_channels = [], []
    visited = set()
    current_url = API_URL
    page_number = 0

    while current_url and page_number < MAX_PAGES:
        page_number += 1
        if current_url in visited:
            print("[WARNING] Pagination loop.")
            break
        visited.add(current_url)

        print(f"\n[+] Page {page_number}: {current_url}")
        data = get_api(current_url)
        if not isinstance(data, dict):
            raise ValueError("Invalid API response")
        all_pages.append(data)

        chans = extract_channels(data)
        all_channels.extend(chans)
        save_json(OUTPUT_DIR / f"page_{page_number:03d}.json", data)
        print(f"    → {len(chans)} channels")

        nxt = get_next_page(data, current_url)
        if not nxt:
            print("[+] No more pages.")
            break
        current_url = nxt
        time.sleep(0.4)

    # Deduplicate
    unique, seen = [], set()
    for ch in all_channels:
        ident = channel_identifier(ch)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(ch)

    print(f"\n[OK] Total unique channels: {len(unique)}")

    # Validate
    validation = {}
    if VALIDATE_STREAM:
        validation = validate_all(unique, cache)
        save_cache(cache)

    # Outputs
    save_json(CHANNEL_FILE, unique)
    save_json(RAW_FILE, all_pages)
    save_health(unique, validation)
    playable = save_playlist(unique, validation)

    print("\n" + "=" * 55)
    print("             UPDATE COMPLETED")
    print("=" * 55)
    print(f"Pages           : {len(all_pages)}")
    print(f"Total channels  : {len(unique)}")
    print(f"Playable in M3U : {playable}")
    print("=" * 55)


if __name__ == "__main__":
    main()
