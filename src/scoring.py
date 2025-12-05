def score_article(article: dict) -> dict:
    sent = article.get("sentiment", "neutral")

    score = {
        "bullish": +1,
        "bearish": -1,
        "neutral": 0
    }.get(sent, 0)

    return {
        **article,
        "sentiment_score": score
    }