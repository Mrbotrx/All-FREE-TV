import os
import re
import json
import time
import urllib.request
import urllib.error

from urllib.parse import urljoin, urlparse
from pathlib import Path


# ==========================================
# BD-KB-IT CONFIGURATION
# ==========================================

BASE_URL = "https://web.aynaott.com"

DEFAULT_API_URL = (
    "https://web.aynaott.com/api/v5/pages/live-tvs/"
)

API_URL = os.environ.get(
    "BD_KB_IT_API_URL",
    DEFAULT_API_URL
)

OUTPUT_DIR = Path("output")

PLAYLIST_FILE = OUTPUT_DIR / "BD-KB-IT.m3u8"
CHANNEL_FILE = OUTPUT_DIR / "ALL_CHANNEL_DATA.json"
RAW_FILE = OUTPUT_DIR / "ALL_API_RESPONSES.json"

MAX_PAGES = 10000
TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://web.aynaott.com/live-tvs"
}

IPTV_LOGO = (
    "https://raw.githubusercontent.com/"
    "Mrbotrx/Mrbotrx/refs/heads/main/IPTV_LINKS_LOGO.jpg"
)

IPTV_VIDEO = (
    "https://github.com/Mrbotrx/Mrbotrx/raw/"
    "refs/heads/main/IPTV_LINKS_VIDEO.mp4"
)


# ==========================================
# CREATE OUTPUT DIRECTORY
# ==========================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# SAFE API REQUEST
# ==========================================

def get_api(url):

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
# GET PAGINATION INFORMATION
# ==========================================

def get_next_page(data, current_url):

    if not isinstance(data, dict):
        return None

    pagination = data.get("blocks_pagination")

    if not isinstance(pagination, dict):
        pagination = data.get("pagination", {})

    if not isinstance(pagination, dict):
        return None

    has_more = pagination.get("has_more", False)

    if not has_more:
        return None

    next_url = pagination.get("next_url")

    if next_url:
        next_url = urljoin(current_url, next_url)

        parsed = urlparse(next_url)

        # Pagination must remain on the official API host.
        if (
            parsed.scheme != "https"
            or parsed.hostname != "web.aynaott.com"
        ):
            raise ValueError(
                "Rejected unexpected pagination URL"
            )

        return next_url

    return None


# ==========================================
# EXTRACT CHANNELS FROM BLOCKS
# ==========================================

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

        group = block.get("title", "Uncategorized")

        items = block.get("items", [])

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            channel = dict(item)

            channel["_group"] = group

            channels.append(channel)

    return channels


# ==========================================
# GET CHANNEL LOGO
# ==========================================

def get_logo(channel):

    possible_keys = [
        "logo",
        "logo_url",
        "image",
        "image_url",
        "thumbnail",
        "thumbnail_url",
        "icon"
    ]

    for key in possible_keys:

        value = channel.get(key)

        if isinstance(value, str) and value.startswith("http"):
            return value

    images = channel.get("images")

    if isinstance(images, dict):

        for value in images.values():

            if isinstance(value, str) and value.startswith("http"):
                return value

            if isinstance(value, dict):

                image_url = (
                    value.get("url")
                    or value.get("original")
                    or value.get("src")
                )

                if isinstance(image_url, str):
                    if image_url.startswith("http"):
                        return image_url

    return ""


# ==========================================
# GET DIRECT AUTHORIZED STREAM URL
# ==========================================

def get_stream_url(channel):

    allowed_keys = {
        "stream_url",
        "play_url",
        "m3u8_url",
        "playlist_url"
    }

    def search(obj):

        if isinstance(obj, dict):

            for key, value in obj.items():

                if key.lower() in allowed_keys:

                    if isinstance(value, str):
                        if value.startswith(("https://", "http://")):
                            return value

                if isinstance(value, (dict, list)):

                    found = search(value)

                    if found:
                        return found

        elif isinstance(obj, list):

            for item in obj:

                found = search(item)

                if found:
                    return found

        return None

    return search(channel)


# ==========================================
# CLEAN M3U TEXT
# ==========================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = re.sub(r'[\r\n"]+', " ", value)

    return value.strip()


# ==========================================
# SAVE M3U8 PLAYLIST
# ==========================================

def save_playlist(channels):

    total = 0

    with open(
        PLAYLIST_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        # Automatic M3U Header
        file.write("#EXTM3U\n\n")

        # Fixed First Entry
        file.write(
            f'#EXTINF:-1 tvg-id="" '
            f'tvg-name="IPTV LINKS" '
            f'tvg-logo="{IPTV_LOGO}" '
            f'group-title="KB PRO TV",IPTV LINKS\n'
        )

        file.write(IPTV_VIDEO + "\n\n")

        # API Channels
        for channel in channels:

            title = clean_text(
                channel.get("title", "Unknown Channel")
            )

            group = clean_text(
                channel.get("_group", "Uncategorized")
            )

            logo = clean_text(
                get_logo(channel)
            )

            stream_url = get_stream_url(channel)

            # Never use nav_path as a playback URL.
            if not stream_url:
                continue

            file.write(
                f'#EXTINF:-1 '
                f'tvg-id="" '
                f'tvg-name="{title}" '
                f'tvg-logo="{logo}" '
                f'group-title="{group}",{title}\n'
            )

            file.write(stream_url + "\n\n")

            total += 1

    print("[OK] Playlist created:", PLAYLIST_FILE)
    print("[OK] Playable API channels:", total)

    return total


# ==========================================
# SAVE JSON
# ==========================================

def save_json(path, data):

    with open(
        path,
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

    print("=" * 50)
    print("          BD-KB-IT PLAYLIST BUILDER")
    print("=" * 50)

    all_pages = []
    all_channels = []

    visited_urls = set()

    current_url = API_URL

    for page_number in range(1, MAX_PAGES + 1):

        if not current_url:
            break

        if current_url in visited_urls:

            print("[WARNING] Pagination loop detected.")
            break

        visited_urls.add(current_url)

        print(f"\n[+] Downloading Page {page_number}")

        try:

            data = get_api(current_url)

            if not isinstance(data, dict):
                raise ValueError("Invalid API response")

            all_pages.append(data)

            channels = extract_channels(data)

            all_channels.extend(channels)

            # Save individual page
            page_file = OUTPUT_DIR / (
                f"page_{page_number:03d}.json"
            )

            save_json(page_file, data)

            print("[OK] Page saved:", page_file)
            print("[+] Channels found:", len(channels))

            # Follow next_url
            current_url = get_next_page(
                data,
                current_url
            )

            if not current_url:

                print("\n[+] No more pages.")
                break

            time.sleep(0.5)

        except urllib.error.HTTPError as error:

            print(
                f"[ERROR] HTTP {error.code}: {error.reason}"
            )

            raise

        except Exception as error:

            print("[ERROR]", str(error))
            raise

    else:

        raise RuntimeError(
            "Maximum page limit reached. "
            "Pagination may not have finished."
        )

    # Remove duplicate channels by ID or slug.
    unique_channels = []
    seen = set()

    for channel in all_channels:

        identifier = (
            channel.get("id")
            or channel.get("slug")
            or channel.get("title")
        )

        if not identifier:
            identifier = json.dumps(
                channel,
                sort_keys=True,
                ensure_ascii=False
            )

        if identifier in seen:
            continue

        seen.add(identifier)
        unique_channels.append(channel)

    # Save combined channel data
    save_json(
        CHANNEL_FILE,
        unique_channels
    )

    # Save all raw API responses
    save_json(
        RAW_FILE,
        all_pages
    )

    # Create M3U8 playlist
    playable_count = save_playlist(
        unique_channels
    )

    print("\n" + "=" * 50)
    print("             UPDATE COMPLETED")
    print("=" * 50)

    print("Total API Pages:", len(all_pages))
    print("Total Channels:", len(unique_channels))
    print("Playable Channels:", playable_count)

    print("\nOutput Files:")
    print(PLAYLIST_FILE)
    print(CHANNEL_FILE)
    print(RAW_FILE)

    print("=" * 50)


if __name__ == "__main__":
    main()
