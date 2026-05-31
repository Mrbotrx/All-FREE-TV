import os
import requests
from datetime import datetime
import pytz

def fetch_links():
    sources_raw = os.getenv("KBTVPRO")

    if not sources_raw:
        print("Error: KBTVPRO secret is missing!")
        return

    SOURCES_LIST = [url.strip() for url in sources_raw.split(",") if url.strip()]

    tz = pytz.timezone("Asia/Dhaka")
    current_time = datetime.now(tz).strftime("%d-%m-%Y | %I:%M %p")

    header = f"#EXTM3U\n# Updated: {current_time} (BD Time)\n\n"
    combined_content = header
    found_count = 0

    for url in SOURCES_LIST:
        try:
            response = requests.get(
                url,
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code == 200:
                lines = response.text.splitlines()

                for i, line in enumerate(lines):
                    line = line.strip()

                    if line.startswith("#EXTINF"):
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()

                            if next_line.startswith("http") and ".mp4" not in next_line.lower():
                                combined_content += f"{line}\n{next_line}\n"
                                found_count += 1

        except Exception as e:
            print(f"Failed {url}: {e}")

    with open("combined_playlist.m3u", "w", encoding="utf-8") as f:
        f.write(combined_content)

    print(f"Success! {found_count} channels saved.")

if __name__ == "__main__":
    fetch_links()
