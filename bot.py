

import os
import asyncio
import aiohttp
from datetime import datetime
import pytz

SECRET_NAMES = ["KBTVPRO1", "KBTVPRO2", "KBTVPRO3"]
MAX_CHANNELS = 350

BLOCK = {
"promo", "promote", "advert", "ads",
".mp4", ".mkv", ".avi", ".mov",
"telegram", "subscribe", "click"
}

def get_sources():
urls = []
for key in SECRET_NAMES:
raw = os.getenv(key, "")
urls.extend([x.strip() for x in raw.split(",") if x.strip()])
return urls

def header(total, bdxi, ind, bd, sports):
now = datetime.now(
pytz.timezone("Asia/Dhaka")
).strftime("%d-%m-%Y | %I:%M %p")

return f"""#EXTM3U

Updated: {now}

TOTAL: {total}

BDXI: {bdxi}

IND: {ind}

BD: {bd}

SPORTS: {sports}

"""

async def fetch(session, url):
try:
async with session.get(url, timeout=10) as r:
if r.status == 200:
return await r.text()
except Exception:
return None

def score_channel(name, url):
score = 0
text = f"{name} {url}".lower()

if any(x in text for x in BLOCK):
    return 0

if any(x in text for x in ["hd", "fhd", "uhd", "4k", "1080", "720"]):
    score += 50

if any(x in text for x in ["sports", "news", "live"]):
    score += 20

if "m3u8" in url.lower():
    score += 20

return score

def category(name):
n = name.lower()

if "sport" in n:
    return "SPORTS"
if "zee" in n or "sony" in n:
    return "BDXI"
if "atn" in n or "ntv" in n or "bangla" in n:
    return "BD"

return "IND"

async def main():
sources = get_sources()

connector = aiohttp.TCPConnector(limit=50)

async with aiohttp.ClientSession(
    connector=connector
) as session:

    results = await asyncio.gather(
        *[fetch(session, u) for u in sources]
    )

channels = []

for playlist in results:
    if not playlist:
        continue

    extinf = None

    for line in playlist.splitlines():
        line = line.strip()

        if line.startswith("#EXTINF"):
            extinf = line
            continue

        if extinf and line.startswith("http"):
            name = extinf.split(",")[-1].strip()

            score = score_channel(name, line)

            if score > 0:
                channels.append({
                    "name": name,
                    "url": line,
                    "extinf": extinf,
                    "score": score
                })

            extinf = None

# remove duplicates
seen = set()
unique = []

for ch in channels:
    key = (ch["name"], ch["url"])
    if key not in seen:
        seen.add(key)
        unique.append(ch)

# top best channels
unique.sort(
    key=lambda x: x["score"],
    reverse=True
)

unique = unique[:MAX_CHANNELS]

# split categories
bdxi = [c for c in unique if category(c["name"]) == "BDXI"]
ind = [c for c in unique if category(c["name"]) == "IND"]
bd = [c for c in unique if category(c["name"]) == "BD"]
sports = [c for c in unique if category(c["name"]) == "SPORTS"]

print("TOTAL:", len(unique))
print("BDXI:", len(bdxi))
print("IND:", len(ind))
print("BD:", len(bd))
print("SPORTS:", len(sports))

if name == "main":
asyncio.run(main()
