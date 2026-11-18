import os
import json
import time
import urllib.request
import urllib.parse
from urllib.parse import urlparse

# =====================================
# CONFIGURATION
# =====================================

API_URL = os.environ.get(
    "BD_KB_IT_API_URL",
    "https://web.aynaott.com/api/v5/pages/live-tvs/"
)

OUTPUT_DIR = "output"

MAX_PAGES = 100
TIMEOUT = 30

os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://web.aynaott.com/live-tvs"
}


# =====================================
# API REQUEST
# =====================================

def get_api(url):

    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ValueError("HTTPS required")

    if parsed.hostname != "web.aynaott.com":
        raise ValueError("Unexpected API hostname")

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


# =====================================
# PAGINATION
# =====================================

def get_next_page(data):

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

    if has_more and next_url:

        return next_url

    return None


# =====================================
# EXTRACT RECORDS
# =====================================

def extract_records(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in [
        "results",
        "items",
        "data",
        "blocks",
        "channels"
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):

            for subkey in [
                "results",
                "items",
                "blocks",
                "channels"
            ]:

                if isinstance(
                    value.get(subkey),
                    list
                ):
                    return value[subkey]

    return []


# =====================================
# MAIN
# =====================================

def main():

    print("=" * 45)
    print("BD KB IT API AUTO DOWNLOADER")
    print("=" * 45)

    all_pages = []
    all_records = []

    visited = set()

    url = API_URL

    for page in range(1, MAX_PAGES + 1):

        if not url:
            break

        if url in visited:

            raise RuntimeError(
                "Pagination loop detected"
            )

        visited.add(url)

        print(f"\nDownloading Page {page}")

        data = get_api(url)

        if not isinstance(data, (dict, list)):
            raise ValueError("Invalid API response")

        all_pages.append(data)

        records = extract_records(data)

        all_records.extend(records)

        print("Records:", len(records))

        next_url = get_next_page(data)

        if not next_url:

            print("No more pages.")

            break

        url = next_url

        time.sleep(0.5)

    else:

        raise RuntimeError(
            "Maximum page limit reached"
        )

    # =================================
    # SAVE RAW JSON
    # =================================

    with open(
        os.path.join(
            OUTPUT_DIR,
            "ALL_API_RESPONSES.json"
        ),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_pages,
            file,
            indent=4,
            ensure_ascii=False
        )

    # =================================
    # SAVE COMBINED JSON
    # =================================

    with open(
        os.path.join(
            OUTPUT_DIR,
            "ALL_CHANNEL_DATA.json"
        ),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_records,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\n" + "=" * 45)

    print("UPDATE COMPLETED")

    print("Total Pages:", len(all_pages))

    print("Total Records:", len(all_records))

    print("Output:", OUTPUT_DIR)

    print("=" * 45)


if __name__ == "__main__":
    main()
