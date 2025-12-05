# src/price_impact.py

from collections import defaultdict

# ---------- Helpers basiques ----------

def _safe_get(row, key, default=""):
    v = row.get(key)
    return v if v is not None else default

def _sentiment_score(sentiment: str) -> int:
    s = (sentiment or "").lower()
    if s == "bullish":
        return 1
    if s == "bearish":
        return -1
    return 0  # neutral ou inconnu

# ---------- Source quality ----------

def _source_quality(row: dict) -> float:
    """
    Score entre 0.4 et 1.0 selon la "qualité" supposée de la source,
    basé sur l'URL (heuristique simple).
    """
    url = (_safe_get(row, "url", "") or "").lower()

    if any(x in url for x in [
        "usda.gov", "fao.org", "igc.int", "ers.usda",
        "ec.europa.eu", "conab.gov.br", "noaa.gov", "ecmwf.int",
        "droughtmonitor.unl.edu", "climate.gov"
    ]):
        return 1.0  # top tier institutionnel

    if any(x in url for x in [
        ".gov", ".gouv", ".gov.br", "agmanager.info",
        "kswheat.com", "kansasagconnection", "agroinformacion",
        "bolsadecereales", "news.agrofy.com.ar"
    ]):
        return 0.7  # bon niveau régional / pro

    if url:
        return 0.5  # source générique
    return 0.4      # pas d'URL -> on met un min

# ---------- Event type → impact de base ----------

_EVENT_BASE_IMPACT = {
    "weather":   {"ct": 0.8, "mt": 1.5},
    "stocks":    {"ct": 0.5, "mt": 1.0},
    "production":{"ct": 0.6, "mt": 1.2},
    "trade":     {"ct": 0.3, "mt": 0.6},
    "politics":  {"ct": 0.4, "mt": 1.0},
    "logistics": {"ct": 0.2, "mt": 0.5},
    "other":     {"ct": 0.1, "mt": 0.2},
}

def _base_impact_for_event(event_type: str):
    et = (event_type or "other").lower()
    return _EVENT_BASE_IMPACT.get(et, _EVENT_BASE_IMPACT["other"])

# ---------- Confidence score ----------

def _compute_confidence_for_commodity(rows: list[dict], macro_score: dict) -> float:
    """
    Calcule un score de confiance entre 0 et 1 pour une matière donnée.
    Combine :
      - nombre de news
      - cohérence du sentiment
      - qualité des sources
      - sévérité des alertes
      - alignement avec la macro
    """
    if not rows:
        return 0.0

    # 1) Nombre de news
    n = len(rows)
    n_news_score = min(n / 10.0, 1.0)  # 10 news ou plus -> 1.0

    # 2) Cohérence du sentiment
    sentiments = []
    for r in rows:
        s = (_safe_get(r, "sentiment", "neutral") or "neutral").lower()
        if s in ("bullish", "bearish", "neutral"):
            sentiments.append(s)

    distinct = set(sentiments)
    if not sentiments:
        sent_consistency = 0.0
    else:
        if distinct == {"neutral"}:
            sent_consistency = 0.3  # tout neutre -> faible cohérence exploitable
        elif len(distinct) == 1:
            sent_consistency = 1.0
        elif len(distinct) == 2:
            sent_consistency = 0.5
        else:
            sent_consistency = 0.0

    # 3) Qualité des sources
    qualities = [_source_quality(r) for r in rows]
    source_quality = sum(qualities) / len(qualities) if qualities else 0.4
    # normalisé déjà entre 0.4 et 1.0

    # 4) Alerte (WATCH / CRITICAL)
    alert_severities = [(_safe_get(r, "alert_severity", "none") or "none").lower()
                        for r in rows]
    max_alert = 0.0
    for sev in alert_severities:
        if sev == "critical":
            max_alert = max(max_alert, 1.0)
        elif sev == "watch":
            max_alert = max(max_alert, 0.6)

    # 5) Alignement macro
    final_macro = macro_score.get("final_macro_score", 0)
    net_sent = sum(_sentiment_score(_safe_get(r, "sentiment", "neutral")) for r in rows)

    if final_macro == 0 or net_sent == 0:
        macro_align = 0.5  # neutre / pas clair
    elif final_macro * net_sent > 0:
        macro_align = 1.0  # même sens
    else:
        macro_align = 0.0  # macro en sens inverse

    # Pondération (Option C — balanced)
    confidence = (
        0.25 * n_news_score +
        0.25 * sent_consistency +
        0.20 * source_quality +
        0.15 * max_alert +
        0.15 * macro_align
    )

    if confidence < 0:
        confidence = 0.0
    if confidence > 1:
        confidence = 1.0

    return round(confidence, 3)

# ---------- Impact prix principal ----------

def compute_price_impact(grain_rows: list[dict], macro_score: dict) -> dict:
    """
    Calcule l'impact prix par matière (wheat / corn / soy) en pourcentage,
    pour court terme (CT) et moyen terme (MT),
    et un score de confiance.

    Retourne un dict :
    {
      "wheat": {"ct_low": ..., "ct_high": ..., "mt_low": ..., "mt_high": ..., "confidence": ...},
      "corn":  {...},
      "soy":   {...}
    }
    """
    by_commodity = defaultdict(list)
    for r in grain_rows:
        c = (_safe_get(r, "commodity", "other") or "other").lower()
        if c in ["wheat", "corn", "soy"]:
            by_commodity[c].append(r)

    impacts = {}

    for commodity, rows in by_commodity.items():
        if not rows:
            continue

        # 1) Impact direct news (somme sur les articles)
        total_ct = 0.0
        total_mt = 0.0

        for r in rows:
            etype = (_safe_get(r, "event_type", "other") or "other").lower()
            base = _base_impact_for_event(etype)

            sent = _safe_get(r, "sentiment", "neutral")
            sscore = _sentiment_score(sent)

            if sscore == 0:
                factor_sent = 0.3  # neutral -> petit signal
            else:
                factor_sent = float(sscore)  # -1 ou +1

            # longueur de l'analyse pour pondérer
            text = (_safe_get(r, "analysis", "") or "").strip()
            if not text:
                text = (_safe_get(r, "summary", "") or "").strip()
            L = len(text)

            if L >= 350:
                len_factor = 1.1
            elif L < 120:
                len_factor = 0.85
            else:
                len_factor = 1.0

            row_ct = base["ct"] * factor_sent * len_factor
            row_mt = base["mt"] * factor_sent * len_factor

            total_ct += row_ct
            total_mt += row_mt

        # 2) Impact macro (modeste mais non nul)
        # coefficients simples, option C (balanced)
        fx_score = macro_score.get("fx", 0)
        energy_score = macro_score.get("energy", 0)
        weather_score = macro_score.get("weather", 0)
        shipping_score = macro_score.get("shipping", 0)

        # sensibilité FX par matière
        fx_sens = {"wheat": 0.25, "corn": 0.45, "soy": 0.70}
        this_fx_sens = fx_sens.get(commodity, 0.3)

        macro_ct = (
            0.30 * weather_score +   # météo globale
            0.10 * energy_score +    # énergie
            0.10 * shipping_score +  # logistique
            (-this_fx_sens * 0.10) * fx_score  # USD fort = pression baissière
        )

        macro_mt = 1.5 * macro_ct

        total_ct += macro_ct
        total_mt += macro_mt

        # 3) Normalisation & bornes (Option C)
        # si presque zéro -> neutre
        if abs(total_ct) < 0.15:
            ct_low = 0.0
            ct_high = 0.0
        else:
            mean_ct = total_ct
            ct_low = mean_ct * 0.7
            ct_high = mean_ct * 1.3
            # clamp
            if abs(ct_low) < 0.2 and abs(ct_low) > 0:
                ct_low = 0.2 if ct_low > 0 else -0.2
            if abs(ct_high) > 1.2:
                ct_high = 1.2 if ct_high > 0 else -1.2

        if abs(total_mt) < 0.5:
            mt_low = 0.0
            mt_high = 0.0
        else:
            mean_mt = total_mt
            mt_low = mean_mt * 0.7
            mt_high = mean_mt * 1.3
            if abs(mt_low) < 0.8 and abs(mt_low) > 0:
                mt_low = 0.8 if mt_low > 0 else -0.8
            if abs(mt_high) > 2.2:
                mt_high = 2.2 if mt_high > 0 else -2.2

        # 4) Confidence
        conf = _compute_confidence_for_commodity(rows, macro_score)

        impacts[commodity] = {
            "ct_low": round(ct_low, 2),
            "ct_high": round(ct_high, 2),
            "mt_low": round(mt_low, 2),
            "mt_high": round(mt_high, 2),
            "confidence": conf,
        }

    return impacts