import os
import time
import requests
from datetime import datetime
import pytz

# =========================
# CONFIG
# =========================
SECRET_NAMES = ["KBTVPRO1", "KBTVPRO2", "KBTVPRO3"]

OUTPUT_DIR = "KBPROTV"
os.makedirs(OUTPUT_DIR, exist_ok=True)

COMBINED_FILE = "combined_playlist.m3u"

BDXI_FILE = os.path.join(OUTPUT_DIR, "bdxikb.m3u")
IND_FILE = os.path.join(OUTPUT_DIR, "Ind_bd.m3u8")
BD_FILE = os.path.join(OUTPUT_DIR, "Bd_KBPRO.m3u8")
SPORTS_FILE = os.path.join(OUTPUT_DIR, "Sports_promax.m3u8")


# =========================
# HEADER
# =========================
def build_header():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")

    return f"""#EXTM3U
# AUTO KBPROTV BOT
# Updated: {now}

"""


# =========================
# LOAD SOURCES
# =========================
def get_sources():
    sources = []

    for secret in SECRET_NAMES:
        raw = os.getenv(secret)

        if not raw:
            print(f"[!] Missing secret: {secret}")
            continue

        sources.extend([x.strip() for x in raw.split(",") if x.strip()])

    return sources


# =========================
# RETRY FETCH (M3U TEXT)
# =========================
def fetch_with_retry(url, retries=3, timeout=10):
    headers = {"User-Agent": "Mozilla/5.0"}

    for i in range(1, retries + 1):
        try:
            print(f"[FETCH TRY {i}] {url}")

            r = requests.get(url, timeout=timeout, headers=headers)

            if r.status_code == 200 and r.text:
                return r.text

        except Exception as e:
            print(f"[ERROR TRY {i}] {e}")

        time.sleep(1)

    print(f"[SKIP] Failed: {url}")
    return None


# =========================
# SPEED CHECK (FAST ONLY)
# =========================
def is_fast(url):
    headers = {"User-Agent": "Mozilla/5.0"}

    for i in range(1, 3):
        try:
            start = time.time()

            r = requests.get(
                url,
                timeout=6,
                stream=True,
                headers=headers
            )

            if r.status_code != 200:
                continue

            r.raw.read(1024)

            speed = time.time() - start

            if speed < 1.5:
                return True

        except:
            pass

        time.sleep(0.5)

    return False


# =========================
# PARSE M3U
# =========================
def parse_sources(urls):
    channels = []
    seen = set()

    for url in urls:
        text = fetch_with_retry(url)

        if not text:
            continue

        lines = text.splitlines()
        extinf = None

        for line in lines:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#EXTINF"):
                extinf = line
                continue

            if extinf and line.startswith(("http://", "https://", "rtmp://")):

                name = extinf.split(",")[-1].strip()

                # speed filter
                if not is_fast(line):
                    extinf = None
                    continue

                key = (name.lower(), line)

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

    return channels


# =========================
# CATEGORY SYSTEM
# =========================
def get_category(name):
    n = name.lower()

    sports = ["sport", "cricket", "football", "ten sports", "star sports"]
    bdxi = ["zee", "star jalsha", "colors", "sony aath"]
    bd = ["atn", "ntv", "rtv", "channel i", "bangla", "somoy", "ekattor"]

    if any(x in n for x in sports):
        return "SPORTS"

    if any(x in n for x in bdxi):
        return "BDXI"

    if any(x in n for x in bd):
        return "BD"

    return "IND"


# =========================
# SAVE FILE
# =========================
def save_file(path, items):
    content = build_header()

    for ch in items:
        content += ch["extinf"] + "\n"
        content += ch["url"] + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# =========================
# MAIN
# =========================
def main():
    urls = get_sources()

    if not urls:
        print("No sources found!")
        return

    channels = parse_sources(urls)

    bdxi, ind, bd, sports = [], [], [], []

    for ch in channels:
        cat = get_category(ch["name"])

        if cat == "BDXI":
            bdxi.append(ch)
        elif cat == "BD":
            bd.append(ch)
        elif cat == "SPORTS":
            sports.append(ch)
        else:
            ind.append(ch)

    # SAVE FILES
    save_file(COMBINED_FILE, channels)
    save_file(BDXI_FILE, bdxi)
    save_file(IND_FILE, ind)
    save_file(BD_FILE, bd)
    save_file(SPORTS_FILE, sports)

    # REPORT
    print("\n========== FINAL REPORT ==========")
    print("BDXI   :", len(bdxi))
    print("IND    :", len(ind))
    print("BD     :", len(bd))
    print("SPORTS :", len(sports))
    print("---------------------------------")
    print("TOTAL  :", len(channels))
    print("=================================\n")

    print("FILES CREATED:")
    print(COMBINED_FILE)
    print(BDXI_FILE)
    print(IND_FILE)
    print(BD_FILE)
    print(SPORTS_FILE)


if __name__ == "__main__":
    main()
