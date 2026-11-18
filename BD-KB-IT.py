#!/usr/bin/env python3
"""
BD-KB-IT Playlist Builder  (FINAL)
---------------------------------
- Pulls all live channels from web.aynaott.com
- Deep-validates each stream (master → variant → segment → bytes)
- Writes ONLY working channels to output/BD-KB-IT.m3u8
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

# ⭐ Absolute path — ফাইল সবসময় script-এর পাশে output/ ফোল্ডারে যাবে
SCRIPT_DIR  = Path(__file__).resolve().parent
OUTPUT_DIR  = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PLAYLIST_FILE = OUTPUT_DIR / "BD-KB-IT.m3u8"
CHANNEL_FILE  = OUTPUT_DIR / "ALL_CHANNEL_DATA.json"
RAW_FILE      = OUTPUT_DIR / "ALL_API_RESPONSES.json"
HEALTH_FILE   = OUTPUT_DIR / "health_report.json"
CACHE_FILE    = OUTPUT_DIR / "validation_cache.json"
DEAD_FILE     = OUTPUT_DIR / "dead_channels.json"

MAX_PAGES     = 10000
API_TIMEOUT   = 30
TIMEOUT       = 15
RETRY_COUNT   = 2
RETRY_DELAY   = 1.5

WORKERS       = 32
CACHE_TTL     = 6 * 3600
MIN_SEGMENT_BYTES = 64

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

IPTV_LOGO  = ("https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/"
              "refs/heads/main/IPTV_LINKS_LOGO.jpg")
IPTV_VIDEO = ("https://github.com/Mrbotrx/Mrbotrx/raw/"
              "refs/heads/main/IPTV_LINKS_VIDEO.mp4")


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
        print("[WARN] cache save:", e)


def cache_get(cache, url):
    e = cache.get(url)
    if not e:
        return None
    if time.time() - e.get("ts", 0) > CACHE_TTL:
        return None
    return e


# ==========================================
# HTTP
# ==========================================

def http_request(url, headers, method="GET", read_bytes=0, timeout=TIMEOUT):
    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ct = (resp.headers.get("Content-Type") or "").lower()
                body = resp.read(read_bytes) if read_bytes > 0 else resp.read()
                return resp.status, ct, body, resp.geturl()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 405 and method == "HEAD":
                method = "GET"
                continue
            if e.code in (403, 404, 410):
                return e.code, "", b"", url
            if 400 <= e.code < 500 and e.code != 429:
                return e.code, "", b"", url
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY * attempt)
    return 0, "", b"", url


# ==========================================
# API
# ==========================================

def get_api(url):
    st, _, body, _ = http_request(url, HEADERS, method="GET", timeout=API_TIMEOUT)
    if st != 200 or not body:
        raise RuntimeError(f"API failed: status={st} url={url}")
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
        grp = block.get("title") or "Uncategorized"
        for item in block.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            c = dict(item)
            c["_group"] = grp
            out.append(c)
    return out


# ==========================================
# EXTRACTORS
# ==========================================

def get_logo(ch):
    for k in LOGO_KEYS:
        v = ch.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    images = ch.get("images")
    if isinstance(images, dict):
        for v in images.values():
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, dict):
                u = v.get("url") or v.get("original") or v.get("src")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    return ""


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
# DEEP VALIDATION (4 steps)
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
    cached = cache_get(cache, url)
    if cached is not None:
        return cached

    result = {"ok": False, "reason": "unknown", "resolved": url,
              "kind": "unknown", "ts": time.time()}

    # STEP 1
    st, ct, body, final = http_request(url, PLAY_HEADERS, method="GET", read_bytes=8192)
    if st not in (200, 206):
        result["reason"] = f"step1_http_{st or 'err'}"
        cache[url] = result
        return result

    looks_m3u8 = (
        "mpegurl" in ct or "m3u" in ct
        or _has_extm3u(body)
        or url.split("?")[0].endswith(".m3u8")
    )
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

    # STEP 2
    media_url, media_body = final, body
    if kind == "master":
        variant = targets[0]
        st2, ct2, body2, final2 = http_request(
            variant, PLAY_HEADERS, method="GET", read_bytes=8192
        )
        if st2 not in (200, 206) or not _has_extm3u(body2):
            result["reason"] = f"step2_variant_{st2 or 'err'}"
            cache[url] = result
            return result
        k2, segs = _parse_m3u8(body2, final2)
        if k2 != "media" or not segs:
            result["reason"] = f"step2_variant_parse_{k2}"
            cache[url] = result
            return result
        media_url, media_body, targets, kind = final2, body2, segs, "media"

    # STEP 3
    first_seg = targets[0]
    st3, ct3, body3, final3 = http_request(
        first_seg, PLAY_HEADERS, method="GET", read_bytes=MIN_SEGMENT_BYTES
    )
    if st3 not in (200, 206):
        result["reason"] = f"step3_segment_{st3 or 'err'}"
        cache[url] = result
        return result

    # STEP 4
    if len(body3) < 16:
        result["reason"] = "step4_empty_segment"
        cache[url] = result
        return result

    result.update(ok=True, reason="all_steps_ok",
                  resolved=media_url, kind=kind)
    cache[url] = result
    return result


def validate_all(channels, cache):
    targets = []
    for ch in channels:
        u = get_stream_url(ch)
        if not u:
            continue
        targets.append((stream_hash(u), u, ch.get("title") or "?"))

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
# WRITERS  (atomic)
# ==========================================

def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    tmp.replace(path)


def save_playlist(channels, validation):
    total = 0
    seen = set()
    tmp = PLAYLIST_FILE.with_suffix(".m3u8.tmp")

    try:
        with open(tmp, "w", encoding="utf-8") as f:
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
                if not res or not res.get("ok"):
                    continue
                if key in seen:
                    continue
                seen.add(key)

                title = clean_text(ch.get("title") or "Unknown Channel")
                group = clean_text(ch.get("_group") or "Uncategorized")
                logo  = clean_text(get_logo(ch))

                f.write(
                    f'#EXTINF:-1 tvg-id="{key}" tvg-name="{title}" '
                    f'tvg-logo="{logo}" group-title="{group}",{title}\n'
                )
                f.write(url + "\n\n")
                total += 1

        tmp.replace(PLAYLIST_FILE)     # ⭐ atomic
    except Exception as e:
        print(f"[FATAL] Playlist write failed: {e}")
        if tmp.exists():
            tmp.unlink()
        raise

    if not PLAYLIST_FILE.exists():
        raise RuntimeError(f"Playlist missing after write: {PLAYLIST_FILE}")

    size = PLAYLIST_FILE.stat().st_size
    print(f"\n[OK] Playlist → {PLAYLIST_FILE.resolve()}")
    print(f"[OK] Size     : {size:,} bytes")
    print(f"[OK] Working  : {total} channels")
    if total == 0:
        print("[WARNING] 0 working channels — see health_report.json")
    return total


def save_health(channels, validation):
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "working": 0, "dead": 0, "channels": []}
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
            "resolved": res.get("resolved"),
            "kind": res.get("kind"),
        })
        report["working" if res["ok"] else "dead"] += 1
    save_json(HEALTH_FILE, report)
    print(f"[OK] Health → {HEALTH_FILE}  "
          f"(working={report['working']}, dead={report['dead']})")


def save_dead_list(validation):
    dead = [{"stream": u, "reason": v["reason"]}
            for u, v in validation.items() if not v.get("ok")]
    save_json(DEAD_FILE, dead)
    print(f"[OK] Dead list → {DEAD_FILE}  ({len(dead)} urls)")


# ==========================================
# MAIN
# ==========================================

def main():
    print("=" * 60)
    print("     BD-KB-IT  ·  FULLY VALIDATED  M3U8 BUILDER")
    print("=" * 60)
    print(f"  Script dir  : {SCRIPT_DIR}")
    print(f"  Output dir  : {OUTPUT_DIR}")
    print(f"  Workers     : {WORKERS}")
    print("=" * 60)

    for old in OUTPUT_DIR.glob("page_*.json"):
        try:
            old.unlink()
        except OSError:
            pass

    cache = load_cache()
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

    # Dedup
    unique, seen = [], set()
    for ch in all_channels:
        ident = channel_identifier(ch)
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(ch)
    print(f"\n[OK] Unique channels: {len(unique)}")

    # Validate
    validation = validate_all(unique, cache)
    save_cache(cache)

    # Save all
    save_json(CHANNEL_FILE, unique)
    save_json(RAW_FILE, all_pages)
    save_health(unique, validation)
    save_dead_list(validation)
    working = save_playlist(unique, validation)

    # Final summary
    print("\n" + "=" * 60)
    print("                  ✅ UPDATE COMPLETED")
    print("=" * 60)
    print(f"  Pages          : {len(all_pages)}")
    print(f"  Total channels : {len(unique)}")
    print(f"  ✅ Working     : {working}")
    print(f"  ❌ Dead        : {len(unique) - working}")

    print("\n[FILES PRODUCED]")
    for f in (PLAYLIST_FILE, CHANNEL_FILE, RAW_FILE,
              HEALTH_FILE, DEAD_FILE, CACHE_FILE):
        exists = f.exists()
        size = f.stat().st_size if exists else 0
        mark = "✓" if exists else "✗"
        print(f"  {mark} {f}  ({size:,} bytes)")

    # ⭐ Hard fail if playlist not created
    if not PLAYLIST_FILE.exists():
        raise SystemExit(f"❌ Playlist NOT created: {PLAYLIST_FILE}")

    # ⭐ Non-zero exit if 0 working → CI catches it
    if working == 0:
        raise SystemExit("⚠ Playlist created but 0 working channels.")

    print("\n✅ Main playlist ready →", PLAYLIST_FILE.resolve())


if __name__ == "__main__":
    main()
