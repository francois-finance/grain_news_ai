# src/alerts.py
from __future__ import annotations
from typing import Dict, Any


# Mots-clés de risque (multi-langues), avec un poids de gravité
RISK_KEYWORDS: Dict[str, int] = {
    # météo / récolte
    "drought": 3, "sécheresse": 3, "sequia": 3, "seca": 3,
    "frost": 3, "gel": 3, "helada": 3, "geada": 3,
    "hail": 2, "grêle": 2, "granizo": 2,
    "heatwave": 2, "canicule": 2, "ola de calor": 2, "onda de calor": 2,

    # logistique / ports / shipping
    "port closed": 4, "port closure": 4,
    "puerto cerrado": 4, "porto fechado": 4,
    "strike": 3, "grève": 3, "huelga": 3, "greve": 3,
    "corridor": 2, "grain corridor": 3, "зерновой коридор": 3,
    "blockade": 4, "blocus": 4,

    # politique / flux / sanctions
    "export ban": 4, "export banne": 4,
    "export restriction": 3, "export taxes": 3,
    "quota": 2, "embargo": 4,
    "sanction": 3, "sanctions": 3, "санкции": 3,

    # conflit / attaque
    "attack": 3, "bombardment": 3, "drone": 2,
    "missile": 3, "strike on port": 4,

    # production / récolte
    "crop failure": 4, "harvest loss": 3,
    "poor yields": 3, "yield loss": 3,
    "pérte de rendimiento": 3, "perda de rendimento": 3,
}


def compute_alert(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ajoute :
      - alert_score (int)
      - alert_severity: "none" | "info" | "watch" | "critical"
      - alert_tags: liste de mots-clés déclencheurs (string join)
    en se basant sur :
      - mots-clés de risque dans title / summary / text
      - event_type (weather / logistics / politics / trade)
      - sentiment (bullish/bearish => mouvement de prix)
      - source_group (geopolitics / shipping / macro / grains)
    """

    title = (article.get("title") or "")
    summary = (article.get("summary") or "")
    text = (article.get("text") or "")

    full = f"{title}\n{summary}\n{text}".lower()

    score = 0
    tags = []

    # 1) Mots-clés de risque
    for kw, w in RISK_KEYWORDS.items():
        if kw in full:
            score += w
            tags.append(kw)

    # 2) Type d'événement
    event = (article.get("event_type") or "").lower()
    if event in ("weather", "logistics", "trade", "politics", "stocks", "production"):
        score += 1

    # 3) Sentiment orienté prix
    sentiment = (article.get("sentiment") or "").lower()
    if sentiment in ("bullish", "bearish"):
        score += 1

    # 4) Groupe de source (macro/shipping/geopolitics/grains)
    group = (article.get("source_group") or "").lower()
    if group in ("geopolitics", "shipping"):
        score += 1

    # 5) Normalisation -> severity
    if score >= 7:
        severity = "critical"
    elif score >= 4:
        severity = "watch"
    elif score >= 2:
        severity = "info"
    else:
        severity = "none"

    article["alert_score"] = score
    article["alert_severity"] = severity
    article["alert_tags"] = ",".join(sorted(set(tags)))

    return article