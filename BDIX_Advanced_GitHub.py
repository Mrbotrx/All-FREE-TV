"""
BDIX + Manual Bangla IPTV Playlist Generator & GitHub Auto Update
Author: ChatGPT
"""

import urllib.request
import requests
import base64
import json

# -----------------------------
# 1️⃣ Playlist URLs
# -----------------------------
BDIX_URL = "https://raw.githubusercontent.com/IPTVFlixBD/BDIX-IPTV-playlist/main/IPTV-mix.m3u"
MANUAL_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/refs/heads/main/playlist.m3u"

# -----------------------------
# 2️⃣ Local Output
# -----------------------------
LOCAL_OUTPUT = "BDIX_Manual_Bangla_Advanced.m3u8"

# -----------------------------
# 3️⃣ GitHub Configuration
# -----------------------------
GITHUB_TOKEN = "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"
REPO = "Mrbotrx/All-FREE-TV"
FILE_PATH = "combined_playlist.m3u"
BRANCH = "main"

# -----------------------------
# 4️⃣ Helper Function
# -----------------------------
def parse_m3u(url, group):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            lines = [l.decode().strip() for l in r if l.strip()]
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")
        return []

    channels = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            name = lines[i].split(",")[-1]
            link = lines[i+1] if i+1 < len(lines) else ""
            if link.startswith("http") and link.endswith(".m3u8"):
                logo = ""
                if 'tvg-logo="' in lines[i]:
                    try:
                        logo = lines[i].split('tvg-logo="')[1].split('"')[0]
                    except:
                        logo = ""
                channels.append({
                    "name": name,
                    "url": link,
                    "group": group,
                    "logo": logo
                })
            i += 2
        else:
            i += 1
    return channels

# -----------------------------
# 5️⃣ Download Playlists
# -----------------------------
print("⏳ Downloading BDIX channels...")
bdix_channels = parse_m3u(BDIX_URL, "BDIX Channels")
print(f"📺 Found {len(bdix_channels)} BDIX channels")

print("⏳ Downloading Manual Bangla channels...")
manual_channels = parse_m3u(MANUAL_URL, "Bangla TV")
print(f"📺 Found {len(manual_channels)} manual Bangla channels")

# -----------------------------
# 6️⃣ Combine Playlists
# -----------------------------
final = ["#EXTM3U"]

# Manual first
for ch in manual_channels:
    final.append(f'#EXTINF:-1 tvg-id="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
    final.append(ch["url"])

# BDIX next
for ch in bdix_channels:
    final.append(f'#EXTINF:-1 tvg-id="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
    final.append(ch["url"])

# -----------------------------
# 7️⃣ Save locally
# -----------------------------
with open(LOCAL_OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(final))
print(f"✅ Playlist saved locally: {LOCAL_OUTPUT}")

# -----------------------------
# 8️⃣ Push to GitHub
# -----------------------------
print("⏳ Updating GitHub combined_playlist.m3u...")

# Get current file sha
url_get = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}?ref={BRANCH}"
headers = {"Authorization": f"token {GITHUB_TOKEN}"}

r = requests.get(url_get, headers=headers)
sha = r.json().get("sha") if r.status_code == 200 else None

payload = {
    "message": "Auto update IPTV playlist",
    "content": base64.b64encode("\n".join(final).encode()).decode(),
    "branch": BRANCH
}

if sha:
    payload["sha"] = sha

res = requests.put(f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}", headers=headers, data=json.dumps(payload))

if res.status_code in [200, 201]:
    print("✅ combined_playlist.m3u updated successfully on GitHub!")
else:
    print(f"❌ GitHub update failed: {res.status_code} {res.text}")

# -----------------------------
# 9️⃣ Summary
# -----------------------------
print(f"📺 Total manual channels: {len(manual_channels)}")
print(f"📺 Total BDIX channels: {len(bdix_channels)}")
print(f"📺 Total channels in final playlist: {len(final)//2}")
