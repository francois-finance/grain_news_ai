from bs4 import BeautifulSoup

def parse_article(raw: dict) -> dict:
    """
    raw = {"url":..., "content":..., "type":...}
    """
    if raw["type"] == "rss":
        # On utilisera juste ce que donne le RSS
        return {
            "url": raw["url"],
            "title": raw.get("title", ""),
            "text": raw.get("summary", ""),
            "published": raw.get("published", None)
        }

    # HTML → extraction principale
    soup = BeautifulSoup(raw["content"], "html.parser")
    text = " ".join([p.get_text(" ", strip=True) for p in soup.find_all("p")])

    return {
        "url": raw["url"],
        "title": soup.title.string if soup.title else "",
        "text": text,
        "published": raw.get("fetched_at", None)
    }