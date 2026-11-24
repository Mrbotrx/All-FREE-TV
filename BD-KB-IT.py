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
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    urlencode,
    urlunparse
)
from concurrent.futures import ThreadPoolExecutor, as_completed


# =====================================================
# BD-KB-IT CONFIGURATION
# =====================================================

VERSION = "1.0.0"

API_URL = os.getenv("BD_KB_IT_API_URL", "").strip()

MAX_PAGES = 10000
MAX_WORKERS = 32

API_TIMEOUT = 25
STREAM_TIMEOUT = 20

CACHE_HOURS = 3

CURSOR_PARAM = os.getenv(
    "BD_KB_IT_CURSOR_PARAM",
    "cursor"
)

OUTPUT_DIR = "output"

PLAYLIST_FILE = f"{OUTPUT_DIR}/BD-KB-IT.m3u8"

CHANNEL_FILE = f"{OUTPUT_DIR}/ALL_CHANNEL_DATA.json"
API_FILE = f"{OUTPUT_DIR}/ALL_API_RESPONSES.json"
HEALTH_FILE = f"{OUTPUT_DIR}/health_report.json"
DEAD_FILE = f"{OUTPUT_DIR}/dead_channels.json"
LOGO_FILE = f"{OUTPUT_DIR}/logo_cache.json"
GROUP_FILE = f"{OUTPUT_DIR}/groups_index.json"
SPEED_FILE = f"{OUTPUT_DIR}/speed_report.json"
CACHE_FILE = f"{OUTPUT_DIR}/validation_cache.json"

LOCK = threading.Lock()

ALL_CHANNELS = []
WORKING_CHANNELS = []
DEAD_CHANNELS = []

API_RESPONSES = []

SEEN_URLS = set()
VISITED_PAGES = set()

CACHE = {}
SPEED_REPORT = []

thread_local = threading.local()


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
# HTTP HEADERS - NO TOKEN
# =====================================================

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 BD-KB-IT/1.0",
    "Accept": "application/json, */*"
}

STREAM_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Range": "bytes=0-4095"
}


# =====================================================
# SESSION
# =====================================================

def get_session():

    if not hasattr(thread_local, "session"):

        session = requests.Session()

        session.headers.update(STREAM_HEADERS)

        thread_local.session = session

    return thread_local.session


# =====================================================
# DIRECTORY
# =====================================================

def setup():

    os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================
# JSON FILE MANAGEMENT
# =====================================================

def load_json(path, default):

    if not os.path.exists(path):
        return default

    try:

        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    except (OSError, ValueError):

        return default


def save_json(path, data):

    temporary = path + ".tmp"

    with open(temporary, "w", encoding="utf-8") as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    os.replace(temporary, path)


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

    if not parsed.hostname:
        return ""

    return url


def is_m3u8_url(url):

    parsed = urlparse(url)

    path = parsed.path.lower()

    return (
        path.endswith(".m3u8")
        or ".m3u8/" in path
        or ".m3u8?" in url.lower()
    )


def clean(value):

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, (int, float)):
        return str(value)

    return ""


# =====================================================
# CHANNEL FIELD DEFINITIONS
# =====================================================

NAME_KEYS = {
    "name",
    "title",
    "channel_name",
    "channelname",
    "display_name",
    "displayname",
    "channel_title",
    "channel",
    "label"
}

LOGO_KEYS = {
    "logo",
    "logo_url",
    "logourl",
    "image",
    "image_url",
    "imageurl",
    "thumbnail",
    "icon",
    "poster",
    "channel_logo"
}

CATEGORY_KEYS = {
    "category",
    "category_name",
    "categoryname",
    "group",
    "group_name",
    "groupname",
    "genre",
    "channel_category"
}

STREAM_KEYS = {
    "url",
    "link",
    "stream",
    "stream_url",
    "streamurl",
    "stream_link",
    "playback_url",
    "playbackurl",
    "hls_url",
    "hlsurl",
    "m3u8",
    "m3u8_url",
    "manifest",
    "manifest_url",
    "source",
    "video_url",
    "videourl"
}


# =====================================================
# FIELD DETECTION
# =====================================================

def find_value(data, keys):

    if not isinstance(data, dict):
        return ""

    for key, value in data.items():

        normalized = str(key).lower().replace("-", "_")

        if normalized in keys:

            result = clean(value)

            if result:
                return result

    return ""


# =====================================================
# URL EXTRACTION
# =====================================================

def extract_urls(value, base_url):

    results = []

    if isinstance(value, str):

        candidate = normalize_url(value, base_url)

        if candidate and is_m3u8_url(candidate):
            results.append(candidate)

        pattern = r'https?://[^\s"\'<>]+'

        for match in re.findall(pattern, value):

            candidate = normalize_url(
                match.rstrip("),];"),
                base_url
            )

            if candidate and is_m3u8_url(candidate):
                results.append(candidate)

    elif isinstance(value, dict):

        for child in value.values():

            results.extend(
                extract_urls(child, base_url)
            )

    elif isinstance(value, list):

        for child in value:

            results.extend(
                extract_urls(child, base_url)
            )

    return list(dict.fromkeys(results))


# =====================================================
# DEEP CHANNEL FINDER
# =====================================================

def extract_channels(data, base_url):

    results = []

    def walk(node, inherited=None):

        if inherited is None:
            inherited = {}

        if isinstance(node, dict):

            name = (
                find_value(node, NAME_KEYS)
                or inherited.get("name", "")
            )

            logo = (
                find_value(node, LOGO_KEYS)
                or inherited.get("logo", "")
            )

            category = (
                find_value(node, CATEGORY_KEYS)
                or inherited.get("category", "")
            )

            context = {
                "name": name,
                "logo": logo,
                "category": category
            }

            urls = []

            # Direct stream fields
            for key, value in node.items():

                normalized = str(key).lower().replace("-", "_")

                if normalized in STREAM_KEYS:

                    urls.extend(
                        extract_urls(value, base_url)
                    )

            # Search nested stream objects
            for value in node.values():

                if isinstance(value, (dict, list)):

                    urls.extend(
                        extract_urls(value, base_url)
                    )

            if name and urls:

                for url in dict.fromkeys(urls):

                    results.append({

                        "name": name,

                        "url": url,

                        "logo": normalize_url(
                            logo,
                            base_url
                        ) if logo else "",

                        "category": category or "Uncategorized"

                    })

            for value in node.values():

                if isinstance(value, (dict, list)):

                    walk(value, context)

        elif isinstance(node, list):

            for item in node:
                walk(item, inherited)

    walk(data)

    return results


# =====================================================
# API FETCH
# =====================================================

def fetch_api(url):

    try:

        response = requests.get(
            url,
            headers=API_HEADERS,
            timeout=API_TIMEOUT
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:

        log(f"API ERROR: {error}")

    except ValueError:

        log("API returned invalid JSON.")

    return None


# =====================================================
# PAGINATION DETECTION
# =====================================================

def find_pagination(data):

    if isinstance(data, dict):

        pagination = data.get("pagination")

        if isinstance(pagination, dict):

            next_url = (
                pagination.get("next_url")
                or pagination.get("nextUrl")
            )

            cursor = pagination.get("next_cursor")

            has_more = pagination.get("has_more")

            return next_url, cursor, has_more

        next_url = (
            data.get("next_url")
            or data.get("nextUrl")
            or data.get("next_page_url")
        )

        if next_url:
            return next_url, None, True

        for value in data.values():

            if isinstance(value, (dict, list)):

                result = find_pagination(value)

                if result[0] or result[1]:
                    return result

    elif isinstance(data, list):

        for item in data:

            result = find_pagination(item)

            if result[0] or result[1]:
                return result

    return None, None, None


def make_cursor_url(url, cursor):

    parsed = urlparse(url)

    params = parse_qs(
        parsed.query,
        keep_blank_values=True
    )

    params[CURSOR_PARAM] = [str(cursor)]

    query = urlencode(
        params,
        doseq=True
    )

    return urlunparse(
        parsed._replace(query=query)
    )


# =====================================================
# SCAN ALL API PAGES
# =====================================================

def scan_api():

    if not API_URL:

        log("ERROR: BD_KB_IT_API_URL missing!")

        sys.exit(1)

    current_url = API_URL

    page = 0

    while current_url and page < MAX_PAGES:

        if current_url in VISITED_PAGES:

            log("Repeated API page detected.")

            break

        VISITED_PAGES.add(current_url)

        page += 1

        log(f"SCANNING API PAGE: {page}")

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

            url = channel["url"]

            with LOCK:

                if url in SEEN_URLS:
                    continue

                SEEN_URLS.add(url)

                ALL_CHANNELS.append(channel)

                added += 1

        log(
            f"PAGE {page}: "
            f"FOUND {len(found)} | "
            f"NEW {added}"
        )

        next_url, cursor, has_more = find_pagination(data)

        if has_more is False:
            break

        if next_url:

            current_url = normalize_url(
                next_url,
                current_url
            )

        elif cursor:

            current_url = make_cursor_url(
                current_url,
                cursor
            )

        else:

            break

    log(f"API PAGES: {page}")

    log(f"TOTAL CHANNELS: {len(ALL_CHANNELS)}")


# =====================================================
# CACHE SYSTEM
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


def cache_key(url):

    return hashlib.sha256(
        url.encode()
    ).hexdigest()


def get_cached(url):

    item = CACHE.get(cache_key(url))

    if not item:
        return None

    age = time.time() - item.get("timestamp", 0)

    if age > CACHE_HOURS * 3600:
        return None

    return item


def set_cached(url, working, ttfb):

    with LOCK:

        CACHE[cache_key(url)] = {

            "working": working,

            "ttfb": ttfb,

            "timestamp": time.time()

        }


# =====================================================
# M3U8 STREAM VALIDATOR
# =====================================================

def validate_stream(channel):

    url = channel["url"]

    cached = get_cached(url)

    if cached:

        return {

            "channel": channel,

            "working": cached["working"],

            "ttfb": cached["ttfb"],

            "cached": True

        }

    start = time.perf_counter()

    working = False

    ttfb = 0

    try:

        response = get_session().get(

            url,

            timeout=STREAM_TIMEOUT,

            stream=True,

            allow_redirects=True

        )

        ttfb = round(
            (time.perf_counter() - start) * 1000,
            2
        )

        if response.status_code in (200, 206):

            content = next(
                response.iter_content(4096),
                b""
            )

            content_type = response.headers.get(
                "Content-Type",
                ""
            ).lower()

            if (
                b"#EXTM3U" in content
                or "mpegurl" in content_type
            ):

                working = True

        response.close()

    except requests.RequestException:

        working = False

    set_cached(
        url,
        working,
        ttfb
    )

    return {

        "channel": channel,

        "working": working,

        "ttfb": ttfb,

        "cached": False

    }


# =====================================================
# MULTI-THREAD VALIDATION
# =====================================================

def validate_all():

    total = len(ALL_CHANNELS)

    log(f"VALIDATING {total} CHANNELS")

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [

            executor.submit(
                validate_stream,
                channel
            )

            for channel in ALL_CHANNELS

        ]

        for index, future in enumerate(
            as_completed(futures),
            1
        ):

            try:

                result = future.result()

                channel = result["channel"]

                if result["working"]:

                    WORKING_CHANNELS.append(channel)

                    SPEED_REPORT.append({

                        "name": channel["name"],

                        "ttfb_ms": result["ttfb"],

                        "cached": result["cached"]

                    })

                    log(
                        f"[{index}/{total}] "
                        f"WORKING: {channel['name']}"
                    )

                else:

                    DEAD_CHANNELS.append(channel)

                    log(
                        f"[{index}/{total}] "
                        f"DEAD: {channel['name']}"
                    )

            except Exception as error:

                log(f"VALIDATION ERROR: {error}")

    save_cache()


# =====================================================
# SORT CHANNELS
# =====================================================

def sort_channels():

    WORKING_CHANNELS.sort(

        key=lambda channel: (

            channel["category"].lower(),

            channel["name"].lower()

        )

    )


# =====================================================
# PLAYLIST GENERATOR
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
#  VERSION   : {VERSION}
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

            name = channel["name"].replace('"', "'")

            logo = channel["logo"].replace('"', "'")

            category = channel["category"].replace('"', "'")

            file.write(

                f'#EXTINF:-1 '
                f'tvg-name="{name}" '
                f'tvg-logo="{logo}" '
                f'group-title="{category}",'
                f'{name}\n'

            )

            # Original URL: No key, no token, no modification.
            file.write(channel["url"] + "\n\n")

    log("PLAYLIST GENERATED SUCCESSFULLY")


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
            working / total * 100,
            2
        ) if total else 0

    }

    save_json(
        CHANNEL_FILE,
        ALL_CHANNELS
    )

    save_json(
        API_FILE,
        API_RESPONSES
    )

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

        groups.setdefault(
            channel["category"],
            []
        ).append(channel["name"])

    save_json(
        GROUP_FILE,
        groups
    )

    log("ALL REPORTS SAVED")


# =====================================================
# MAIN ENGINE
# =====================================================

def main():

    start = time.time()

    setup()

    load_cache()

    log("======================================")

    log("BD-KB-IT ENGINE STARTED")

    log(f"VERSION: {VERSION}")

    log("API TOKEN: DISABLED")

    log("======================================")

    scan_api()

    validate_all()

    sort_channels()

    create_playlist()

    generate_reports()

    elapsed = round(
        time.time() - start,
        2
    )

    log("======================================")

    log("BD-KB-IT UPDATE COMPLETED")

    log(f"FOUND: {len(ALL_CHANNELS)}")

    log(f"WORKING: {len(WORKING_CHANNELS)}")

    log(f"DEAD: {len(DEAD_CHANNELS)}")

    log(f"TIME: {elapsed}s")

    log(f"OUTPUT: {PLAYLIST_FILE}")

    log("======================================")


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log("STOPPED BY USER")

        sys.exit(130)

    except Exception:

        logger.exception("FATAL ERROR")

        sys.exit(1)
