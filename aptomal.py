import json
import requests
import xml.etree.ElementTree as ET
import re
import time

# === CONFIG ===
INPUT_JSON = "export.json"
OUTPUT_XML = "convert.xml"
USERNAME = "your_username"  # Replace with your MAL username
SKIPPED_LOG = "skipped_titles.txt"

# === CLEANING FUNCTION ===
def clean_title(title):
    title = re.sub(r"\s*\(.*?\)", "", title)  # Remove (TV), (OVA), etc.
    title = re.sub(r"[^a-zA-Z0-9\s:]", "", title)  # Remove special characters
    return title.strip()

# === STATUS CONVERSION ===
def convert_status(status):
    return {
        "watching": "1",
        "watched": "2",
        "completed": "2",
        "on-hold": "3",
        "dropped": "4",
        "plan to watch": "6",
        "want to watch": "6"
    }.get(status.lower(), "6")

# === AUTO-MATCH FIRST MAL RESULT WITH DELAY + RETRY ===
def auto_match_first_result(original_title, delay=1.5, retries=3):
    cleaned = clean_title(original_title)

    for attempt in range(1, retries + 1):
        try:
            response = requests.get("https://api.jikan.moe/v4/anime", params={"q": cleaned, "limit": 1})
            response.raise_for_status()
            results = response.json().get("data", [])
            if not results:
                print(f"❌ No matches found for: {original_title}")
                return None, None, None

            selected = results[0]
            print(f"✅ Matched: {original_title} → {selected['title']} ({selected['episodes']} eps)")
            time.sleep(delay)  # Respectful pause
            return selected["mal_id"], selected["title"], selected.get("episodes", 0)

        except Exception as e:
            print(f"⚠️ Attempt {attempt} failed for '{original_title}': {e}")
            if attempt < retries:
                time.sleep(delay * attempt)  # Exponential backoff
            else:
                print(f"⏭️ Skipping '{original_title}' after {retries} failed attempts.")
                return None, None, None

# === LOAD JSON ===
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

entries = None
for key in data:
    if isinstance(data[key], list) and all(isinstance(i, dict) for i in data[key]):
        entries = data[key]
        break

if not entries:
    print("❌ Could not find a list of entries.")
    exit()

# === BUILD XML ===
root = ET.Element("myanimelist")
user = ET.SubElement(root, "myinfo")
ET.SubElement(user, "user_name").text = USERNAME
ET.SubElement(user, "user_export_type").text = "1"

converted = 0
skipped_titles = []
total = len(entries)

for index, entry in enumerate(entries, start=1):
    title = entry.get("name")
    if not title:
        continue

    print(f"\n🔄 [{index}/{total}] Processing: {title}")
    mal_id, matched_title, episode_count = auto_match_first_result(title)
    if not mal_id:
        skipped_titles.append(title)
        continue

    raw_rating = entry.get("rating", 0)
    mal_score = int(round(raw_rating * 2)) if raw_rating else 0
    status = convert_status(entry.get("status", "plan to watch"))

    anime = ET.SubElement(root, "anime")
    ET.SubElement(anime, "series_animedb_id").text = str(mal_id)
    ET.SubElement(anime, "my_id").text = "0"
    ET.SubElement(anime, "my_watched_episodes").text = str(episode_count)
    ET.SubElement(anime, "my_start_date").text = "0000-00-00"
    ET.SubElement(anime, "my_finish_date").text = "0000-00-00"
    ET.SubElement(anime, "my_score").text = str(mal_score)
    ET.SubElement(anime, "my_status").text = status
    ET.SubElement(anime, "my_times_watched").text = "0"
    ET.SubElement(anime, "my_rewatch_value").text = "0"
    ET.SubElement(anime, "update_on_import").text = "1"

    converted += 1

# === SAVE XML ===
tree = ET.ElementTree(root)
tree.write(OUTPUT_XML, encoding="utf-8", xml_declaration=True)
print(f"\n📄 Exported {converted} entries to {OUTPUT_XML}")

# === LOG SKIPPED TITLES ===
if skipped_titles:
    with open(SKIPPED_LOG, "w", encoding="utf-8") as f:
        for title in skipped_titles:
            f.write(title + "\n")
    print(f"⚠️ Logged {len(skipped_titles)} skipped titles to {SKIPPED_LOG}")

# === FINAL SUMMARY ===
print(f"\n✅ Finished: {converted} converted, {len(skipped_titles)} skipped, {total} total.")
