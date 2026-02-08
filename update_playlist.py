import requests

RAW_PLAYLIST = "https://raw.githubusercontent.com/Mrbotrx/All-FREE-TV/refs/heads/main/combined_playlist.m3u"
OUTPUT_FILE = "playlist.m3u"

def is_alive(url):
    try:
        r = requests.head(
            url,
            timeout=8,
            allow_redirects=True,
            headers={"User-Agent": "IPTV-Checker"}
        )
        return r.status_code < 500
    except:
        return False

# 1️⃣ Download remote playlist
response = requests.get(RAW_PLAYLIST, timeout=15)
lines = [line.strip() for line in response.text.splitlines() if line.strip()]

final_playlist = ["#EXTM3U"]
i = 0

# 2️⃣ Parse playlist
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        info = lines[i]
        url = lines[i + 1] if i + 1 < len(lines) else ""

        if url.startswith("http") and is_alive(url):
            final_playlist.append(info)
            final_playlist.append(url)

        i += 2
    else:
        i += 1

# 3️⃣ Save clean playlist
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(final_playlist))

print("✅ playlist.m3u তৈরি হয়েছে (dead channel বাদ)")
