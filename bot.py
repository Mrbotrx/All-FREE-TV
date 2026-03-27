import os
import requests

def main():
    # Secret থেকে লিংকগুলো নেওয়া
    sources_env = os.getenv("KBPROTV", "")
    sources = [s.strip() for s in sources_env.split(",") if s.strip()]

    if not sources:
        print("No sources found! Check your KBPROTV secret.")
        return

    combined_content = "#EXTM3U\n"
    for url in sources:
        try:
            print(f"Fetching: {url}")
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                # প্রথম লাইন (#EXTM3U) বাদ দিয়ে বাকিটা নেওয়া
                lines = resp.text.splitlines()
                if lines and lines[0].startswith("#EXTM3U"):
                    combined_content += "\n".join(lines[1:]) + "\n"
                else:
                    combined_content += resp.text + "\n"
        except Exception as e:
            print(f"Error: {e}")

    with open("combined_playlist.m3u", "w", encoding="utf-8") as f:
        f.write(combined_content)
    print("Playlist updated successfully!")

if __name__ == "__main__":
    main()
