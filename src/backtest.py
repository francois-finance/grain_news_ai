# src/backtest.py

import os
import glob
import json
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

DATA_DIR = "data/processed"

COMMODITY_TICKERS = {
    "wheat": "ZW=F",
    "corn": "ZC=F",
    "soy": "ZS=F",
}

FORWARD_DAYS = 5  # horizon de backtest (jours calendaires)


def _sentiment_score(sentiment: str) -> int:
    s = (sentiment or "").lower()
    if s == "bullish":
        return 1
    if s == "bearish":
        return -1
    return 0


def load_signals() -> pd.DataFrame:
    pattern = os.path.join(DATA_DIR, "signals_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"Aucun fichier trouvé avec le pattern {pattern}")

    records = []

    for path in files:
        base = os.path.basename(path)
        date_part = base.replace("signals_", "").replace(".csv", "")
        try:
            file_date = datetime.fromisoformat(date_part).date()
        except Exception:
            print(f"[WARN] Date invalide dans le nom de fichier: {base}")
            continue

        df = pd.read_csv(path)
        for _, row in df.iterrows():
            commodity = str(row.get("commodity", "other")).lower()
            if commodity not in ("wheat", "corn", "soy"):
                continue

            sentiment = str(row.get("sentiment", "neutral"))
            score = _sentiment_score(sentiment)

            records.append(
                {
                    "date": file_date,
                    "commodity": commodity,
                    "sentiment_score": score,
                }
            )

    if not records:
        raise ValueError("Aucun signal exploitable (wheat/corn/soy) trouvé.")

    df_signals = pd.DataFrame(records)

    df_agg = (
        df_signals
        .groupby(["date", "commodity"], as_index=False)
        .agg({"sentiment_score": "sum"})
    )

    return df_agg


def download_prices(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    tickers = list(COMMODITY_TICKERS.values())
    data = yf.download(
        tickers,
        start=start_date - timedelta(days=7),
        end=end_date + timedelta(days=7),
        interval="1d",
        auto_adjust=True,
        progress=False,
    )

    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data.copy()

    close = close.dropna(how="all")
    close.index = close.index.date
    return close


def attach_returns(df_signals: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df_signals.iterrows():
        date = row["date"]
        commodity = row["commodity"]
        score = row["sentiment_score"]

        ticker = COMMODITY_TICKERS.get(commodity)
        if ticker not in prices.columns:
            continue

        if date not in prices.index:
            continue

        date_fwd = date + timedelta(days=FORWARD_DAYS)
        possible_dates = [d for d in prices.index if d >= date_fwd]
        if not possible_dates:
            continue
        d2 = min(possible_dates)

        p0 = prices.loc[date, ticker]
        p1 = prices.loc[d2, ticker]
        if p0 <= 0 or pd.isna(p0) or pd.isna(p1):
            continue

        fwd_ret = (p1 / p0) - 1.0
        r = dict(row)
        r["ticker"] = ticker
        r["fwd_return"] = fwd_ret
        rows.append(r)

    if not rows:
        # Pas assez de data pour le moment
        return pd.DataFrame(
            columns=list(df_signals.columns) + ["ticker", "fwd_return"]
        )

    return pd.DataFrame(rows)


def _summary_stats(df_bt: pd.DataFrame) -> dict:
    """Construit un petit résumé global + par commodity pour le JSON."""
    out = {
        "global": {},
        "by_commodity": {},
    }

    if df_bt.empty:
        return out

    # Global
    out["global"]["n_signals"] = int(len(df_bt))
    out["global"]["mean_fwd_return"] = float(df_bt["fwd_return"].mean())

    bull = df_bt[df_bt["sentiment_score"] > 0]
    bear = df_bt[df_bt["sentiment_score"] < 0]

    out["global"]["bullish_n"] = int(len(bull))
    out["global"]["bearish_n"] = int(len(bear))
    out["global"]["bullish_mean"] = float(bull["fwd_return"].mean()) if len(bull) else None
    out["global"]["bearish_mean"] = float(bear["fwd_return"].mean()) if len(bear) else None

    # Par commodity
    for comm in ["wheat", "corn", "soy"]:
        sub = df_bt[df_bt["commodity"] == comm]
        if sub.empty:
            continue

        d = {}
        d["n_signals"] = int(len(sub))
        d["mean_fwd_return"] = float(sub["fwd_return"].mean())

        sub_bull = sub[sub["sentiment_score"] > 0]
        sub_bear = sub[sub["sentiment_score"] < 0]

        d["bullish_n"] = int(len(sub_bull))
        d["bearish_n"] = int(len(sub_bear))
        d["bullish_mean"] = float(sub_bull["fwd_return"].mean()) if len(sub_bull) else None
        d["bearish_mean"] = float(sub_bear["fwd_return"].mean()) if len(sub_bear) else None

        out["by_commodity"][comm] = d

    return out


def save_backtest_summary(summary: dict, path: str = "data/backtest_summary.json"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[BT] Résumé backtest écrit dans {path}")


def backtest():
    print("[BT] Chargement des signaux...")
    df_signals = load_signals()

    start_date = df_signals["date"].min()
    end_date = df_signals["date"].max()
    print(f"[BT] Période des signaux : {start_date} -> {end_date}")

    print("[BT] Téléchargement des prix futures (yfinance)...")
    prices = download_prices(start_date, end_date)

    print("[BT] Calcul des retours forward...")
    df_bt = attach_returns(df_signals, prices)

    if df_bt.empty:
        print("[BT] Aucune combinaison signal/prix exploitable pour le moment.")
        print("     Reviens quand tu auras quelques semaines de signaux sur des dates passées 😉")
        # On sauvegarde quand même un résumé vide
        save_backtest_summary(_summary_stats(df_bt))
        return

    # Stats console
    print("\n==== Résultats globaux (toutes commodités) ====\n")
    print("Nombre total de signaux :", len(df_bt))
    print("Retour moyen (tous signaux) : {:.4%}".format(df_bt["fwd_return"].mean()))

    bullish = df_bt[df_bt["sentiment_score"] > 0]
    bearish = df_bt[df_bt["sentiment_score"] < 0]
    neutral = df_bt[df_bt["sentiment_score"] == 0]

    if len(bullish) > 0:
        print("Bullish - N =", len(bullish),
              " | mean fwd_ret = {:.4%}".format(bullish["fwd_return"].mean()))
    if len(bearish) > 0:
        print("Bearish - N =", len(bearish),
              " | mean fwd_ret = {:.4%}".format(bearish["fwd_return"].mean()))
    if len(neutral) > 0:
        print("Neutral - N =", len(neutral),
              " | mean fwd_ret = {:.4%}".format(neutral["fwd_return"].mean()))

    print("\n==== Résultats par commodity ====\n")
    for comm in ["wheat", "corn", "soy"]:
        sub = df_bt[df_bt["commodity"] == comm]
        if sub.empty:
            continue

        print(f"--- {comm.upper()} ---")
        print("N signaux :", len(sub))
        print("Retour moyen (tous) : {:.4%}".format(sub["fwd_return"].mean()))

        sub_bull = sub[sub["sentiment_score"] > 0]
        sub_bear = sub[sub["sentiment_score"] < 0]

        if len(sub_bull) > 0:
            print("  Bullish -> mean fwd_ret = {:.4%}".format(sub_bull["fwd_return"].mean()))
        if len(sub_bear) > 0:
            print("  Bearish -> mean fwd_ret = {:.4%}".format(sub_bear["fwd_return"].mean()))

        print("")

    # Sauvegarde du résumé pour le rapport
    summary = _summary_stats(df_bt)
    save_backtest_summary(summary)


if __name__ == "__main__":
    backtest()