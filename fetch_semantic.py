import feedparser
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# -----------------------------
# CONFIG
# -----------------------------
FEEDS = [
    "http://www.thedailystar.net/latest/rss/rss.xml",
    "https://tbsnews.net/top-news/rss.xml",
    "https://www.dhakatribune.com/feed/",
]

OUTFILE = "result.xml"
MAX_ITEMS = 1000
MAX_FEED_ITEMS = 50           # max items checked per feed
MAX_EXISTING_CHECK = 50       # compare only with last 50 items
SIM_THRESHOLD = 0.88
BLOCK = ["/sport/", "/sports/", "/entertainment/"]

SLEEP_SECONDS = 300           # 5 minutes


# -----------------------------
# Initialize XML
# -----------------------------
def load_existing():
    if not os.path.exists(OUTFILE):
        root = ET.Element("rss")
        chan = ET.SubElement(root, "channel")
        ET.ElementTree(root).write(OUTFILE, encoding="utf-8", xml_declaration=True)

    tree = ET.parse(OUTFILE)
    return tree, tree.getroot().find("channel")


# -----------------------------
# Model
# -----------------------------
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_title(t):
    return model.encode(t, convert_to_numpy=True)


def semantic_match(embed_a, embed_b):
    return cosine_similarity([embed_a], [embed_b])[0][0] >= SIM_THRESHOLD


# -----------------------------
# Block unwanted urls
# -----------------------------
def blocked(url):
    url = url.lower()
    return any(b in url for b in BLOCK)


# -----------------------------
# Add at top
# -----------------------------
def add_item(channel, entry):
    item = ET.Element("item")
    ET.SubElement(item, "title").text = entry.get("title", "")
    ET.SubElement(item, "link").text = entry.get("link", "")
    ET.SubElement(item, "pubDate").text = entry.get("published", datetime.utcnow().isoformat())

    # Move current children down, insert new at top
    children = list(channel)
    for child in children:
        channel.remove(child)
    channel.insert(0, item)
    for child in children:
        channel.append(child)

    # enforce max size
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        for old in items[MAX_ITEMS:]:
            channel.remove(old)


# -----------------------------
# Fetch Once
# -----------------------------
def fetch_once():
    tree, channel = load_existing()

    # Get newest 50 existing titles
    existing_items = channel.findall("item")[:MAX_EXISTING_CHECK]
    existing_titles = [i.findtext("title", "") for i in existing_items]
    existing_embeds = [embed_title(t) for t in existing_titles]

    for url in FEEDS:
        feed = feedparser.parse(url)

        count = 0
        for entry in feed.entries[:MAX_FEED_ITEMS]:  # max check 50 per feed
            title = entry.get("title", "")
            link = entry.get("link", "")

            if not title or not link:
                continue
            if blocked(link):
                continue

            # embed once per new title
            new_emb = embed_title(title)

            # compare only against last 50 existing
            duplicate = False
            for old_emb in existing_embeds:
                if semantic_match(new_emb, old_emb):
                    duplicate = True
                    break

            if duplicate:
                continue

            # New article
            add_item(channel, entry)
            existing_embeds.insert(0, new_emb)   # update top
            existing_embeds = existing_embeds[:MAX_EXISTING_CHECK]

            count += 1

            if count >= MAX_FEED_ITEMS:
                break

    tree.write(OUTFILE, encoding="utf-8", xml_declaration=True)


# -----------------------------
# Loop
# -----------------------------
if __name__ == "__main__":
    while True:
        fetch_once()
        time.sleep(SLEEP_SECONDS)