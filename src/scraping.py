import requests
import feedparser
from datetime import datetime
import yaml

with open("configs/sources.yaml", encoding="utf-8") as f:
  cfg = yaml.safe_load(f)

all_sources = []
for group_name, group_sources in cfg["sources"].items():
    for s in group_sources:
        s["group"] = group_name  # grains / macro / fx / energy / shipping / geopolitics
        all_sources.append(s)
        
def fetch_html(url: str) -> dict | None:
    try:
        # timeout réduit à 8 secondes
        r = requests.get(url, timeout=8)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[WARN] Failed to fetch {url} -> {e}")
        return None

    return {
        "url": url,
        "fetched_at": datetime.utcnow().isoformat(),
        "content": r.text,
        "type": "html"
    }

def fetch_rss(url: str) -> list:
    feed = feedparser.parse(url)
    entries = []
    for item in feed.entries:
        entries.append({
            "url": item.link,
            "title": item.title,
            "summary": item.get("summary", ""),
            "published": item.get("published", None),
            "type": "rss",
        })
    return entries

def fetch_source(source_cfg: dict):
    if source_cfg["type"] == "html":
        item = fetch_html(source_cfg["url"])
        return [item] if item is not None else []
    elif source_cfg["type"] == "rss":
        return fetch_rss(source_cfg["url"])
    else:
        raise ValueError(f"Unknown source type: {source_cfg['type']}")