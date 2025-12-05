# src/plots.py

import os
import csv
from collections import Counter, defaultdict

import matplotlib.pyplot as plt

from src.scoring_macro import compute_macro_score


def _load_rows(csv_path: str):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sentiment_score(sentiment: str) -> int:
    s = (sentiment or "").lower()
    if s == "bullish":
        return 1
    if s == "bearish":
        return -1
    return 0


def plot_articles_by_commodity(csv_path: str, out_dir: str = "figures") -> str:
    os.makedirs(out_dir, exist_ok=True)
    rows = _load_rows(csv_path)

    counts = Counter((r.get("commodity") or "other").lower() for r in rows)

    labels = list(counts.keys())
    values = [counts[k] for k in labels]

    plt.figure()
    plt.bar(labels, values)
    plt.title("Nombre d'articles par commodity")
    plt.ylabel("Nombre d'articles")
    plt.tight_layout()

    base = os.path.basename(csv_path).replace("signals_", "").replace(".csv", "")
    out_path = os.path.join(out_dir, f"articles_by_commodity_{base}.png")
    plt.savefig(out_path)
    plt.close()

    print(f"[PLOT] Saved {out_path}")
    return out_path


def plot_sentiment_by_commodity(csv_path: str, out_dir: str = "figures") -> str:
    os.makedirs(out_dir, exist_ok=True)
    rows = _load_rows(csv_path)

    scores_sum = defaultdict(int)
    scores_count = defaultdict(int)

    for r in rows:
        c = (r.get("commodity") or "other").lower()
        s = _sentiment_score(r.get("sentiment"))
        scores_sum[c] += s
        scores_count[c] += 1

    labels = list(scores_sum.keys())
    avg_vals = [
        scores_sum[c] / scores_count[c] if scores_count[c] else 0.0
        for c in labels
    ]

    plt.figure()
    plt.bar(labels, avg_vals)
    plt.title("Sentiment moyen par commodity (bullish = +1, bearish = -1)")
    plt.ylabel("Score moyen")
    plt.axhline(0, linestyle="--")
    plt.tight_layout()

    base = os.path.basename(csv_path).replace("signals_", "").replace(".csv", "")
    out_path = os.path.join(out_dir, f"sentiment_by_commodity_{base}.png")
    plt.savefig(out_path)
    plt.close()

    print(f"[PLOT] Saved {out_path}")
    return out_path


def plot_macro_score(csv_path: str, out_dir: str = "figures") -> str:
    """
    Utilise uniquement les lignes 'macro' (commodity == 'other')
    et trace un bar chart des scores par thème + score global.
    """
    os.makedirs(out_dir, exist_ok=True)
    rows = _load_rows(csv_path)

    macro_rows = [r for r in rows if (r.get("commodity") or "").lower() == "other"]
    if not macro_rows:
        print("[PLOT] No macro rows (commodity='other'), skipping macro plot.")
        return ""

    scores = compute_macro_score(macro_rows)

    # on trace weather / fx / energy / shipping / other + final
    labels = ["weather", "fx", "energy", "shipping", "other", "final"]
    values = [
        scores.get("weather", 0),
        scores.get("fx", 0),
        scores.get("energy", 0),
        scores.get("shipping", 0),
        scores.get("other", 0),
        scores.get("final_macro_score", 0),
    ]

    plt.figure()
    plt.bar(labels, values)
    plt.title("Score macro-grains par thème (+ global)")
    plt.ylabel("Score")
    plt.axhline(0, linestyle="--")
    plt.tight_layout()

    base = os.path.basename(csv_path).replace("signals_", "").replace(".csv", "")
    out_path = os.path.join(out_dir, f"macro_scores_{base}.png")
    plt.savefig(out_path)
    plt.close()

    print(f"[PLOT] Saved {out_path}")
    return out_path


def generate_daily_plots(csv_path: str, out_dir: str = "figures") -> None:
    """
    Fonction façade : génère tous les graphes du jour.
    """
    print("[PLOT] Generating daily plots...")
    plot_articles_by_commodity(csv_path, out_dir=out_dir)
    plot_sentiment_by_commodity(csv_path, out_dir=out_dir)
    plot_macro_score(csv_path, out_dir=out_dir)
    print("[PLOT] All plots generated.")