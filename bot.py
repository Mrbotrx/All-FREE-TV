import os
import asyncio
import aiohttp
import time
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
# FILTER
# =========================
BLOCK = {
    "promo", "promote", "advert", "ads",
    ".mp4", "trailer", "sample",
    "click", "subscribe", "telegram"
}

def clean(name, url):
    text = (name + " " + url).lower()
    return not any(b in text for b in BLOCK)

# =========================
# HEADER
# =========================
def header():
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")
    return f"#EXTM3U\n# KBTVPRO ULTRA BOT\n# Updated: {now}\n\n"

# =========================
# SOURCES
# =========================
def get_sources():
    urls = []
    for s in SECRET_NAMES:
        raw = os.getenv(s)
        if raw:
            urls += [x.strip() for x in raw.split(",") if x.strip()]
    return urls

# =========================
# ASYNC FETCH + DEAD FILTER
# =========================
async def fetch(session, url):
    try:
        start = time.time()

        async with session.get(url, timeout=10) as r:
            if r.status != 200:
                return None

            text = await r.text()

            # DEAD STREAM FILTER (FAST CHECK)
            if (time.time() - start) > 2.8:
                return None

            return text

    except:
        return None

# =========================
# PARSE M3U
# =========================
def parse(text):
    channels = []
    extinf = None

    for line in text.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF"):
            extinf = line
            continue

        if extinf and line.startswith("http"):
            name = extinf.split(",")[-1].strip()

            if clean(name, line):
                channels.append({
                    "extinf": extinf,
                    "url": line,
                    "name": name
                })

            extinf = None

    return channels

# =========================
# WORKER (ASYNC PARALLEL)
# =========================
async def worker(urls):
    connector = aiohttp.TCPConnector(limit=40)
    async with aiohttp.ClientSession(connector=connector) as session:

        tasks = [fetch(session, u) for u in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []

    for r in results:
        if r:
            all_channels.extend(parse(r))

    return all_channels

# =========================
# CATEGORY
# =========================
def cat(name):
    n = name.lower()

    if "sport" in n:
        return "SPORTS"
    if "zee" in n or "sony" in n:
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
# READ FILE
# =========================
def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

# =========================
# BUILD COMBINED (MERGE ALL FILES)
# =========================
def build_combined():
    files = [
        BDXI_FILE,
        IND_FILE,
        BD_FILE,
        SPORTS_FILE
    ]

    content = header()

    for f in files:
        data = read_file(f)
        data = data.replace("#EXTM3U", "").strip()

        content += f"\n# ===== {os.path.basename(f)} =====\n"
        content += data + "\n"

    with open(COMBINED_FILE, "w", encoding="utf-8") as f:
        f.write(content)

# =========================
# MAIN
# =========================
async def main():
    urls = get_sources()

    if not urls:
        print("NO SOURCES FOUND")
        return

    data = await worker(urls)

    # REMOVE DUPLICATES
    seen = set()
    unique = []

    for c in data:
        key = (c["name"], c["url"])
        if key not in seen:
            seen.add(key)
            unique.append(c)

    # SPLIT CATEGORY
    bdxi, ind, bd, sports = [], [], [], []

    for c in unique:
        t = cat(c["name"])

        if t == "BDXI":
            bdxi.append(c)
        elif t == "BD":
            bd.append(c)
        elif t == "SPORTS":
            sports.append(c)
        else:
            ind.append(c)

    # SAVE FILES
    save(BDXI_FILE, bdxi)
    save(IND_FILE, ind)
    save(BD_FILE, bd)
    save(SPORTS_FILE, sports)

    # BUILD MASTER FILE (IMPORTANT)
    build_combined()

    # =========================
    # REPORT
    # =========================
    print("\n===== FINAL REPORT =====")
    print("TOTAL   :", len(unique))
    print("BDXI    :", len(bdxi))
    print("IND     :", len(ind))
    print("BD      :", len(bd))
    print("SPORTS  :", len(sports))
    print("========================\n")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    asyncio.run(main())
