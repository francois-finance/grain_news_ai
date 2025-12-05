# src/scoring_macro.py

from typing import List, Dict, Any


def _safe_get(row: Dict[str, Any], key: str, default: str = "") -> str:
    v = row.get(key)
    return v if v is not None else default


def _sentiment_score(sentiment: str) -> int:
    s = (sentiment or "").lower()
    if s == "bullish":
        return 1
    if s == "bearish":
        return -1
    return 0


def classify_macro_theme(row: Dict[str, Any]) -> str:
    """
    Classe un article 'macro' dans un thème :
    weather / fx / energy / shipping / other
    basé sur event_type + url.
    (Version locale à ce module pour éviter l'import circulaire.)
    """
    et = (_safe_get(row, "event_type", "other") or "other").lower()
    url = (_safe_get(row, "url", "") or "").lower()

    # Météo
    if et == "weather" or any(x in url for x in ["noaa", "droughtmonitor", "ecmwf", "climate.gov"]):
        return "weather"

    # FX / devises
    if any(x in url for x in ["currencies/usd", "dollar-index", "usd-brl", "usd-ars"]):
        return "fx"

    # Énergie
    if any(x in url for x in ["brent-oil", "eia.gov", "energy"]):
        return "energy"

    # Shipping / logistique
    if et == "logistics" or any(x in url for x in ["splash247", "blackseagrain", "baltic"]):
        return "shipping"

    return "other"


def compute_macro_score(macro_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Agrège les articles 'macro' pour produire un score macro-grains.

    Retourne un dict :
      {
        "final_macro_score": -5..+5,
        "weather": int,
        "fx": int,
        "energy": int,
        "shipping": int,
        "other": int,
      }
    """
    weather_score = 0
    fx_score = 0
    energy_score = 0
    shipping_score = 0
    other_score = 0

    for r in macro_rows:
        theme = classify_macro_theme(r)
        sent = _sentiment_score(_safe_get(r, "sentiment", "neutral"))

        if theme == "weather":
            weather_score += sent
        elif theme == "fx":
            fx_score += sent
        elif theme == "energy":
            energy_score += sent
        elif theme == "shipping":
            shipping_score += sent
        else:
            other_score += sent

    final = weather_score + fx_score + energy_score + shipping_score + other_score
    final = max(-5, min(5, final))  # clamp entre -5 et +5

    return {
        "final_macro_score": final,
        "weather": weather_score,
        "fx": fx_score,
        "energy": energy_score,
        "shipping": shipping_score,
        "other": other_score,
    }