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

MAX_PAGES = 10000
TIMEOUT = 30
DELAY = 0.5

os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": BASE_URL + "/live-tvs"
}

# ==========================================
# IPTV LINKS FIRST ENTRY
# ==========================================

FIRST_CHANNEL = {
    "id": "",
    "name": "IPTV LINKS",
    "logo": (
        "https://raw.githubusercontent.com/"
        "Mrbotrx/Mrbotrx/refs/heads/main/"
        "IPTV_LINKS_LOGO.jpg"
    ),
    "group": "IPTV",
    "url": (
        "https://github.com/Mrbotrx/Mrbotrx/"
        "raw/refs/heads/main/IPTV_LINKS_VIDEO.mp4"
    )
}


# ==========================================
# VALIDATE URL
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

    next_url = pagination.get("next_url")

    if not has_more:
        return None

    if not next_url:

        raise RuntimeError(
            "has_more=true but next_url is missing"
        )

    next_url = urljoin(
        current_url,
        next_url
    )

    return validate_url(next_url)


# ==========================================
# EXTRACT BLOCK ITEMS
# ==========================================

def extract_records(data):

    records = []

    if not isinstance(data, dict):
        return records

    blocks = data.get("blocks", [])

    if not isinstance(blocks, list):
        return records

    for block in blocks:

        if not isinstance(block, dict):
            continue

        block_title = block.get(
            "title",
            "Uncategorized"
        )

        items = block.get("items", [])

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            records.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "slug": item.get("slug", ""),
                "description": item.get(
                    "description", ""
                ),
                "nav_path": item.get(
                    "nav_path", ""
                ),
                "type": item.get("type", ""),
                "group": block_title,
                "access": item.get(
                    "access", {}
                ),
                "access_verdict": item.get(
                    "access_verdict", {}
                ),
                "images": item.get(
                    "images", []
                )
            })

    return records


# ==========================================
# EXTRACT LOGO
# ==========================================

def extract_logo(item):

    for key in [
        "logo",
        "logo_url",
        "image",
        "thumbnail",
        "icon"
    ]:

        value = item.get(key)

        if isinstance(value, str) and value:
            return value

        if isinstance(value, dict):

            for subkey in ["url", "src"]:
                if value.get(subkey):
                    return value[subkey]

    images = item.get("images")

    if isinstance(images, list):

        for image in images:

            if isinstance(image, dict):

                value = (
                    image.get("url")
                    or image.get("src")
                )

                if value:
                    return value

    return ""


# ==========================================
# NORMALIZE CHANNEL METADATA
# ==========================================

def normalize_channel(item):

    if not isinstance(item, dict):
        return None

    name = item.get("title")

    if not name:
        return None

    access = item.get("access", {})

    if not isinstance(access, dict):
        access = {}

    verdict = item.get(
        "access_verdict",
        {}
    )

    if not isinstance(verdict, dict):
        verdict = {}

    return {
        "id": str(item.get("id", "")),
        "name": str(name),
        "logo": extract_logo(item),
        "group": str(
            item.get("group") or "Uncategorized"
        ),
        "slug": str(item.get("slug", "")),
        "description": str(
            item.get("description", "")
        ),
        "nav_path": str(
            item.get("nav_path", "")
        ),
        "type": str(item.get("type", "")),
        "access_level": str(
            access.get("level", "")
        ),
        "access_allowed": verdict.get(
            "allowed", False
        )
    }


# ==========================================
# CLEAN TEXT
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
# M3U GENERATOR
# ==========================================

def generate_m3u(channels):

    lines = [
        "#EXTM3U"
    ]

    # First fixed entry

    first = FIRST_CHANNEL

    lines.append("")

    lines.append(
        '#EXTINF:-1 '
        'tvg-id="" '
        'tvg-name="IPTV LINKS" '
        f'tvg-logo="{first["logo"]}" '
        'group-title="IPTV",IPTV LINKS'
    )

    lines.append(first["url"])

    # Channel metadata entries.
    # Protected subscription streams are not
    # resolved or extracted by this script.

    for channel in channels:

        name = clean_text(channel["name"])

        logo = clean_text(channel["logo"])

        group = clean_text(channel["group"])

        channel_id = clean_text(channel["id"])

        # The API object shown contains channel
        # metadata, not a direct playback URL.
        # Only an explicitly authorized URL can
        # be added to a playable playlist.

        stream = channel.get(
            "authorized_stream_url",
            ""
        )

        parsed = urlparse(stream)

        if parsed.scheme not in ("http", "https"):
            continue

        if not parsed.netloc:
            continue

        lines.append("")

        lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{name if not channel_id else channel_id}" '
            f'tvg-name="{name}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",'
            f'{name}'
        )

        lines.append(stream)

    with open(
        M3U_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            "\n".join(lines) + "\n"
        )


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
# MAIN
# ==========================================

def main():

    print("=" * 55)
    print("       BD KB IT AUTO UPDATE")
    print("=" * 55)

    url = API_URL

    visited = set()

    all_pages = []

    all_records = []

    page = 0

    # ======================================
    # FETCH ALL API PAGES
    # ======================================

    while url:

        if page >= MAX_PAGES:

            raise RuntimeError(
                "Maximum page limit reached"
            )

        if url in visited:

            raise RuntimeError(
                "Pagination loop detected"
            )

        visited.add(url)

        page += 1

        print(f"\n[PAGE {page}] Downloading")

        data = get_api(url)

        if not isinstance(data, dict):
            raise RuntimeError(
                "Unexpected API response"
            )

        all_pages.append(data)

        records = extract_records(data)

        all_records.extend(records)

        print("Channels/Items:", len(records))

        url = get_next_page(
            data,
            url
        )

        if url:
            print("[+] Next URL found")

            time.sleep(DELAY)

        else:
            print("[+] All pages completed")

    # ======================================
    # NORMALIZE CHANNELS
    # ======================================

    channels = []

    seen = set()

    for record in all_records:

        channel = normalize_channel(record)

        if not channel:
            continue

        key = channel["id"] or channel["name"]

        if key in seen:
            continue

        seen.add(key)

        channels.append(channel)

    # ======================================
    # SAVE RAW API DATA
    # ======================================

    save_json(
        RAW_FILE,
        all_pages
    )

    # ======================================
    # SAVE CHANNEL JSON
    # ======================================

    output = {
        "project": "BD-KB-IT",
        "total_pages": len(all_pages),
        "total_records": len(all_records),
        "total_channels": len(channels),
        "channels": channels
    }

    save_json(
        JSON_FILE,
        output
    )

    # ======================================
    # GENERATE PLAYLIST
    # ======================================

    generate_m3u(channels)

    # ======================================
    # FINAL REPORT
    # ======================================

    print("\n" + "=" * 55)

    print("UPDATE SUCCESSFUL")

    print("Total Pages:", len(all_pages))

    print("Total Records:", len(all_records))

    print("Total Channels:", len(channels))

    print("\nOUTPUT:")

    print(JSON_FILE)

    print(RAW_FILE)

    print(M3U_FILE)

    print("=" * 55)


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    main()
