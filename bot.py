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
BD_FILE = os.path.join(OUTPUT_DIR, "Bd_KBPRO.m3u8")
IND_FILE = os.path.join(OUTPUT_DIR, "Ind_bd.m3u8")
SPORTS_FILE = os.path.join(OUTPUT_DIR, "Sports_promax.m3u8")

# =========================
# BLOCK FILTER (STRICT)
# =========================
BLOCK = {
    "promo", "promote", "advert", "ads", "advertisement",
    "sample", "trailer", "preview",
    "telegram", "click", "subscribe", "join",
    ".mp4", "mp4", ".mkv", ".avi", ".mov"
}

# =========================
# HD + LIVE KEYWORDS
# =========================
HD = {"hd", "1080", "720", "fhd", "uhd", "4k"}
LIVE = {"live", "sports", "news", "entertainment"}

# =========================
# AI SCORE SYSTEM
# =========================
def ai_score(name, url, resp_time):
    text = (name + " " + url).lower()
    score = 0

    if any(b in text for b in BLOCK):
        return 0

    if any(h in text for h in HD):
        score += 40

    if any(l in text for l in LIVE):
        score += 20

    if "m3u8" in url.lower():
        score += 20

    if resp_time < 1.0:
        score += 20
    elif resp_time < 2.0:
        score += 10

    return score

# =========================
# HEADER (v5 - BEST)
# =========================
def header(total=0, bdxi=0, ind=0, bd=0, sports=0):
    tz = pytz.timezone("Asia/Dhaka")
    now = datetime.now(tz)
    date = now.strftime("%d-%m-%Y")
    time = now.strftime("%I:%M %p")

    return f"""╔══════════════════════════════════════╗
║         🔥 KB PRO IPTV V67 🔥        ║
╚══════════════════════════════════════╝

📊 PLAYLIST STATISTICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 TOTAL CHANNELS : {total}
🇧🇩 BDXI CHANNELS : {bdxi}
🇧৩ BD CHANNELS   : {bd}
🇮৩ IND CHANNELS  : {ind}
🏆 SPORTS         : {sports}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 UPDATE DATE    : {date}
🕒 UPDATE TIME    : {time}
🌍 TIMEZONE       : Asia/Dhaka
⚡ STATUS         : ONLINE
🔄 AUTO UPDATED   : SUCCESS

💎 Premium IPTV Playlist
🚀 Fast • Stable • Auto Updated
"""

# =========================
# GET SOURCES
# =========================
def get_sources():
    urls = []
    for s in SECRET_NAMES:
        raw = os.getenv(s)
        if raw:
            urls += [x.strip() for x in raw.split(",") if x.strip()]
    return urls

# =========================
# FETCH (Fast)
# =========================
async def fetch(session, url):
    try:
        start = time.time()
        async with session.get(url, timeout=2.5) as r:
            if r.status != 200:
                return None
            text = await r.text()
            resp_time = time.time() - start
            return text, resp_time
    except:
        return None

# =========================
# PARSE + SCORE FILTER
# =========================
def parse(text, resp_time):
    channels = []
    extinf = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            extinf = line
            continue
        if extinf and line.startswith("http"):
            name = extinf.split(",")[-1].strip()
            score = ai_score(name, line, resp_time)
            if score >= 70:
                new_name = name + " KB"
                channels.append({
                    "extinf": extinf,
                    "url": line,
                    "name": new_name
                })
            extinf = None
    return channels

# =========================
# WORKER (Fast)
# =========================
async def worker(urls):
    connector = aiohttp.TCPConnector(limit=50)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch(session, u) for u in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []
    for r in results:
        if r:
            text, rt = r
            all_channels.extend(parse(text, rt))
    return all_channels

# =========================
# CATEGORY (খুব স্ট্রিক্ট)
# =========================
def cat(name):
    n = name.lower()
    if "sport" in n:
        return "SPORTS"
    if "zee" in n or "sony" in n:
        return "BDXI"
    if "atn" in n or "ntv" in n or "bangla" in n:
        return "BD"
    if "hindi" in n or "bollywood" in n:
        return "HINDI"
    return None  # অন্য সব চ্যানেল কোনো ফাইলে যাবে না

# =========================
# SAVE FILE
# =========================
def save(path, items, h):
    with open(path, "w", encoding="utf-8") as f:
        f.write(h)
        for c in items:
            f.write(c["extinf"] + "\n")
            f.write(c["url"] + "\n")

# =========================
# COMBINED FILE
# =========================
def build_combined(total, bdxi, ind, bd, sports):
    files = [BDXI_FILE, IND_FILE, BD_FILE, SPORTS_FILE]

    content = header(total, bdxi, ind, bd, sports)

    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                data = file.read().strip()
                if data.startswith("#EXTM3U"):
                    data = data.split("#EXTM3U", 1)[1].strip()
                content += f"\n# ===== {os.path.basename(f)} =====\n"
                content += data + "\n"
        except:
            pass

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

    # CATEGORY SPLIT
    bdxi, ind, bd, sports = [], [], [], []
    for c in unique:
        t = cat(c["name"])
        if t == "BDXI":
            bdxi.append(c)
        elif t == "BD":
            bd.append(c)
        elif t == "IND":
            ind.append(c)
        elif t == "HINDI":
            ind.append(c)
        elif t == "SPORTS":
            sports.append(c)

    # HEADERS
    h = header(len(unique), len(bdxi), len(ind), len(bd), len(sports))

    # SAVE 4 ফাইল
    save(BDXI_FILE, bdxi, h)
    save(IND_FILE, ind, h)
    save(BD_FILE, bd, h)
    save(SPORTS_FILE, sports, h)

    # BUILD COMBINED
    build_combined(len(unique), len(bdxi), len(ind), len(bd), len(sports))

    # REPORT
    print("\n===== FINAL AI HD REPORT =====")
    print("TOTAL   :", len(unique))
    print("BDXI+IND:", len(bdxi) + len(ind))
    print("BD      :", len(bd))
    print("IND     :", len(ind))
    print("SPORTS  :", len(sports))
    print("==============================\n")

# RUN
if __name__ == "__main__":
    asyncio.run(main())
