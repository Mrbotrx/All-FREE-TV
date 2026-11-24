#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BD-KB-IT VIP PLAYLIST ENGINE
FULL SCAN + NEXT_URL + EXTRACTION + VALIDATION + SPEED SORT
"""

import os
import re
import json
import time
import hashlib
import urllib.request
import urllib.error

from pathlib import Path
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone


# =====================================================
# CONFIGURATION
# =====================================================

API_URL = os.environ.get(
    "BD_KB_IT_API_URL",
    "https://web.aynaott.com/api/v5/pages/live-tvs/"
)

API_HOST = "web.aynaott.com"

MAX_PAGES = 10000
API_TIMEOUT = 30
STREAM_TIMEOUT = 15

WORKERS = 32
RETRIES = 2
RETRY_DELAY = 1.5

CACHE_TTL = 21600
CACHE_VERSION = 3

SORT_BY = os.environ.get("SORT_BY", "group_speed")

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

EPG_URL = os.environ.get("EPG_URL", "")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PLAYLIST_FILE = OUTPUT_DIR / "BD-KB-IT.m3u8"
CHANNEL_FILE = OUTPUT_DIR / "ALL_CHANNEL_DATA.json"
RAW_FILE = OUTPUT_DIR / "ALL_API_RESPONSES.json"

HEALTH_FILE = OUTPUT_DIR / "health_report.json"
CACHE_FILE = OUTPUT_DIR / "validation_cache.json"
DEAD_FILE = OUTPUT_DIR / "dead_channels.json"
LOGO_CACHE = OUTPUT_DIR / "logo_cache.json"

GROUPS_FILE = OUTPUT_DIR / "groups_index.json"
SPEED_FILE = OUTPUT_DIR / "speed_report.json"

IPTV_LOGO = (
    "https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/"
    "refs/heads/main/IPTV_LINKS_LOGO.jpg"
)

IPTV_VIDEO = (
    "https://github.com/Mrbotrx/Mrbotrx/raw/"
    "refs/heads/main/IPTV_LINKS_VIDEO.mp4"
)


# =====================================================
# HEADERS
# =====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://web.aynaott.com/live-tvs",
    "Origin": "https://web.aynaott.com",
}

STREAM_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/vnd.apple.mpegurl, "
              "application/x-mpegURL, */*",
    "Referer": "https://web.aynaott.com/",
}

IMAGE_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "image/*,*/*",
}


# =====================================================
# FIELD DEFINITIONS
# =====================================================

STREAM_KEYS = {
    "stream_url",
    "play_url",
    "m3u8_url",
    "playlist_url",
    "url",
    "stream",
    "src",
    "link",
    "hls",
    "hls_url",
    "playback_url",
    "content_url",
    "manifest_url",
}

TITLE_KEYS = (
    "title",
    "name",
    "channel_name",
    "channelName",
    "display_name",
    "displayName",
)

LOGO_KEYS = (
    "logo",
    "logo_url",
    "image",
    "image_url",
    "thumbnail",
    "thumbnail_url",
    "icon",
    "poster",
    "cover",
)

GROUP_KEYS = (
    "group_title",
    "category_name",
    "category",
    "group",
)


# =====================================================
# GROUP RULES
# =====================================================

GROUP_RULES = {
    "Sports": [
        "sport", "cricket", "football", "soccer",
        "tennis", "fifa", "uefa", "espn",
        "sony ten", "star sports", "bein",
        "willow", "nba", "f1",
    ],

    "News": [
        "news", "cnn", "bbc", "aljazeera",
        "somoy", "jamuna", "dbc", "ekattor",
        "ndtv", "aaj tak", "republic",
    ],

    "Movies": [
        "movie", "cinema", "hbo", "star gold",
        "sony pix", "zee cinema", "film",
    ],

    "Kids": [
        "kids", "cartoon", "disney", "nick",
        "pogo", "hungama",
    ],

    "Music": [
        "music", "mtv", "vh1", "9xm",
        "b4u music",
    ],

    "Religious": [
        "islam", "quran", "religious",
        "madani", "aastha", "bhakti",
    ],

    "Documentary": [
        "discovery", "national geographic",
        "history", "animal planet",
    ],

    "Entertainment": [
        "entertainment", "serial", "drama",
        "star plus", "zee tv", "sony",
        "colors", "star jalsha", "zee bangla",
    ],

    "Local": [
        "bangla", "bangladesh", "bengali",
        "deshi", "kolkata", "west bengal",
        "btv",
    ],
}

GROUP_ORDER = [
    "Sports",
    "News",
    "Movies",
    "Kids",
    "Music",
    "Religious",
    "Documentary",
    "Entertainment",
    "Lifestyle",
    "Business",
    "Education",
    "Local",
    "Other",
    "Uncategorized",
]


# =====================================================
# HELPERS
# =====================================================

def sha256(value):

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]


def clean_text(value):

    if value is None:
        return ""

    return re.sub(
        r'[\r\n"]+',
        " ",
        str(value)
    ).strip()


def save_json(path, data):

    if DRY_RUN:
        return

    temp = path.with_suffix(path.suffix + ".tmp")

    with open(temp, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

    temp.replace(path)


def load_cache(path):

    if not path.exists():
        return {}

    try:

        with open(path, encoding="utf-8") as f:
            return json.load(f)

    except Exception:

        return {}


def get_title(obj):

    for key in TITLE_KEYS:

        value = obj.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def get_group(obj, inherited=""):

    for key in GROUP_KEYS:

        value = obj.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return inherited


# =====================================================
# HTTP REQUEST
# =====================================================

def request_url(
    url,
    headers,
    timeout=STREAM_TIMEOUT,
    read_bytes=0
):

    for attempt in range(RETRIES):

        start = time.perf_counter()

        try:

            req = urllib.request.Request(
                url,
                headers=headers
            )

            with urllib.request.urlopen(
                req,
                timeout=timeout
            ) as response:

                body = (
                    response.read(read_bytes)
                    if read_bytes > 0
                    else response.read()
                )

                elapsed = (
                    time.perf_counter() - start
                ) * 1000

                return (
                    response.status,
                    response.headers.get(
                        "Content-Type", ""
                    ).lower(),
                    body,
                    response.geturl(),
                    elapsed,
                )

        except urllib.error.HTTPError as error:

            return (
                error.code,
                "",
                b"",
                url,
                0,
            )

        except Exception:

            if attempt + 1 < RETRIES:

                time.sleep(
                    RETRY_DELAY * (attempt + 1)
                )

    return 0, "", b"", url, 0


# =====================================================
# API
# =====================================================

def get_api(url):

    status, content_type, body, final, elapsed = request_url(
        url,
        HEADERS,
        API_TIMEOUT
    )

    if status != 200:

        raise RuntimeError(
            f"API HTTP {status}: {url}"
        )

    if not body:

        raise RuntimeError("Empty API response")

    try:

        data = json.loads(
            body.decode("utf-8-sig")
        )

    except json.JSONDecodeError:

        raise RuntimeError(
            "API returned invalid JSON"
        )

    if not isinstance(data, (dict, list)):

        raise RuntimeError(
            "Unexpected API JSON structure"
        )

    return data


# =====================================================
# STREAM EXTRACTION
# =====================================================

def get_stream_url(channel):

    candidates = []

    def walk(obj, depth=0):

        if depth > 8:
            return

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if (
                    key_lower in STREAM_KEYS
                    and isinstance(value, str)
                    and value.startswith(
                        ("http://", "https://")
                    )
                ):

                    candidates.append(
                        (key_lower, value.strip())
                    )

            for value in obj.values():

                if isinstance(value, (dict, list)):
                    walk(value, depth + 1)

        elif isinstance(obj, list):

            for item in obj:
                walk(item, depth + 1)

    walk(channel)

    if not candidates:
        return None

    priority = [
        "m3u8_url",
        "hls_url",
        "stream_url",
        "play_url",
        "playlist_url",
        "manifest_url",
        "playback_url",
        "stream",
        "src",
        "url",
        "link",
    ]

    for key in priority:

        for candidate_key, value in candidates:

            if candidate_key == key:

                return value

    return candidates[0][1]


# =====================================================
# CHANNEL EXTRACTION
# =====================================================

def extract_channels(data):

    channels = []
    seen = set()

    def walk(obj, inherited_group=""):

        if isinstance(obj, list):

            for item in obj:
                walk(item, inherited_group)

            return

        if not isinstance(obj, dict):
            return

        group = get_group(
            obj,
            inherited_group
        )

        title = get_title(obj)

        stream = get_stream_url(obj)

        if title and stream:

            key = sha256(stream)

            if key not in seen:

                channel = dict(obj)

                channel["_api_group"] = group

                channels.append(channel)

                seen.add(key)

        for key, value in obj.items():

            if isinstance(value, (dict, list)):

                child_group = group

                if key.lower() in (
                    "blocks",
                    "items",
                    "channels",
                    "live_tvs",
                    "results",
                    "contents",
                    "data",
                ):

                    walk(value, child_group)

                else:

                    walk(value, child_group)

    walk(data)

    return channels


# =====================================================
# NEXT_URL PAGINATION
# =====================================================

def get_next_page(data, current_url, ctx):

    def find_next(obj):

        if isinstance(obj, dict):

            for key in (
                "next_url",
                "next_page_url",
            ):

                value = obj.get(key)

                if (
                    isinstance(value, str)
                    and value.strip()
                ):

                    return value.strip()

            for value in obj.values():

                result = find_next(value)

                if result:
                    return result

        elif isinstance(obj, list):

            for item in obj:

                result = find_next(item)

                if result:
                    return result

        return None

    next_url = find_next(data)

    if not next_url:
        return None

    full_url = urljoin(
        current_url,
        next_url
    )

    parsed = urlparse(full_url)

    if parsed.scheme not in ("http", "https"):
        return None

    if parsed.hostname != API_HOST:

        print(
            "[WARN] Rejected external next_url"
        )

        return None

    if parsed.username or parsed.password:
        return None

    ctx["type"] = "next_url"

    return full_url


# =====================================================
# AUTO GROUP
# =====================================================

def auto_group(title, api_group=""):

    text = (
        title + " " + api_group
    ).lower()

    for group, keywords in GROUP_RULES.items():

        for keyword in keywords:

            if keyword in text:
                return group

    if api_group:

        return api_group

    return "Other"


# =====================================================
# LOGO
# =====================================================

def find_logo(channel):

    for key in LOGO_KEYS:

        value = channel.get(key)

        if isinstance(value, str):

            if value.startswith(
                ("http://", "https://", "//")
            ):

                if value.startswith("//"):
                    return "https:" + value

                return value.replace(
                    "http://",
                    "https://",
                    1
                )

    images = channel.get("images")

    if isinstance(images, dict):

        for value in images.values():

            if isinstance(value, str):

                if value.startswith("http"):
                    return value

            if isinstance(value, dict):

                for key in (
                    "url",
                    "original",
                    "src",
                ):

                    url = value.get(key)

                    if isinstance(url, str):
                        if url.startswith("http"):
                            return url

    return ""


def validate_logo(url, cache):

    if not url:
        return False

    old = cache.get(url)

    if old:

        if (
            old.get("v") == CACHE_VERSION
            and time.time() - old.get("ts", 0)
            < 86400
        ):

            return old.get("ok", False)

    status, content_type, body, _, _ = request_url(
        url,
        IMAGE_HEADERS,
        timeout=8,
        read_bytes=1024
    )

    ok = (
        status in (200, 206)
        and (
            "image" in content_type
            or body.startswith(b"\xff\xd8")
            or body.startswith(b"\x89PNG")
            or body.startswith(b"GIF8")
            or body.startswith(b"RIFF")
        )
    )

    cache[url] = {
        "ok": ok,
        "ts": time.time(),
        "v": CACHE_VERSION
    }

    return ok


# =====================================================
# STREAM VALIDATION
# =====================================================

def validate_stream(url, cache):

    old = cache.get(url)

    if old:

        if (
            old.get("v") == CACHE_VERSION
            and time.time() - old.get("ts", 0)
            < CACHE_TTL
        ):

            return old

    result = {
        "ok": False,
        "reason": "unknown",
        "ttfb_ms": 0,
        "seg_kbps": 0,
        "tier": "very_slow",
        "kind": "unknown",
        "resolved": url,
        "ts": time.time(),
        "v": CACHE_VERSION,
    }

    start = time.perf_counter()

    status, content_type, body, final, elapsed = request_url(
        url,
        STREAM_HEADERS,
        timeout=STREAM_TIMEOUT,
        read_bytes=8192
    )

    result["ttfb_ms"] = round(elapsed, 1)

    if status not in (200, 206):

        result["reason"] = f"http_{status}"

        cache[url] = result

        return result

    text = body.decode(
        "utf-8",
        errors="ignore"
    )

    if "#EXTM3U" not in text:

        if any(
            item in content_type
            for item in (
                "video",
                "mpeg",
                "octet-stream",
            )
        ):

            result.update(
                ok=True,
                reason="direct_video",
                kind="video",
                tier=speed_tier(elapsed),
            )

        else:

            result["reason"] = "invalid_m3u8"

        cache[url] = result

        return result

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    targets = []

    for line in lines:

        if not line.startswith("#"):

            targets.append(
                urljoin(final, line)
            )

    if not targets:

        result["reason"] = "no_stream_targets"

        cache[url] = result

        return result

    if "#EXT-X-STREAM-INF" in text:

        variant = targets[0]

        status2, ct2, body2, final2, elapsed2 = request_url(
            variant,
            STREAM_HEADERS,
            timeout=STREAM_TIMEOUT,
            read_bytes=8192
        )

        if status2 not in (200, 206):

            result["reason"] = "variant_failed"

            cache[url] = result

            return result

        text2 = body2.decode(
            "utf-8",
            errors="ignore"
        )

        if "#EXTM3U" not in text2:

            result["reason"] = "invalid_variant"

            cache[url] = result

            return result

        targets = [
            urljoin(final2, line.strip())
            for line in text2.splitlines()
            if line.strip()
            and not line.strip().startswith("#")
        ]

    if not targets:

        result["reason"] = "no_segments"

        cache[url] = result

        return result

    seg_start = time.perf_counter()

    status3, _, segment, _, seg_elapsed = request_url(
        targets[0],
        STREAM_HEADERS,
        timeout=STREAM_TIMEOUT,
        read_bytes=65536
    )

    if status3 not in (200, 206):

        result["reason"] = "segment_failed"

        cache[url] = result

        return result

    if len(segment) < 16:

        result["reason"] = "empty_segment"

        cache[url] = result

        return result

    elapsed = max(seg_elapsed / 1000, 0.001)

    result.update(
        ok=True,
        reason="working",
        kind="hls",
        tier=speed_tier(result["ttfb_ms"]),
        seg_kbps=round(
            len(segment) / 1024 / elapsed,
            1
        ),
    )

    cache[url] = result

    return result


def speed_tier(ms):

    if ms <= 0:
        return "very_slow"

    if ms < 800:
        return "fast"

    if ms < 2000:
        return "medium"

    if ms < 4500:
        return "slow"

    return "very_slow"


# =====================================================
# VALIDATION
# =====================================================

def validate_all(channels, cache):

    targets = {}

    for channel in channels:

        url = get_stream_url(channel)

        if url:
            targets[sha256(url)] = url

    results = {}

    total = len(targets)

    print(
        f"\n[+] Validating {total} streams..."
    )

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as executor:

        futures = {
            executor.submit(
                validate_stream,
                url,
                cache
            ): key

            for key, url in targets.items()
        }

        done = 0

        for future in as_completed(futures):

            key = futures[future]

            try:

                result = future.result()

            except Exception as error:

                result = {
                    "ok": False,
                    "reason": str(error),
                    "ttfb_ms": 0,
                    "seg_kbps": 0,
                    "tier": "very_slow",
                }

            results[key] = result

            done += 1

            status = (
                "OK"
                if result.get("ok")
                else "DEAD"
            )

            print(
                f"[{done}/{total}] "
                f"{status} "
                f"{result.get('reason')}"
            )

    return results


# =====================================================
# SORT
# =====================================================

def group_rank(group):

    try:
        return GROUP_ORDER.index(group)

    except ValueError:
        return len(GROUP_ORDER)


def tier_rank(tier):

    return {
        "fast": 0,
        "medium": 1,
        "slow": 2,
        "very_slow": 3,
    }.get(tier, 4)


# =====================================================
# PLAYLIST BUILDER
# =====================================================

def build_playlist(
    channels,
    validation,
    logo_cache
):

    enriched = []

    seen = set()

    for channel in channels:

        url = get_stream_url(channel)

        if not url:
            continue

        key = sha256(url)

        result = validation.get(key)

        if not result or not result.get("ok"):
            continue

        if key in seen:
            continue

        seen.add(key)

        title = clean_text(
            get_title(channel) or "Unknown Channel"
        )

        api_group = clean_text(
            channel.get("_api_group", "")
        )

        group = auto_group(
            title,
            api_group
        )

        logo = find_logo(channel)

        if not validate_logo(
            logo,
            logo_cache
        ):

            logo = IPTV_LOGO

        enriched.append({
            "title": title,
            "group": group,
            "logo": logo,
            "stream": url,
            "tier": result.get(
                "tier",
                "very_slow"
            ),
            "ttfb_ms": result.get(
                "ttfb_ms",
                0
            ),
            "seg_kbps": result.get(
                "seg_kbps",
                0
            ),
        })

    if SORT_BY == "speed":

        enriched.sort(
            key=lambda item: (
                tier_rank(item["tier"]),
                item["ttfb_ms"]
            )
        )

    elif SORT_BY == "group":

        enriched.sort(
            key=lambda item: (
                group_rank(item["group"]),
                item["title"].lower()
            )
        )

    else:

        enriched.sort(
            key=lambda item: (
                group_rank(item["group"]),
                tier_rank(item["tier"]),
                item["ttfb_ms"]
            )
        )

    with open(
        PLAYLIST_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write("#EXTM3U\n")

        if EPG_URL:

            file.write(
                f'#EXTM3U x-tvg-url="{EPG_URL}"\n'
            )

        file.write(
            f'#EXTINF:-1 tvg-name="IPTV LINKS" '
            f'tvg-logo="{IPTV_LOGO}" '
            f'group-title="KB PRO TV",IPTV LINKS\n'
        )

        file.write(
            IPTV_VIDEO + "\n\n"
        )

        for index, channel in enumerate(
            enriched,
            1
        ):

            file.write(
                f'#EXTINF:-1 '
                f'tvg-name="{channel["title"]}" '
                f'tvg-logo="{channel["logo"]}" '
                f'group-title="{channel["group"]}" '
                f'tvg-chno="{index}" '
                f'tvg-speed="{channel["tier"]}",'
                f'{channel["title"]}\n'
            )

            file.write(
                channel["stream"] + "\n\n"
            )

    print(
        f"\n[OK] Playlist: {PLAYLIST_FILE}"
    )

    print(
        f"[OK] Channels: {len(enriched)}"
    )

    return enriched


# =====================================================
# REPORTS
# =====================================================

def save_reports(
    channels,
    validation,
    enriched,
    stream_cache,
    logo_cache
):

    save_json(
        CHANNEL_FILE,
        channels
    )

    save_json(
        CACHE_FILE,
        stream_cache
    )

    save_json(
        LOGO_CACHE,
        logo_cache
    )

    save_json(
        HEALTH_FILE,
        {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),

            "total": len(channels),

            "working": len(enriched),

            "dead": len(channels) - len(enriched),
        }
    )

    dead = [
        {
            "stream": url,
            "reason": result.get(
                "reason",
                "unknown"
            )
        }

        for url, result in (
            (
                item,
                stream_cache[item]
            )
            for item in stream_cache
        )

        if not result.get("ok")
    ]

    save_json(
        DEAD_FILE,
        dead
    )

    groups = {}

    for channel in enriched:

        groups.setdefault(
            channel["group"],
            []
        ).append(
            channel["title"]
        )

    save_json(
        GROUPS_FILE,
        groups
    )

    save_json(
        SPEED_FILE,
        enriched
    )


# =====================================================
# MAIN
# =====================================================

def main():

    print("=" * 64)

    print(
        "   BD-KB-IT VIP "
        "FULL SCAN + NEXT_URL ENGINE"
    )

    print("=" * 64)

    print("API       :", API_URL)
    print("Max Pages :", MAX_PAGES)
    print("Sort      :", SORT_BY)
    print("Workers   :", WORKERS)

    print("=" * 64)

    stream_cache = load_cache(
        CACHE_FILE
    )

    logo_cache = load_cache(
        LOGO_CACHE
    )

    all_pages = []

    all_channels = []

    visited_urls = set()

    visited_hashes = set()

    current_url = API_URL

    ctx = {
        "type": "next_url"
    }

    page_number = 0

    stop_reason = "unknown"

    while (
        current_url
        and page_number < MAX_PAGES
    ):

        page_number += 1

        if current_url in visited_urls:

            print(
                "[STOP] Pagination URL loop"
            )

            stop_reason = "url_loop"

            break

        visited_urls.add(
            current_url
        )

        print(
            f"\n[+] Page {page_number}: "
            f"{current_url}"
        )

        try:

            data = get_api(
                current_url
            )

        except Exception as error:

            print(
                f"[ERROR] Page {page_number}: "
                f"{error}"
            )

            stop_reason = "api_error"

            break

        page_hash = hashlib.sha256(
            json.dumps(
                data,
                sort_keys=True,
                ensure_ascii=False
            ).encode()
        ).hexdigest()

        if page_hash in visited_hashes:

            print(
                "[STOP] Duplicate page response"
            )

            stop_reason = "duplicate_page"

            break

        visited_hashes.add(
            page_hash
        )

        all_pages.append(data)

        channels = extract_channels(
            data
        )

        all_channels.extend(
            channels
        )

        print(
            f"    → {len(channels)} channels "
            f"(total: {len(all_channels)})"
        )

        save_json(
            OUTPUT_DIR / (
                f"page_{page_number:05d}.json"
            ),
            data
        )

        # IMPORTANT:
        # Empty page does NOT stop pagination.

        if not channels:

            print(
                "[INFO] Empty page - "
                "checking next_url"
            )

        # Only API-provided next_url.

        next_url = get_next_page(
            data,
            current_url,
            ctx
        )

        if not next_url:

            stop_reason = "no_next_url"

            print(
                "\n[+] API pagination finished"
            )

            break

        current_url = next_url

        time.sleep(0.35)

    if page_number >= MAX_PAGES and current_url:

        stop_reason = "max_pages_reached"

    # =================================================
    # PAGINATION SUMMARY
    # =================================================

    print("\n" + "=" * 64)

    print("PAGINATION SUMMARY")

    print(
        "Pages scanned:",
        page_number
    )

    print(
        "Channels found:",
        len(all_channels)
    )

    print(
        "Pagination:",
        ctx["type"]
    )

    print(
        "Stopped:",
        stop_reason
    )

    print("=" * 64)

    if not all_pages:

        raise SystemExit(
            "ERROR: No API pages fetched"
        )

    # =================================================
    # DEDUPLICATION
    # =================================================

    unique = []

    seen = set()

    for channel in all_channels:

        stream = get_stream_url(
            channel
        )

        if not stream:
            continue

        key = sha256(stream)

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            channel
        )

    print(
        "\n[OK] Unique channels:",
        len(unique)
    )

    # =================================================
    # VALIDATION
    # =================================================

    validation = validate_all(
        unique,
        stream_cache
    )

    # =================================================
    # PLAYLIST
    # =================================================

    enriched = build_playlist(
        unique,
        validation,
        logo_cache
    )

    # =================================================
    # REPORTS
    # =================================================

    save_reports(
        unique,
        validation,
        enriched,
        stream_cache,
        logo_cache
    )

    save_json(
        RAW_FILE,
        all_pages
    )

    # =================================================
    # SUMMARY
    # =================================================

    print("\n" + "=" * 64)

    print(
        "       BD-KB-IT UPDATE COMPLETED"
    )

    print("=" * 64)

    print(
        "Pages scanned:",
        page_number
    )

    print(
        "Total channels:",
        len(unique)
    )

    print(
        "Working channels:",
        len(enriched)
    )

    print(
        "Playlist:",
        PLAYLIST_FILE
    )

    print(
        "Health:",
        HEALTH_FILE
    )

    print(
        "Dead:",
        DEAD_FILE
    )

    print(
        "Groups:",
        GROUPS_FILE
    )

    print(
        "Speed:",
        SPEED_FILE
    )

    print("=" * 64)

    if not enriched:

        print(
            "[WARNING] No working channels found."
        )

        raise SystemExit(1)


if __name__ == "__main__":

    main()
