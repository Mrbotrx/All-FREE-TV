import os
import re
import json
import time
import urllib.request
from urllib.parse import urljoin, urlparse

# =====================================
# CONFIGURATION
# =====================================

BASE_URL = "https://web.aynaott.com"

API_URL = os.getenv(
    "BD_KB_IT_API_URL",
    BASE_URL + "/api/v5/pages/live-tvs/"
)

OUTPUT_DIR = "output"

os.makedirs(OUTPUT_DIR, exist_ok=True)

JSON_FILE = OUTPUT_DIR + "/ALL_CHANNEL_DATA.json"
RAW_FILE = OUTPUT_DIR + "/ALL_API_RESPONSES.json"
M3U_FILE = OUTPUT_DIR + "/BD-KB-IT.m3u8"

MAX_PAGES = 10000
TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": BASE_URL + "/live-tvs"
}

# =====================================
# FIRST PLAYLIST ENTRY
# =====================================

FIRST_CHANNEL = {
    "id": "",
    "name": "IPTV LINKS",
    "logo": "https://raw.githubusercontent.com/Mrbotrx/Mrbotrx/refs/heads/main/IPTV_LINKS_LOGO.jpg",
    "group": "IPTV",
    "url": "https://github.com/Mrbotrx/Mrbotrx/raw/refs/heads/main/IPTV_LINKS_VIDEO.mp4"
}


# =====================================
# API REQUEST
# =====================================

def get_api(url):

    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("HTTPS required")

    if parsed.hostname != "web.aynaott.com":
        raise ValueError("Unexpected API host")

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        return json.loads(
            response.read().decode(
                "utf-8",
                errors="replace"
            )
        )


# =====================================
# NEXT URL
# =====================================

def get_next_url(data, current_url):

    if not isinstance(data, dict):
        return None

    pagination = data.get(
        "blocks_pagination",
        {}
    )

    if not isinstance(pagination, dict):
        return None

    if not pagination.get("has_more", False):
        return None

    next_url = pagination.get("next_url")

    if not next_url:
        raise RuntimeError(
            "Next URL missing while has_more is true"
        )

    next_url = urljoin(current_url, next_url)

    parsed = urlparse(next_url)

    if (
        parsed.scheme != "https"
        or parsed.hostname != "web.aynaott.com"
    ):
        raise ValueError("Invalid next_url")

    return next_url


# =====================================
# EXTRACT CHANNEL ITEMS
# =====================================

def extract_channels(data):

    channels = []

    if not isinstance(data, dict):
        return channels

    blocks = data.get("blocks", [])

    if not isinstance(blocks, list):
        return channels

    for block in blocks:

        if not isinstance(block, dict):
            continue

        group = block.get(
            "title",
            "Uncategorized"
        )

        items = block.get("items", [])

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            channels.append({
                "id": item.get("id", ""),
                "name": item.get("title", ""),
                "slug": item.get("slug", ""),
                "description": item.get(
                    "description", ""
                ),
                "group": group,
                "nav_path": item.get(
                    "nav_path", ""
                ),
                "logo": extract_logo(item),
                "url": extract_authorized_stream(item),
                "access": item.get("access", {})
            })

    return channels


# =====================================
# LOGO EXTRACTION
# =====================================

def extract_logo(item):

    for key in [
        "logo",
        "logo_url",
        "image",
        "thumbnail",
        "icon"
    ]:

        value = item.get(key)

        if isinstance(value, str):
            return value

        if isinstance(value, dict):

            return (
                value.get("url")
                or value.get("src")
                or ""
            )

    return ""


# =====================================
# AUTHORIZED STREAM FIELD
# =====================================

def extract_authorized_stream(item):

    for key in [
        "stream_url",
        "play_url",
        "m3u8_url",
        "playlist_url"
    ]:

        value = item.get(key)

        if isinstance(value, str):

            parsed = urlparse(value)

            if parsed.scheme in ("http", "https"):
                return value

    return ""


# =====================================
# CLEAN TEXT
# =====================================

def clean(value):

    value = str(value or "")

    return re.sub(
        r'[\r\n"]+',
        " ",
        value
    ).strip()


# =====================================
# GENERATE M3U8
# =====================================

def generate_m3u(channels):

    lines = [
        "#EXTM3U"
    ]

    # FIRST ENTRY

    first = FIRST_CHANNEL

    lines.append("")

    lines.append(
        '#EXTINF:-1 tvg-id="" '
        'tvg-name="IPTV LINKS" '
        'tvg-logo="' + first["logo"] + '" '
        'group-title="IPTV",IPTV LINKS'
    )

    lines.append(first["url"])

    # API CHANNELS

    count = 0

    for channel in channels:

        name = clean(channel["name"])

        logo = clean(channel["logo"])

        group = clean(channel["group"])

        channel_id = clean(channel["id"])

        stream = channel["url"]

        if not stream:
            continue

        parsed = urlparse(stream)

        if parsed.scheme not in ("http", "https"):
            continue

        if not parsed.netloc:
            continue

        lines.append("")

        lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{channel_id}" '
            f'tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",'
            f'{name}'
        )

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


# =====================================
# SAVE JSON
# =====================================

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


# =====================================
# MAIN
# =====================================

def main():

    print("=" * 50)
    print("BD KB IT AUTO PLAYLIST")
    print("=" * 50)

    url = API_URL

    visited = set()

    all_pages = []

    all_channels = []

    page = 0

    # FETCH ALL NEXT URLS

    while url:

        if page >= MAX_PAGES:
            raise RuntimeError("Maximum page limit reached")

        if url in visited:
            raise RuntimeError("Pagination loop detected")

        visited.add(url)

        page += 1

        print(f"\nDownloading API Page: {page}")

        data = get_api(url)

        if not isinstance(data, dict):
            raise RuntimeError("Invalid API response")

        all_pages.append(data)

        channels = extract_channels(data)

        all_channels.extend(channels)

        print("Channels found:", len(channels))

        # NEXT API

        url = get_next_url(data, url)

        if url:
            print("Next URL found!")
            time.sleep(0.5)
        else:
            print("All API pages completed!")

    # REMOVE DUPLICATES

    unique_channels = []

    seen = set()

    for channel in all_channels:

        key = channel["id"] or channel["name"]

        if not key or key in seen:
            continue

        seen.add(key)

        unique_channels.append(channel)

    # SAVE RAW API

    save_json(
        RAW_FILE,
        all_pages
    )

    # SAVE COMBINED JSON

    output = {
        "project": "BD-KB-IT",
        "total_pages": len(all_pages),
        "total_channels": len(unique_channels),
        "channels": unique_channels
    }

    save_json(
        JSON_FILE,
        output
    )

    # GENERATE PLAYLIST

    playlist_count = generate_m3u(
        unique_channels
    )

    # FINAL REPORT

    print("\n" + "=" * 50)

    print("UPDATE COMPLETED")

    print("Total Pages:", len(all_pages))

    print("Total Channels:", len(unique_channels))

    print("Playable Entries:", playlist_count)

    print("\nOUTPUT FILES:")

    print(JSON_FILE)
    print(RAW_FILE)
    print(M3U_FILE)

    print("=" * 50)


if __name__ == "__main__":
    main()
