import csv
from datetime import datetime
import os

def save_signals(signals, output_dir="data/processed"):
    if not signals:
        print("[INFO] No signals to save.")
        return ""

    os.makedirs(output_dir, exist_ok=True)

    date = datetime.utcnow().strftime("%Y-%m-%d")
    path = os.path.join(output_dir, f"signals_{date}.csv")

    fields = list(signals[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(signals)

    print(f"[OK] Saved {len(signals)} articles → {path}")
    return path