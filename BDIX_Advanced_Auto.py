"""
Advanced BDIX + Manual Bangla IPTV Playlist Generator
Code Name: BDIX_Advanced_Auto.py
Author: ChatGPT
Features:
    - Auto fetch manual Bangla playlist from GitHub
    - Filter only working .m3u8 links
    - Auto assign tvg-logo and group-title
    - Combine with BDIX playlist if needed
    - Output IPTV-ready .m3u8
"""

import urllib.request

# -----------------------------
# 1️⃣ Playlist URLs
# -----------------------------
# BDIX main playlist (optional)
BDIX_URL = "https://raw.githubusercontent.com/IPTVFlixBD/BDIX-IPTV-playlist/main/IPTV-mix.m3u"
# Manual Bangla channels playlist
MANUAL_URL = "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/refs/heads/main/playlist.m3u"

# -----------------------------
# 2️⃣ Output file
# -----------------------------
OUTPUT_FILE = "BDIX_Manual_Bangla_Advanced.m3u8"

# -----------------------------
# 3️⃣ Helper function to parse GitHub playlist
# -----------------------------
def parse_github_m3u(url, group="Bangla TV", default_logo=""):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            lines = [line.decode().strip() for line in response if line.decode().strip()]
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")
        return []

    channels = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i]
            link = lines[i+1] if i+1 < len(lines) else ""
            if link.startswith("http") and link.endswith(".m3u8"):
                # Try to extract tvg-logo if exists in original info
                logo = ""
                if 'tvg-logo="' in info:
                    try:
                        logo = info.split('tvg-logo="')[1].split('"')[0]
                    except:
                        logo = default_logo
                else:
                    logo = default_logo
                name = info.split(",")[-1]
                channels.append({
                    "name": name,
                    "url": link,
                    "logo": logo,
                    "group": group
                })
            i += 2
        else:
            i += 1
    return channels

# -----------------------------
# 4️⃣ Download BDIX channels (optional)
# -----------------------------
print("⏳ Downloading BDIX channels...")
bdix_channels = parse_github_m3u(BDIX_URL, group="BDIX Channels")
print(f"📺 Found {len(bdix_channels)} BDIX channels")

# -----------------------------
# 5️⃣ Download Manual Bangla channels
# -----------------------------
print("⏳ Downloading Manual Bangla channels...")
manual_channels = parse_github_m3u(MANUAL_URL, group="Bangla TV")
print(f"📺 Found {len(manual_channels)} manual Bangla channels")

# -----------------------------
# 6️⃣ Combine playlists
# -----------------------------
final = ["#EXTM3U"]

# Optional: Manual channels first
for ch in manual_channels:
    final.append(f'#EXTINF:-1 tvg-id="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
    final.append(ch["url"])

# BDIX channels next
for ch in bdix_channels:
    final.append(f'#EXTINF:-1 tvg-id="{ch["name"]}" tvg-logo="{ch["logo"]}" group-title="{ch["group"]}",{ch["name"]}')
    final.append(ch["url"])

# -----------------------------
# 7️⃣ Write output file
# -----------------------------
try:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(final))
    print(f"✅ Advanced playlist saved as {OUTPUT_FILE}")
except Exception as e:
    print(f"❌ Error writing file: {e}")

# -----------------------------
# 8️⃣ Summary
# -----------------------------
print(f"📺 Total manual channels: {len(manual_channels)}")
print(f"📺 Total BDIX channels: {len(bdix_channels)}")
print(f"📺 Total channels in final playlist: {len(final)//2}")
