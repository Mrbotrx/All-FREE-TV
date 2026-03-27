import os
import requests
from datetime import datetime
import pytz

def fetch_links():
    # এখন সরাসরি 'KBTVPRO' থেকে ডাটা নেওয়া হচ্ছে
    sources_raw = os.getenv("KBTVPRO", "")
    if not sources_raw:
        print("Error: No links found in KBTVPRO secret!")
        return

    # লিঙ্ক লিস্ট তৈরি
    SOURCES_LIST = [url.strip() for url in sources_raw.split(",") if url.strip()]
    
    # বিডি টাইম জোন
    tz = pytz.timezone('Asia/Dhaka')
    current_time = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")

    # M3U হেডার
    header = f"#EXTM3U\n# Updated: {current_time} (BD Time)\n# Developer: Mrbot × KB CYBER TEAM\n\n"
    combined_content = header
    found_count = 0

    for url in SOURCES_LIST:
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                lines = response.text.splitlines()
                for i in range(len(lines)):
                    line = lines[i].strip()
                    if line.startswith("#EXTINF"):
                        if i + 1 < len(lines):
                            next_line = lines[i+1].strip()
                            # .mp4 ফিল্টার
                            if next_line.startswith("http") and ".mp4" not in next_line.lower():
                                combined_content += f"{line}\n{next_line}\n"
                                found_count += 1
        except:
            continue

    with open("combined_playlist.m3u", "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"Success! {found_count} channels processed from KBTVPRO.")

if __name__ == "__main__":
    fetch_links()
