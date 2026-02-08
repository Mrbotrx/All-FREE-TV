import urllib.request
import os

# Source playlist (GitHub raw)
SOURCE_URL = "https://raw.githubusercontent.com/IPTVFlixBD/BDIX-IPTV-playlist/main/IPTV-mix.m3u"
OUTPUT_FILE = "BDIX_working_playlist.m3u8"

print("⏳ Downloading playlist from GitHub...")

# Download playlist
with urllib.request.urlopen(SOURCE_URL, timeout=20) as response:
    lines = [line.decode().strip() for line in response if line.decode().strip()]

# Build clean playlist with only .m3u8 URLs
final = ["#EXTM3U"]
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        info = lines[i]
        url = lines[i+1] if i+1 < len(lines) else ""
        # Keep only valid .m3u8 links
        if url.startswith("http") and url.endswith(".m3u8"):
            final.append(info)
            final.append(url)
        i += 2
    else:
        i += 1

# Write to output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("\n".join(final))

print(f"✅ Clean working playlist saved as {OUTPUT_FILE}")
