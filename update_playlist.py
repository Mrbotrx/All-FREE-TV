import urllib.request

SOURCE_URL = "https://raw.githubusercontent.com/Mrbotrx/All-FREE-TV/refs/heads/main/combined_playlist.m3u"
OUTPUT = "playlist.m3u"

print("Downloading playlist...")

with urllib.request.urlopen(SOURCE_URL, timeout=20) as response:
    lines = [line.decode().strip() for line in response if line.decode().strip()]

final = ["#EXTM3U"]
i = 0

while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        info = lines[i]
        url = lines[i+1] if i + 1 < len(lines) else ""
        if url.startswith("http"):
            final.append(info)
            final.append(url)
        i += 2
    else:
        i += 1

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\n".join(final))

print("✅ playlist.m3u তৈরি হয়েছে (requests ছাড়াই)")
