import yaml
from datetime import datetime, timedelta, timezone

from src.scraping import fetch_source
from src.parsing import parse_article
from src.llm_summarizer import summarize_and_extract
from src.scoring import score_article
from src.storage import save_signals
from src.reports import generate_daily_report
from src.alerts import compute_alert
from src.scoring_macro import compute_macro_score  # <- macro score
from src.plots import generate_daily_plots

MAX_AGE_DAYS = 180  # 6 mois ~ 180 jours


def is_recent(article: dict) -> bool:
    ts = article.get("published") or article.get("fetched_at")
    if not ts:
        return True  # pas de date -> on garde

    try:
        # On tronque à la partie 'YYYY-MM-DDTHH:MM:SS'
        dt = datetime.fromisoformat(ts[:19])
        # On le rend "aware" en UTC s'il est naïf
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return True  # en cas de doute, on garde

    limit = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    return dt >= limit


def load_all_sources(yaml_path: str = "configs/sources.yaml") -> list[dict]:
    """
    Aplati la structure hiérarchique :
    sources:
      grains: [...]
      macro: [...]
      fx: [...]
      ...
    en une liste de dicts avec un champ "group".
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    grouped = cfg["sources"]  # dict: grains / macro / fx / energy / shipping / geopolitics
    all_sources: list[dict] = []

    for group_name, group_list in grouped.items():
        if not group_list:
            continue
        for s in group_list:
            item = dict(s)
            item["group"] = group_name  # ex: "grains", "macro", ...
            all_sources.append(item)

    return all_sources


def main():
    print("[INFO] Starting daily grain pipeline...")

    # 1) Charger toutes les sources (aplaties)
    # Garder seulement les sources "grains" pour l'instant (performance)
    sources = [s for s in load_all_sources() if s.get("group") == "grains"]

    # Limiter le nombre de sources pour des runs rapides (tu peux augmenter plus tard)
    sources = sources[:5]

    # 2) Scraper toutes les sources
    all_raw = []
    for src in sources:
        print(f"[INFO] Fetching: {src['name']}")
        raw_items = fetch_source(src)
        # on garde l'info du groupe sur chaque item brut si besoin plus tard
        for r in raw_items:
            if r is None:
                continue
            r["source_group"] = src.get("group", "grains")
            all_raw.append(r)

    # 3) Parser le HTML / RSS
    all_parsed = []
    for raw in all_raw:
        parsed = parse_article(raw)
        if parsed.get("text"):
            all_parsed.append(parsed)

    # 3bis) Filtre recence (<= 6 mois)
    recent_parsed = [p for p in all_parsed if is_recent(p)]
    print(f"[INFO] Keeping {len(recent_parsed)} recent articles out of {len(all_parsed)} total.")

    # 4) LLM (résumé + extraction)
    all_enriched = []
    for p in recent_parsed:
        all_enriched.append(summarize_and_extract(p))

    # 5) Scoring "grains"
    all_scored = [score_article(e) for e in all_enriched]

    # 5bis) Alertes (early warning)
    all_alerted = [compute_alert(e) for e in all_scored]

    # 5ter) Macro score (sur les lignes macro, si tu en as)
    # Ici, on considère "macro" = commodity == "other"
    macro_rows = [r for r in all_alerted if (r.get("commodity") or "").lower() == "other"]
    if macro_rows:
        macro_score_dict = compute_macro_score(macro_rows)
        print("[INFO] Macro score :", macro_score_dict)
    else:
        print("[INFO] Macro score : aucun article macro (commodity='other') dans ce run.")

    # 6) Sauvegarde CSV
    csv_path = save_signals(all_alerted)

    # 7) Rapport
    if csv_path:
        generate_daily_report(csv_path)
        generate_daily_plots(csv_path)

    print("[DONE] Daily pipeline finished.")


if __name__ == "__main__":
    main()