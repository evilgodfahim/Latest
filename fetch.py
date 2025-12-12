import feedparser
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from fuzzywuzzy import fuzz

FEEDS = [
    "http://www.thedailystar.net/latest/rss/rss.xml",
    "https://tbsnews.net/top-news/rss.xml",
    "https://www.dhakatribune.com/feed/",
]

OUTFILE = "result.xml"
MAX_ITEMS = 500
BLOCK = ["/sport/", "/sports/", "/entertainment/"]

# -----------------------------
# Load or initialize XML
# -----------------------------
def load_existing():
    if not os.path.exists(OUTFILE):
        root = ET.Element("rss")
        chan = ET.SubElement(root, "channel")
        ET.ElementTree(root).write(OUTFILE, encoding="utf-8", xml_declaration=True)
    tree = ET.parse(OUTFILE)
    return tree, tree.getroot().find("channel")

# -----------------------------
# Check if titles are similar
# -----------------------------
def title_similar(a, b, threshold=85):
    """
    Uses fuzzy string matching (Levenshtein distance) to detect near-identical titles.
    Returns True if similarity score exceeds threshold.
    """
    return fuzz.ratio(a.lower().strip(), b.lower().strip()) >= threshold

# -----------------------------
# Check if item exists
# -----------------------------
def exists(channel, title):
    for item in channel.findall("item"):
        t = item.findtext("title", "")
        if title_similar(title, t):
            return True
    return False

# -----------------------------
# Block unwanted links
# -----------------------------
def blocked(link):
    link = link.lower()
    return any(x in link for x in BLOCK)

# -----------------------------
# Add new item at top
# -----------------------------
def add_item(channel, entry):
    item = ET.Element("item")
    ET.SubElement(item, "title").text = entry.get("title", "")
    ET.SubElement(item, "link").text = entry.get("link", "")
    ET.SubElement(item, "pubDate").text = entry.get("published", datetime.utcnow().isoformat())

    # Insert at top
    children = list(channel)
    for child in children:
        channel.remove(child)
    channel.insert(0, item)
    for child in children:
        channel.append(child)

    # Enforce max items
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        for old in items[MAX_ITEMS:]:
            channel.remove(old)

# -----------------------------
# Fetch feeds once
# -----------------------------
def fetch_once():
    tree, channel = load_existing()
    for url in FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = e.get("title", "")
            link = e.get("link", "")
            if not title or not link:
                continue
            if blocked(link):
                continue
            if exists(channel, title):
                continue
            add_item(channel, e)
    tree.write(OUTFILE, encoding="utf-8", xml_declaration=True)

# -----------------------------
# Main loop (every 5 mins)
# -----------------------------
if __name__ == "__main__":
    while True:
        fetch_once()
        time.sleep(300)
