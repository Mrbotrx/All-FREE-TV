import os
import requests
from datetime import datetime
import pytz
import time

EXCLUDED_KEYWORDS = {
    "promo", ".mp4",
    "islam", "quran", "madani", "peace tv",
    "church", "christian", "bible",
    "hindu", "temple", "buddhist",
    "religious", "waaz", "namaz"
}


# ---------- YOUR HEADER (UNCHANGED) ----------
def build_header():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")

    return f"""#EXTM3U
# =====================================
#  AUTO IPTV PLAYLIST
#  Website: https://kbtvpro.totalh.net/
#  Updated: {now} (Bangladesh Time)
#  Source: KBTVPRO Auto Bot
#  Developer: Mrbot × KB CYBER TEAM
# =====================================

"""


def should_skip(text):
    text = text.lower()
    return any(k in text for k in EXCLUDED_KEYWORDS)


def get_category(name):
    name = name.lower()

    if any(x in name for x in ["sport", "cricket", "football"]):
        return "Sports"
    if any(x in name for x in ["news", "bbc", "cnn"]):
        return "News"
    if any(x in name for x in ["movie", "film", "cinema"]):
        return "Movies"

    return "Others"


# ---------- SPEED TEST ----------
def check_speed(url):
    try:
        start = time.time()

        r = requests.get(
            url,
            timeout=5,
            stream=True,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if r.status_code != 200:
            return None

        r.raw.read(1024)
        end = time.time()

        return round(end - start, 3)

    except:
        return None


def fetch_links():
    sources_raw = os.getenv("KBTVPRO")

    if not sources_raw:
        print("KBTVPRO missing")
        return

    sources = [s.strip() for s in sources_raw.split(",") if s.strip()]

    channels = []
    seen = set()

    for url in sources:
        try:
            print("Fetching:", url)

            res = requests.get(url, timeout=20)
            lines = res.text.splitlines()

            extinf = None
            name = None

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                # ---------- CHANNEL NAME ----------
                if line.startswith("#EXTINF"):
                    name = line.split(",")[-1].strip()

                    if should_skip(name):
                        extinf = None
                        name = None
                        continue

                    extinf = line
                    continue

                # ---------- STREAM URL ----------
                if extinf and line.startswith(("http://", "https://", "rtmp://")):

                    if should_skip(line):
                        extinf = None
                        name = None
                        continue

                    key = (name.lower(), line)

                    if key in seen:
                        extinf = None
                        name = None
                        continue

                    # DEAD + SPEED CHECK
                    speed = check_speed(line)

                    if speed is None:
                        extinf = None
                        name = None
                        continue

                    seen.add(key)

                    channels.append({
                        "name": name,
                        "extinf": extinf,
                        "url": line,
                        "speed": speed,
                        "category": get_category(name)
                    })

                    extinf = None
                    name = None

        except Exception as e:
            print("Error:", e)

    # ---------- FASTEST FIRST ----------
    channels.sort(key=lambda x: x["speed"])

    output = build_header()

    for cat in ["Sports", "News", "Movies", "Others"]:
        output += f"# ===== {cat} =====\n"

        for ch in channels:
            if ch["category"] == cat:
                output += ch["extinf"] + "\n"
                output += ch["url"] + "\n"

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Done! {len(channels)} working channels saved.")


if __name__ == "__main__":
    fetch_links()
