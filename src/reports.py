import csv
import os
import json
from collections import defaultdict

from src.scoring_macro import compute_macro_score
from src.price_impact import compute_price_impact
from src.plots import (
    plot_articles_by_commodity,
    plot_sentiment_by_commodity,
    plot_macro_score,
)

# Horizon utilisé dans le backtest (en jours)
FORWARD_DAYS = 5

# ---------- Helpers génériques ----------


def _safe_get(row, key, default=""):
    v = row.get(key)
    return v if v is not None else default


def _sentiment_score(sentiment: str) -> int:
    s = (sentiment or "").lower()
    if s == "bullish":
        return 1
    if s == "bearish":
        return -1
    return 0


def _bias_label(score: int) -> str:
    if score > 0:
        return f"Haussier (score {score})"
    if score < 0:
        return f"Baissier (score {score})"
    return f"Neutre (score {score})"


# ---------- Macro helpers ----------


def classify_macro_theme(row: dict) -> str:
    """
    Classe un article 'macro' dans un thème :
    weather / fx / energy / shipping / other
    basé sur event_type + url.
    """
    et = (_safe_get(row, "event_type", "other") or "other").lower()
    url = (_safe_get(row, "url", "") or "").lower()

    # Météo
    if et == "weather" or any(
        x in url for x in ["noaa", "droughtmonitor", "ecmwf", "climate.gov"]
    ):
        return "weather"

    # FX / devises
    if any(
        x in url
        for x in ["currencies/usd", "dollar-index", "usd-brl", "usd-ars", "usdars"]
    ):
        return "fx"

    # Énergie
    if any(x in url for x in ["brent-oil", "brent", "eia.gov", "energy"]):
        return "energy"

    # Shipping / logistique
    if et == "logistics" or any(
        x in url for x in ["splash247", "blackseagrain", "baltic"]
    ):
        return "shipping"

    return "other"


def _macro_score(rows):
    score = 0
    for r in rows:
        score += _sentiment_score(_safe_get(r, "sentiment", "neutral"))
    return score


# ---------- Rapport principal ----------


def generate_daily_report(csv_path: str, out_dir: str = "reports") -> str:
    """
    Génère un rapport Markdown de type "Daily Grain Intelligence" :

    - Indicateur Macro-Grains + graphiques
    - Section ALERTES DU JOUR (alert_score / alert_severity)
    - Sections par matière (wheat / corn / soy) :
        Biais LLM, Impact prix quantifié (backtest + macro),
        Résumé analytique, Impact prix narratif, Risques, Perspectives, Sources
    - Section Macro marché :
        Weather / FX / Energy / Shipping, avec résumés + scores
    - Section Backtest globale (si data dispo)
    """
    if not os.path.exists(csv_path):
        print(f"[WARN] CSV not found: {csv_path}")
        return ""

    os.makedirs(out_dir, exist_ok=True)

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("[INFO] No rows to report.")
        return ""

    base = os.path.basename(csv_path)
    date_part = base.replace("signals_", "").replace(".csv", "")

    # ---------- Gestion des alertes (early warning) ----------

    for r in rows:
        try:
            r["alert_score"] = int(r.get("alert_score", 0))
        except Exception:
            r["alert_score"] = 0

    alert_rows = [
        r
        for r in rows
        if (r.get("alert_severity") or "").lower() in ("watch", "critical")
    ]
    alert_rows.sort(key=lambda x: x.get("alert_score", 0), reverse=True)

    # ---------- Séparation grains / macro ----------

    grain_rows = []
    macro_rows = []
    for r in rows:
        c = (_safe_get(r, "commodity", "other") or "other").lower()
        if c in ["wheat", "corn", "soy"]:
            grain_rows.append(r)
        else:
            macro_rows.append(r)

    # Groupement par matière
    by_commodity = defaultdict(list)
    for r in grain_rows:
        c = (_safe_get(r, "commodity", "other") or "other").lower()
        by_commodity[c].append(r)

    # Groupement macro par thème
    macro_by_theme = defaultdict(list)
    for r in macro_rows:
        theme = classify_macro_theme(r)
        macro_by_theme[theme].append(r)

    # ---------- Macro score global & impact prix ----------

    macro_score_dict = compute_macro_score(macro_rows)
    print("[INFO] Macro score :", macro_score_dict)

    price_impact_dict = compute_price_impact(grain_rows, macro_score_dict)

    # ---------- Construction du Markdown ----------
    lines = []
    lines.append(f"# Daily Grain Intelligence Report — {date_part}\n")

    # ================
    # Indicateur macro
    # ================

    lines.append("## 🧭 Indicateur Macro-Grains\n")
    final_macro = macro_score_dict.get("final_macro_score", 0)
    lines.append(f"- **Score global** : {final_macro} / 5")
    lines.append(f"- **Météo** : {macro_score_dict.get('weather', 0)}")
    lines.append(f"- **Devises (FX)** : {macro_score_dict.get('fx', 0)}")
    lines.append(f"- **Énergie** : {macro_score_dict.get('energy', 0)}")
    lines.append(
        f"- **Logistique / Shipping** : {macro_score_dict.get('shipping', 0)}"
    )
    lines.append(f"- **Autres facteurs** : {macro_score_dict.get('other', 0)}\n")

    # ================
    # Graphiques
    # ================

    lines.append("## 📊 Graphiques du jour\n")

    lines.append("### Nombre d'articles par commodity")
    lines.append(
        f"![Articles par commodity](../figures/articles_by_commodity_{date_part}.png)\n"
    )

    lines.append("### Sentiment moyen par commodity")
    lines.append(
        f"![Sentiment par commodity](../figures/sentiment_by_commodity_{date_part}.png)\n"
    )

    lines.append("### Score macro-grains par thème")
    lines.append(
        f"![Score macro](../figures/macro_scores_{date_part}.png)\n"
    )

    # ============================
    #   SECTION ALERTES DU JOUR
    # ============================

    lines.append("## ALERTES DU JOUR 🔔\n")

    if not alert_rows:
        lines.append("_Aucune alerte significative aujourd'hui._\n")
    else:
        for r in alert_rows[:10]:
            title = _safe_get(r, "title", "Sans titre").strip() or "Sans titre"
            url = _safe_get(r, "url", "").strip()
            commodity = _safe_get(r, "commodity", "other")
            event_type = _safe_get(r, "event_type", "other")
            severity = (r.get("alert_severity") or "none").lower()
            score = r.get("alert_score", 0)
            tags = (r.get("alert_tags") or "").strip()

            lines.append(f"### [{severity.upper()}] {title}")
            if url:
                lines.append(f"[Lien]({url})")
            lines.append(f"- Commodity : **{commodity}**")
            lines.append(f"- Type : **{event_type}**")
            lines.append(f"- Score alerte : **{score}**")
            if tags:
                lines.append(f"- Mots-clés risque : `{tags}`")

            summary = (_safe_get(r, "summary", "") or "").strip()
            if summary:
                lines.append(f"\n> {summary}\n")
            lines.append("")

    # ============================
    #   SECTIONS PAR MATIÈRE
    # ============================

    for commodity in ["wheat", "corn", "soy"]:
        items = by_commodity.get(commodity, [])
        if not items:
            continue

        lines.append(f"## {commodity.capitalize()}\n")

        # Biais global LLM
        total_score = sum(
            _sentiment_score(_safe_get(r, "sentiment", "neutral")) for r in items
        )
        bias = _bias_label(total_score)
        lines.append(f"**Biais de marché (LLM) :** {bias}\n")

        # Impact prix quantifié (à partir du backtest + macro)
        imp = price_impact_dict.get(commodity)
        if imp:
            ct_low = imp["ct_low"]
            ct_high = imp["ct_high"]
            mt_low = imp["mt_low"]
            mt_high = imp["mt_high"]
            conf = imp["confidence"]

            lines.append("### Impact quantifié sur les prix\n")
            if (
                ct_low == 0
                and ct_high == 0
                and mt_low == 0
                and mt_high == 0
            ):
                lines.append(
                    "- Signal global : **neutre** "
                    "(pas d'impact prix significatif détecté)"
                )
            else:
                lines.append(
                    f"- Court terme (1–3 jours) : **{ct_low:+.2f}% → {ct_high:+.2f}%**"
                )
                lines.append(
                    f"- Moyen terme (7–20 jours) : **{mt_low:+.2f}% → {mt_high:+.2f}%**"
                )
            lines.append(f"- Confiance du signal : **{conf:.2f}**\n")

        # Résumé analytique (LLM)
        analyses = [
            _safe_get(r, "analysis", "").strip()
            for r in items
            if _safe_get(r, "analysis", "").strip()
        ]
        if analyses:
            lines.append("**Résumé analytique :**")
            for a in analyses[:5]:
                lines.append(f"- {a}")
            lines.append("")
        else:
            lines.append("**Résumé analytique :**")
            lines.append("- Aucune analyse disponible.\n")

        # Impact sur les prix (narratif LLM)
        impacts = [
            _safe_get(r, "impact", "").strip()
            for r in items
            if _safe_get(r, "impact", "").strip()
        ]
        if impacts:
            lines.append("**Impact sur les prix (narratif LLM) :**")
            for imp_text in impacts[:3]:
                lines.append(f"- {imp_text}")
            lines.append("")

        # Risques
        risks = []
        for r in items:
            r_list = r.get("risks")
            if isinstance(r_list, list):
                risks.extend(
                    [str(x).strip() for x in r_list if str(x).strip()]
                )
        if risks:
            lines.append("**Risques clés :**")
            seen = set()
            clean_risks = []
            for ri in risks:
                if ri not in seen:
                    seen.add(ri)
                    clean_risks.append(ri)
            for ri in clean_risks[:5]:
                lines.append(f"- {ri}")
            lines.append("")

        # Perspectives
        outlooks = [
            _safe_get(r, "outlook", "").strip()
            for r in items
            if _safe_get(r, "outlook", "").strip()
        ]
        if outlooks:
            lines.append("**Perspectives court terme :**")
            for o in outlooks[:3]:
                lines.append(f"- {o}")
            lines.append("")

        # Sources
        lines.append("**Sources :**")
        for r in items[:8]:
            title = _safe_get(r, "title", "Sans titre").strip() or "Sans titre"
            url = _safe_get(r, "url", "").strip()
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
        lines.append("")

    # ============================
    #   SECTION MACRO MARCHÉ
    # ============================

    if macro_rows:
        lines.append("## Macro marché (tous grains)\n")

        label = {
            "weather": "Météo",
            "fx": "Devises (FX)",
            "energy": "Énergie",
            "shipping": "Logistique / Shipping",
            "other": "Autres facteurs",
        }

        lines.append("**Scores macro par thème :**")
        for theme in ["weather", "fx", "energy", "shipping", "other"]:
            rows_theme = macro_by_theme.get(theme, [])
            if not rows_theme:
                continue
            sc = _macro_score(rows_theme)
            n = len(rows_theme)
            lines.append(
                f"- {label[theme]} : score **{sc}** (sur {n} news)"
            )
        lines.append("")

        # Détail par thème
        for theme in ["weather", "fx", "energy", "shipping", "other"]:
            rows_theme = macro_by_theme.get(theme, [])
            if not rows_theme:
                continue

            lines.append(f"### {label[theme]}\n")

            # Résumé analytique
            analyses = [
                _safe_get(r, "analysis", "").strip()
                for r in rows_theme
                if _safe_get(r, "analysis", "").strip()
            ]
            if analyses:
                lines.append("**Résumé analytique :**")
                for a in analyses[:3]:
                    lines.append(f"- {a}")
                lines.append("")

            # Impact prix (narratif)
            impacts = [
                _safe_get(r, "impact", "").strip()
                for r in rows_theme
                if _safe_get(r, "impact", "").strip()
            ]
            if impacts:
                lines.append("**Impact sur les prix :**")
                for imp in impacts[:3]:
                    lines.append(f"- {imp}")
                lines.append("")

            # Perspectives
            outlooks = [
                _safe_get(r, "outlook", "").strip()
                for r in rows_theme
                if _safe_get(r, "outlook", "").strip()
            ]
            if outlooks:
                lines.append("**Perspectives court terme :**")
                for o in outlooks[:3]:
                    lines.append(f"- {o}")
                lines.append("")

            # Sources macro
            lines.append("**Sources :**")
            for r in rows_theme[:8]:
                title = _safe_get(r, "title", "Sans titre").strip() or "Sans titre"
                url = _safe_get(r, "url", "").strip()
                if url:
                    lines.append(f"- [{title}]({url})")
                else:
                    lines.append(f"- {title}")
            lines.append("")

    # ============================
    #   SECTION BACKTEST (si dispo)
    # ============================

    bt_path = "data/backtest_summary.json"
    if os.path.exists(bt_path):
        try:
            with open(bt_path, "r", encoding="utf-8") as f:
                bt = json.load(f)
        except Exception:
            bt = None

        if bt:
            lines.append("## 📈 Backtest – Performance historique des signaux\n")

            g = bt.get("global", {}) or {}
            n_sig = g.get("n_signals", 0)
            if n_sig:
                lines.append(
                    f"- Nombre total de signaux backtestés : **{n_sig}**"
                )
                if g.get("mean_fwd_return") is not None:
                    lines.append(
                        f"- Retour moyen à {FORWARD_DAYS} jours : "
                        f"**{g['mean_fwd_return']*100:.2f} %**"
                    )

                bull_n = g.get("bullish_n", 0)
                bear_n = g.get("bearish_n", 0)
                bull_m = g.get("bullish_mean")
                bear_m = g.get("bearish_mean")

                if bull_n and bull_m is not None:
                    lines.append(
                        f"- Signaux **bullish** : {bull_n} | retour moyen : **{bull_m*100:.2f} %**"
                    )
                if bear_n and bear_m is not None:
                    lines.append(
                        f"- Signaux **bearish** : {bear_n} | retour moyen : **{bear_m*100:.2f} %**"
                    )

                lines.append("")

            # Détail par commodity
            byc = bt.get("by_commodity", {}) or {}
            if byc:
                lines.append("### Détail par commodity\n")
                for comm in ["wheat", "corn", "soy"]:
                    d = byc.get(comm)
                    if not d:
                        continue

                    lines.append(f"**{comm.capitalize()}** :")
                    lines.append(f"- N signaux : {d.get('n_signals', 0)}")

                    if d.get("mean_fwd_return") is not None:
                        lines.append(
                            f"- Retour moyen : **{d['mean_fwd_return']*100:.2f} %**"
                        )

                    bn = d.get("bullish_n", 0)
                    bm = d.get("bullish_mean")
                    if bn and bm is not None:
                        lines.append(
                            f"- Bullish ({bn}) : **{bm*100:.2f} %**"
                        )

                    bn2 = d.get("bearish_n", 0)
                    bm2 = d.get("bearish_mean")
                    if bn2 and bm2 is not None:
                        lines.append(
                            f"- Bearish ({bn2}) : **{bm2*100:.2f} %**"
                        )
                    lines.append("")

    # ---------- Écriture fichier ----------
    content = "\n".join(lines)
    out_path = os.path.join(out_dir, f"daily_{date_part}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] Nouveau rapport écrit → {out_path}")

    # ---------- Graphiques ----------
    os.makedirs("figures", exist_ok=True)
    plot_articles_by_commodity(csv_path, date_part)
    plot_sentiment_by_commodity(csv_path, date_part)
    plot_macro_score(csv_path, date_part)

    return out_path