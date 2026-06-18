import os
import requests
from datetime import datetime
import pytz

# ==========================================
# GitHub Secrets
# ==========================================
SECRET_NAMES = [
    "KBTVPRO1",
    "KBTVPRO2",
    "KBTVPRO3"
]

# ==========================================
# Output Folder
# ==========================================
OUTPUT_DIR = "KBPROTV"
os.makedirs(OUTPUT_DIR, exist_ok=True)

COMBINED_FILE = os.path.join(
    OUTPUT_DIR,
    "combined_playlist.m3u"
)

BDXI_FILE = os.path.join(
    OUTPUT_DIR,
    "bdxikb.m3u"
)

IND_FILE = os.path.join(
    OUTPUT_DIR,
    "Ind_bd.m3u8"
)

BD_FILE = os.path.join(
    OUTPUT_DIR,
    "Bd_KBPRO.m3u8"
)

SPORTS_FILE = os.path.join(
    OUTPUT_DIR,
    "Sports_promax.m3u8"
)


def build_header():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")

    return f"""#EXTM3U
# =====================================
# KBPROTV AUTO PLAYLIST
# Updated: {now}
# =====================================

"""


def get_sources():
    sources = []

    for secret in SECRET_NAMES:
        value = os.getenv(secret)

        if not value:
            print(f"[!] Missing Secret: {secret}")
            continue

        sources.extend(
            [x.strip() for x in value.split(",") if x.strip()]
        )

    return sources


def parse_sources(sources):
    channels = []
    seen = set()

    for source in sources:
        try:
            print(f"Fetching: {source}")

            r = requests.get(
                source,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            lines = r.text.splitlines()

            extinf = None

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                if line.startswith("#EXTINF"):
                    extinf = line
                    continue

                if extinf and line.startswith(
                    ("http://", "https://", "rtmp://")
                ):

                    name = extinf.split(",")[-1].strip()

                    key = (
                        name.lower(),
                        line.strip()
                    )

                    if key in seen:
                        extinf = None
                        continue

                    seen.add(key)

                    channels.append({
                        "name": name,
                        "extinf": extinf,
                        "url": line
                    })

                    extinf = None

        except Exception as e:
            print(f"Error: {e}")

    return channels


def detect_category(name):
    text = name.lower()

    sports_keywords = [
        "sport",
        "sports",
        "cricket",
        "football",
        "star sports",
        "sony sports",
        "ten sports",
        "t sports",
        "willow"
    ]

    bdxi_keywords = [
        "star jalsha",
        "zee bangla",
        "colors bangla",
        "sony aath"
    ]

    bd_keywords = [
        "channel i",
        "atn",
        "atn bangla",
        "ntv",
        "rtv",
        "ekattor",
        "somoy",
        "dbc",
        "banglavision",
        "desh tv",
        "boishakhi"
    ]

    if any(k in text for k in sports_keywords):
        return "SPORTS"

    if any(k in text for k in bdxi_keywords):
        return "BDXI"

    if any(k in text for k in bd_keywords):
        return "BD"

    return "IND"


def save_playlist(filename, channels):
    content = build_header()

    for ch in channels:
        content += ch["extinf"] + "\n"
        content += ch["url"] + "\n"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(content)


def main():
    sources = get_sources()

    if not sources:
        print("No sources found.")
        return

    channels = parse_sources(sources)

    bdxi = []
    ind = []
    bd = []
    sports = []

    for ch in channels:

        category = detect_category(
            ch["name"]
        )

        if category == "BDXI":
            bdxi.append(ch)

        elif category == "BD":
            bd.append(ch)

        elif category == "SPORTS":
            sports.append(ch)

        else:
            ind.append(ch)

    save_playlist(
        COMBINED_FILE,
        channels
    )

    save_playlist(
        BDXI_FILE,
        bdxi
    )

    save_playlist(
        IND_FILE,
        ind
    )

    save_playlist(
        BD_FILE,
        bd
    )

    save_playlist(
        SPORTS_FILE,
        sports
    )

    print("\n==============================")
    print("      KBPROTV REPORT")
    print("==============================")

    print(f"BDXI     : {len(bdxi)}")
    print(f"IND      : {len(ind)}")
    print(f"BD       : {len(bd)}")
    print(f"SPORTS   : {len(sports)}")

    print("------------------------------")
    print(f"TOTAL    : {len(channels)}")
    print("------------------------------")

    print("\nGenerated Files:")
    print(COMBINED_FILE)
    print(BDXI_FILE)
    print(IND_FILE)
    print(BD_FILE)
    print(SPORTS_FILE)


if __name__ == "__main__":
    main()
