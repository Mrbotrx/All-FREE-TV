import os
import re
import sys
import json
import time
import hashlib
import logging
import threading
import requests

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================
# BD-KB-IT FREE TV ENGINE
# VERSION: 1.0.0
# =====================================================

VERSION = "1.0.0"

API_URL = os.getenv("BD_KB_IT_API_URL", "").strip()

OUTPUT_DIR = "output"
DATA_DIR = "data"

PLAYLIST_FILE = f"{OUTPUT_DIR}/BD-KB-IT.m3u8"

CHANNEL_DATA_FILE = f"{DATA_DIR}/ALL_CHANNEL_DATA.json"
API_BACKUP_FILE = f"{DATA_DIR}/ALL_API_RESPONSES.json"
HEALTH_FILE = f"{DATA_DIR}/health_report.json"
CACHE_FILE = f"{DATA_DIR}/validation_cache.json"
DEAD_FILE = f"{DATA_DIR}/dead_channels.json"
LOGO_FILE = f"{DATA_DIR}/logo_cache.json"
GROUP_FILE = f"{DATA_DIR}/groups_index.json"
SPEED_FILE = f"{DATA_DIR}/speed_report.json"

MAX_PAGES = 10000
MAX_WORKERS = 32
REQUEST_TIMEOUT = 20
CACHE_HOURS = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13) BD-KB-IT/1.0",
    "Accept": "application/json, */*"
}

STREAM_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Range": "bytes=0-4095"
}

LOCK = threading.Lock()

API_RESPONSES = []
ALL_CHANNELS = []
WORKING_CHANNELS = []
DEAD_CHANNELS = []

SEEN_STREAMS = set()
VISITED_PAGES = set()

CACHE = {}
SPEED_REPORT = []

SESSION_LOCAL = threading.local()


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("BD-KB-IT")


def log(message):
    logger.info(message)


# =====================================================
# FILE MANAGEMENT
# =====================================================

def setup_directories():

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(path, default):

    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json(path, data):

    temporary = path + ".tmp"

    with open(temporary, "w", encoding="utf-8") as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

    os.replace(temporary, path)


# =====================================================
# HTTP SESSION
# =====================================================

def get_session():

    if not hasattr(SESSION_LOCAL, "session"):

        session = requests.Session()

        session.headers.update(HEADERS)

        SESSION_LOCAL.session = session

    return SESSION_LOCAL.session


# =====================================================
# URL UTILITIES
# =====================================================

def normalize_url(url, base=""):

    if not isinstance(url, str):
        return ""

    url = url.strip()

    if not url:
        return ""

    url = urljoin(base, url)

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return ""

    return url


def is_m3u8(url):

    path = urlparse(url).path.lower()

    return (
        path.endswith(".m3u8")
        or ".m3u8/" in path
    )


def clean_text(value):

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return ""

    return str(value).strip()


def get_first(data, keys):

    if not isinstance(data, dict):
        return ""

    for key in keys:

        value = clean_text(data.get(key))

        if value:
            return value

    return ""


# =====================================================
# CHANNEL FIELD DEFINITIONS
# =====================================================

NAME_KEYS = [
    "name",
    "title",
    "channel_name",
    "channelName",
    "display_name",
    "displayName",
    "label"
]

STREAM_KEYS = [
    "stream_url",
    "streamUrl",
    "m3u8_url",
    "m3u8",
    "hls_url",
    "hlsUrl",
    "playback_url",
    "playbackUrl",
    "video_url",
    "videoUrl",
    "manifest_url",
    "manifestUrl",
    "stream",
    "url",
    "link"
]

LOGO_KEYS = [
    "logo",
    "logo_url",
    "logoUrl",
    "image",
    "image_url",
    "thumbnail",
    "icon",
    "poster"
]

CATEGORY_KEYS = [
    "category",
    "category_name",
    "categoryName",
    "group",
    "group_name",
    "groupName",
    "genre",
    "type"
]


# =====================================================
# API PAGINATION DETECTION
# =====================================================

def find_pagination(data):

    if isinstance(data, dict):

        pagination = data.get("pagination")

        if isinstance(pagination, dict):

            next_url = (
                pagination.get("next_url")
                or pagination.get("nextUrl")
                or pagination.get("next")
            )

            cursor = pagination.get("next_cursor")

            has_more = pagination.get("has_more")

            if next_url:
                return {
                    "next_url": next_url,
                    "cursor": cursor,
                    "has_more": has_more
                }

            if cursor:
                return {
                    "next_url": None,
                    "cursor": cursor,
                    "has_more": has_more
                }

        for key in (
            "next_url",
            "nextUrl",
            "next_page_url"
        ):

            value = data.get(key)

            if isinstance(value, str) and value.strip():

                return {
                    "next_url": value,
                    "cursor": None,
                    "has_more": True
                }

        for value in data.values():

            result = find_pagination(value)

            if result:
                return result

    elif isinstance(data, list):

        for item in data:

            result = find_pagination(item)

            if result:
                return result

    return None


def build_cursor_url(current_url, cursor):

    parsed = urlparse(current_url)

    params = parse_qs(
        parsed.query,
        keep_blank_values=True
    )

    params["cursor"] = [str(cursor)]

    query = urlencode(params, doseq=True)

    return urlunparse(
        parsed._replace(query=query)
    )


# =====================================================
# CHANNEL EXTRACTION ENGINE
# =====================================================

def extract_channels(data, base_url):

    results = []

    if isinstance(data, dict):

        name = get_first(data, NAME_KEYS)

        stream = get_first(data, STREAM_KEYS)

        logo = get_first(data, LOGO_KEYS)

        category = get_first(data, CATEGORY_KEYS)

        if name and stream:

            stream = normalize_url(
                stream,
                base_url
            )

            logo = normalize_url(
                logo,
                base_url
            ) if logo else ""

            if stream and is_m3u8(stream):

                results.append({

                    "name": name,

                    "url": stream,

                    "logo": logo,

                    "category": category or "Uncategorized"

                })

        for key, value in data.items():

            if isinstance(value, (dict, list)):

                results.extend(
                    extract_channels(value, base_url)
                )

    elif isinstance(data, list):

        for item in data:

            results.extend(
                extract_channels(item, base_url)
            )

    return results


# =====================================================
# API FETCH
# =====================================================

def fetch_api(url):

    try:

        response = get_session().get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:

        log(f"API REQUEST ERROR: {error}")

    except ValueError as error:

        log(f"INVALID JSON: {error}")

    return None


# =====================================================
# COMPLETE API SCANNER
# =====================================================

def scan_all_pages():

    if not API_URL:

        log("ERROR: BD_KB_IT_API_URL missing!")

        sys.exit(1)

    current_url = API_URL

    page = 0

    while current_url and page < MAX_PAGES:

        if current_url in VISITED_PAGES:
            log("Repeated API URL detected. Stopping.")
            break

        VISITED_PAGES.add(current_url)

        page += 1

        log(f"Scanning API Page {page}")

        data = fetch_api(current_url)

        if data is None:
            break

        API_RESPONSES.append({

            "page": page,

            "url": current_url,

            "data": data

        })

        found = extract_channels(
            data,
            current_url
        )

        added = 0

        for channel in found:

            stream = channel["url"]

            with LOCK:

                if stream in SEEN_STREAMS:
                    continue

                SEEN_STREAMS.add(stream)

                ALL_CHANNELS.append(channel)

                added += 1

        log(
            f"Page {page}: "
            f"{len(found)} records, "
            f"{added} unique channels"
        )

        pagination = find_pagination(data)

        if not pagination:
            break

        next_url = pagination.get("next_url")

        cursor = pagination.get("cursor")

        has_more = pagination.get("has_more")

        if has_more is False:
            break

        if next_url:

            current_url = normalize_url(
                next_url,
                current_url
            )

        elif cursor:

            current_url = build_cursor_url(
                current_url,
                cursor
            )

        else:

            break

    log(f"Total API Pages: {page}")

    log(f"Total Unique Channels: {len(ALL_CHANNELS)}")


# =====================================================
# VALIDATION CACHE
# =====================================================

def load_cache():

    global CACHE

    CACHE = load_json(
        CACHE_FILE,
        {}
    )


def save_cache():

    save_json(
        CACHE_FILE,
        CACHE
    )


def get_cache_key(url):

    return hashlib.sha256(
        url.encode()
    ).hexdigest()


def get_cached_result(url):

    key = get_cache_key(url)

    entry = CACHE.get(key)

    if not entry:
        return None

    timestamp = entry.get("timestamp", 0)

    age = time.time() - timestamp

    if age > CACHE_HOURS * 3600:
        return None

    return entry


def update_cache(url, result):

    key = get_cache_key(url)

    with LOCK:

        CACHE[key] = {

            "working": result["working"],

            "ttfb": result["ttfb"],

            "timestamp": time.time()

        }


# =====================================================
# STREAM VALIDATOR
# =====================================================

def validate_stream(channel):

    url = channel["url"]

    cached = get_cached_result(url)

    if cached:

        return {

            "channel": channel,

            "working": cached["working"],

            "ttfb": cached.get("ttfb", 0),

            "cached": True

        }

    start = time.perf_counter()

    working = False

    ttfb = 0

    try:

        response = requests.get(

            url,

            headers=STREAM_HEADERS,

            timeout=REQUEST_TIMEOUT,

            stream=True,

            allow_redirects=True

        )

        ttfb = round(
            (time.perf_counter() - start) * 1000,
            2
        )

        if response.status_code in (200, 206):

            content_type = response.headers.get(
                "Content-Type",
                ""
            ).lower()

            content = next(
                response.iter_content(4096),
                b""
            )

            if (
                b"#EXTM3U" in content
                or "mpegurl" in content_type
                or "vnd.apple.mpegurl" in content_type
            ):

                working = True

        response.close()

    except requests.RequestException:

        working = False

    result = {

        "working": working,

        "ttfb": ttfb

    }

    update_cache(url, result)

    return {

        "channel": channel,

        "working": working,

        "ttfb": ttfb,

        "cached": False

    }


# =====================================================
# MULTI-THREAD VALIDATION
# =====================================================

def validate_all_channels():

    total = len(ALL_CHANNELS)

    log(f"Validating {total} channels...")

    completed = 0

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {

            executor.submit(
                validate_stream,
                channel
            ): channel

            for channel in ALL_CHANNELS

        }

        for future in as_completed(futures):

            completed += 1

            try:

                result = future.result()

                channel = result["channel"]

                if result["working"]:

                    WORKING_CHANNELS.append(channel)

                    SPEED_REPORT.append({

                        "name": channel["name"],

                        "url": channel["url"],

                        "ttfb_ms": result["ttfb"]

                    })

                    log(
                        f"[{completed}/{total}] "
                        f"WORKING: {channel['name']}"
                    )

                else:

                    DEAD_CHANNELS.append(channel)

                    log(
                        f"[{completed}/{total}] "
                        f"DEAD: {channel['name']}"
                    )

            except Exception as error:

                log(f"VALIDATION ERROR: {error}")

    save_cache()


# =====================================================
# CHANNEL SORTING
# =====================================================

def sort_channels():

    WORKING_CHANNELS.sort(

        key=lambda channel: (

            channel.get("category", "").lower(),

            channel.get("name", "").lower()

        )

    )


# =====================================================
# M3U PLAYLIST GENERATOR
# =====================================================

def create_playlist():

    updated = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    header = f"""#EXTM3U
#PLAYLIST:BD-KB-IT
#
# ╔══════════════════════════════════════════════════╗
# ║        B D - K B - I T   •   F R E E   T V       ║
# ║     BANGLADESH  +  INTERNATIONAL  LIVE  TV       ║
# ╚══════════════════════════════════════════════════╝
#
#  NAME      : BD-KB-IT
#  VERSION   : 1.0.0
#  UPDATED   : {updated}
#  CHANNELS  : {len(WORKING_CHANNELS)}
#  FORMAT    : M3U8 (HLS)
#  STATUS    : 24/7 LIVE
#
#  MAKE BY   : Kallyan Biswas
#  FACEBOOK  : Www.Facebook.com/kallyan.biswas.29
#
# ──────────────────────────────────────────────────

"""

    with open(
        PLAYLIST_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(header)

        for channel in WORKING_CHANNELS:

            name = channel["name"]

            logo = channel["logo"]

            category = channel["category"]

            url = channel["url"]

            name = name.replace('"', "'")

            logo = logo.replace('"', "'")

            category = category.replace('"', "'")

            file.write(

                f'#EXTINF:-1 '
                f'tvg-name="{name}" '
                f'tvg-logo="{logo}" '
                f'group-title="{category}",'
                f'{name}\n'

            )

            # Original stream URL remains unchanged.
            file.write(url + "\n\n")

    log(f"Playlist generated: {PLAYLIST_FILE}")


# =====================================================
# REPORT GENERATOR
# =====================================================

def generate_reports():

    total = len(ALL_CHANNELS)

    working = len(WORKING_CHANNELS)

    dead = len(DEAD_CHANNELS)

    health = {

        "project": "BD-KB-IT",

        "version": VERSION,

        "updated": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_channels": total,

        "working_channels": working,

        "dead_channels": dead,

        "success_rate": round(
            (working / total * 100)
            if total else 0,
            2
        )

    }

    save_json(
        HEALTH_FILE,
        health
    )

    save_json(
        DEAD_FILE,
        DEAD_CHANNELS
    )

    save_json(
        SPEED_FILE,
        SPEED_REPORT
    )

    save_json(
        CHANNEL_DATA_FILE,
        ALL_CHANNELS
    )

    save_json(
        API_BACKUP_FILE,
        API_RESPONSES
    )

    logos = {

        channel["name"]: channel["logo"]

        for channel in ALL_CHANNELS

        if channel["logo"]

    }

    save_json(
        LOGO_FILE,
        logos
    )

    groups = {}

    for channel in WORKING_CHANNELS:

        category = channel["category"]

        groups.setdefault(
            category,
            []
        ).append(channel["name"])

    save_json(
        GROUP_FILE,
        groups
    )

    log("All reports generated.")


# =====================================================
# MAIN ENGINE
# =====================================================

def main():

    start = time.time()

    setup_directories()

    load_cache()

    log("======================================")

    log("BD-KB-IT ENGINE STARTED")

    log(f"VERSION: {VERSION}")

    log("======================================")

    # 1. Scan all API pages

    scan_all_pages()

    # 2. Validate streams

    validate_all_channels()

    # 3. Sort working channels

    sort_channels()

    # 4. Generate M3U playlist

    create_playlist()

    # 5. Generate reports and backups

    generate_reports()

    elapsed = round(
        time.time() - start,
        2
    )

    log("======================================")

    log("BD-KB-IT UPDATE COMPLETED")

    log(f"API CHANNELS: {len(ALL_CHANNELS)}")

    log(f"WORKING: {len(WORKING_CHANNELS)}")

    log(f"DEAD: {len(DEAD_CHANNELS)}")

    log(f"TIME: {elapsed} seconds")

    log(f"PLAYLIST: {PLAYLIST_FILE}")

    log("======================================")


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log("Process stopped by user.")

        sys.exit(130)

    except Exception:

        logger.exception("FATAL ENGINE ERROR")

        sys.exit(1)
