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
# BLOCK FILTER
# =========================
BLOCK_KEYWORDS = {
    "promo", "promote", "advert", "ads",
    ".mp4", "trailer", "sample",
    "click", "subscribe", "telegram"
}

def is_clean(name, url):
    text = (name + " " + url).lower()
    return not any(b in text for b in BLOCK_KEYWORDS)

# =========================
# HEADER
# =========================
def header():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")
    return f"#EXTM3U\n# KBTVPRO AUTO BOT\n# Updated: {now}\n\n"

# =========================
# LOAD SOURCES
# =========================
def get_sources():
    urls = []

    for s in SECRET_NAMES:
        raw = os.getenv(s)

        if not raw:
            print(f"[WARN] Missing secret: {s}")
            continue

        urls.extend([x.strip() for x in raw.split(",") if x.strip()])

    return urls

# =========================
# FETCH WITH RETRY
# =========================
def fetch(url, retries=2):
    headers = {"User-Agent": "Mozilla/5.0"}

    for i in range(retries):
        try:
            r = requests.get(url, timeout=6, headers=headers)
            if r.status_code == 200 and r.text:
                return r.text
        except:
            pass
        time.sleep(1)

    return None

# =========================
# SPEED CHECK (FAST ONLY)
# =========================
def fast_ok(url):
    try:
        start = time.time()
        r = requests.get(url, timeout=4, stream=True)
        if r.status_code != 200:
            return False
        r.raw.read(256)
        return (time.time() - start) < 1.3
    except:
        return False

# =========================
# PARSE M3U
# =========================
def parse(urls):
    channels = []
    seen = set()

    for u in urls:
        text = fetch(u)
        if not text:
            continue

        extinf = None

        for line in text.splitlines():
            line = line.strip()

            if line.startswith("#EXTINF"):
                extinf = line
                continue

            if extinf and line.startswith(("http://", "https://", "rtmp://")):

                name = extinf.split(",")[-1].strip()

                # FILTER
                if not is_clean(name, line):
                    extinf = None
                    continue

                # SPEED FILTER
                if not fast_ok(line):
                    extinf = None
                    continue

                key = (name, line)
                if key in seen:
                    extinf = None
                    continue

                seen.add(key)

                channels.append({
                    "extinf": extinf,
                    "url": line,
                    "name": name
                })

                extinf = None

    return channels

# =========================
# CATEGORY
# =========================
def cat(name):
    n = name.lower()

    if "sport" in n:
        return "SPORTS"
    if "zee" in n or "sony" in n or "star jalsha" in n:
        return "BDXI"
    if "atn" in n or "ntv" in n or "bangla" in n:
        return "BD"
    return "IND"

# =========================
# SAVE FILE
# =========================
def save(path, items):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header())
        for c in items:
            f.write(c["extinf"] + "\n")
            f.write(c["url"] + "\n")

# =========================
# MAIN
# =========================
def main():
    urls = get_sources()

    if not urls:
        print("NO SOURCES FOUND")
        return

    data = parse(urls)

    bdxi, ind, bd, sports = [], [], [], []

    for c in data:
        t = cat(c["name"])

        if t == "BDXI":
            bdxi.append(c)
        elif t == "BD":
            bd.append(c)
        elif t == "SPORTS":
            sports.append(c)
        else:
            ind.append(c)

    save(COMBINED_FILE, data)
    save(BDXI_FILE, bdxi)
    save(IND_FILE, ind)
    save(BD_FILE, bd)
    save(SPORTS_FILE, sports)

    print("\n===== FINAL REPORT =====")
    print("TOTAL:", len(data))
    print("BDXI:", len(bdxi))
    print("IND:", len(ind))
    print("BD:", len(bd))
    print("SPORTS:", len(sports))

if __name__ == "__main__":
    main()
