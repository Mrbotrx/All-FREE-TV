import os
import re
import json
import time
import urllib.request
import urllib.error

from urllib.parse import urljoin, urlparse

# ==========================================
# BD KB IT CONFIGURATION
# ==========================================

BASE_URL = "https://web.aynaott.com"

API_URL = os.environ.get(
    "BD_KB_IT_API_URL",
    BASE_URL + "/api/v5/pages/live-tvs/"
)

OUTPUT_DIR = "output"

JSON_FILE = os.path.join(
    OUTPUT_DIR,
    "ALL_CHANNEL_DATA.json"
)

RAW_FILE = os.path.join(
    OUTPUT_DIR,
    "ALL_API_RESPONSES.json"
)

M3U_FILE = os.path.join(
    OUTPUT_DIR,
    "BD-KB-IT.m3u8"
)

TIMEOUT = 30
DELAY = 0.5

# Prevent accidental infinite pagination.
MAX_PAGES = 10000

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": BASE_URL + "/live-tvs"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==========================================
# VALIDATE API URL
# ==========================================

def validate_url(url):

    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("HTTPS required")

    if parsed.hostname != "web.aynaott.com":
        raise ValueError("Unexpected API hostname")

    return url


# ==========================================
# API REQUEST
# ==========================================

def get_api(url):

    url = validate_url(url)

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        content = response.read().decode(
            "utf-8",
            errors="replace"
        )

        return json.loads(content)


# ==========================================
# PAGINATION
# ==========================================

def get_next_page(data, current_url):

    if not isinstance(data, dict):
        return None

    pagination = data.get(
        "blocks_pagination",
        {}
    )

    if not isinstance(pagination, dict):
        return None

    has_more = pagination.get(
        "has_more",
        False
    )

    next_url = pagination.get(
        "next_url"
    )

    if not has_more:
        return None

    if not next_url:

        raise RuntimeError(
            "has_more is true but next_url is missing"
        )

    # Support relative and absolute next_url.
    next_url = urljoin(
        current_url,
        next_url
    )

    return validate_url(next_url)


# ==========================================
# EXTRACT RECORDS
# ==========================================

def extract_records(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    possible_keys = [
        "results",
        "items",
        "data",
        "blocks",
        "channels"
    ]

    for key in possible_keys:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for subkey in possible_keys:

                subvalue = value.get(subkey)

                if isinstance(subvalue, list):
                    return subvalue

    return []


# ==========================================
# FIELD EXTRACTION
# ==========================================

def get_value(data, keys):

    if not isinstance(data, dict):
        return None

    for key in keys:

        value = data.get(key)

        if value is not None and value != "":
            return value

    return None


def get_nested_value(data, keys):

    value = get_value(data, keys)

    if isinstance(value, dict):

        return get_value(
            value,
            ["url", "src", "name", "title"]
        )

    return value


# ==========================================
# NORMALIZE CHANNEL
# ==========================================

def normalize_channel(record):

    if not isinstance(record, dict):
        return None

    name = get_nested_value(
        record,
        [
            "name",
            "title",
            "channel_name",
            "display_name"
        ]
    )

    logo = get_nested_value(
        record,
        [
            "logo",
            "logo_url",
            "image",
            "thumbnail",
            "icon"
        ]
    )

    group = get_nested_value(
        record,
        [
            "category",
            "group",
            "group_title",
            "genre"
        ]
    )

    channel_id = get_value(
        record,
        [
            "id",
            "channel_id",
            "slug"
        ]
    )

    stream = get_nested_value(
        record,
        [
            "stream_url",
            "play_url",
            "url",
            "link",
            "m3u8",
            "source"
        ]
    )

    if not name:
        return None

    if isinstance(stream, str):

        stream = stream.strip()

    else:

        stream = ""

    return {
        "id": str(channel_id or name),
        "name": str(name),
        "logo": str(logo or ""),
        "group": str(group or "Uncategorized"),
        "url": stream
    }


# ==========================================
# CLEAN M3U TEXT
# ==========================================

def clean_text(value):

    value = str(value or "")

    value = re.sub(
        r'[\r\n"]+',
        " ",
        value
    )

    return value.strip()


# ==========================================
# GENERATE M3U
# ==========================================

def generate_m3u(channels):

    lines = ["#EXTM3U"]

    count = 0

    for channel in channels:

        name = clean_text(channel["name"])

        logo = clean_text(channel["logo"])

        group = clean_text(channel["group"])

        channel_id = clean_text(channel["id"])

        stream = channel["url"]

        # Only include explicitly available
        # HTTP(S) stream URLs.

        parsed = urlparse(stream)

        if parsed.scheme not in ("http", "https"):
            continue

        if not parsed.netloc:
            continue

        info = (
            f'#EXTINF:-1 '
            f'tvg-id="{channel_id}" '
            f'tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",'
            f'{name}'
        )

        lines.append(info)

        lines.append(stream)

        count += 1

    with open(
        M3U_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "\n".join(lines) + "\n"
        )

    return count


# ==========================================
# SAVE JSON
# ==========================================

def save_json(filename, data):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# ==========================================
# MAIN DOWNLOADER
# ==========================================

def main():

    print("=" * 55)
    print("          BD KB IT AUTO UPDATE")
    print("=" * 55)

    url = API_URL

    visited = set()

    all_pages = []

    all_records = []

    page = 0

    # ======================================
    # FETCH ALL PAGINATION
    # ======================================

    while url:

        if page >= MAX_PAGES:

            raise RuntimeError(
                "Maximum page safety limit reached"
            )

        if url in visited:

            raise RuntimeError(
                "Pagination loop detected"
            )

        visited.add(url)

        page += 1

        print(f"\n[PAGE {page}] Fetching API")

        print(url)

        try:

            data = get_api(url)

        except Exception as error:

            raise RuntimeError(
                f"API request failed on page {page}: {error}"
            )

        if not isinstance(data, (dict, list)):

            raise RuntimeError(
                "Invalid API response"
            )

        all_pages.append(data)

        records = extract_records(data)

        all_records.extend(records)

        print(
            "[OK] Records:",
            len(records)
        )

        # ==================================
        # GET NEXT URL
        # ==================================

        next_url = get_next_page(
            data,
            url
        )

        if next_url:

            print("[+] Next URL Found")

        else:

            print("[+] All API Pages Completed")

        url = next_url

        if url:
            time.sleep(DELAY)

    # ======================================
    # NORMALIZE CHANNELS
    # ======================================

    channels = []

    seen = set()

    for record in all_records:

        channel = normalize_channel(record)

        if not channel:
            continue

        # Avoid duplicate records.
        unique_key = (
            channel["id"],
            channel["name"]
        )

        if unique_key in seen:
            continue

        seen.add(unique_key)

        channels.append(channel)

    # ======================================
    # SAVE RAW API RESPONSES
    # ======================================

    save_json(
        RAW_FILE,
        all_pages
    )

    # ======================================
    # SAVE CHANNEL JSON
    # ======================================

    json_output = {
        "project": "BD KB IT",
        "total_pages": len(all_pages),
        "total_records": len(all_records),
        "total_channels": len(channels),
        "channels": channels
    }

    save_json(
        JSON_FILE,
        json_output
    )

    # ======================================
    # GENERATE PLAYLIST
    # ======================================

    playlist_count = generate_m3u(
        channels
    )

    # ======================================
    # FINAL REPORT
    # ======================================

    print("\n" + "=" * 55)

    print("UPDATE SUCCESSFUL")

    print("Total Pages:", len(all_pages))

    print("Total Records:", len(all_records))

    print("Total Channels:", len(channels))

    print("Playlist Entries:", playlist_count)

    print("\nOUTPUT FILES:")

    print(JSON_FILE)

    print(RAW_FILE)

    print(M3U_FILE)

    print("=" * 55)


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    main()
