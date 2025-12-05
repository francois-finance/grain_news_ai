Grain News AI

Automated Intelligence Pipeline for Global Grain Markets (Wheat · Corn · Soy)
Real-time news ingestion • LLM analytics • Macro scoring • Price impact estimates • Alerts • Backtesting

⸻

Overview

Grain News AI is a fully automated intelligence system designed to extract actionable trading signals from global agricultural news flows.

The pipeline ingests multi-language news (EN/FR/ES/PT), parses articles, summarizes them using an LLM, classifies events, computes sentiment & macro scores, generates alerts, quantifies price impact, and produces a complete Daily Grain Intelligence Report with charts.

It also includes a lightweight historical backtester to evaluate the predictive power of generated signals.

⸻

Key Features

1. Multi-source News Scraping
	•	Dozens of configurable sources
	•	Grains → Wheat, Corn, Soy
	•	Macro → Weather, FX, Energy, Shipping, Geopolitics
	•	Automatic date filtering (≤ 6 months)

2. LLM-Enhanced Analytics

For each article, the system extracts:
	•	Market sentiment (bullish / bearish / neutral)
	•	Structured analysis
	•	Price impact assessment
	•	Risks & vulnerabilities
	•	Short-term outlook
	•	Commodity classification
	•	Event type (supply, demand, logistics, weather, policy…)

3. Early-Warning Signal Engine

Articles are scored for:
	•	Severity of risk
	•	Trigger keywords (frost, drought, strikes, export bans, BRL volatility…)
	•	Alerts: INFO → WATCH → CRITICAL

4. Macro-Grains Indicator

A synthetic score (0 to 5):
	•	Weather impact
	•	FX pressure
	•	Energy cost shock
	•	Shipping disruptions
	•	Other macro factors

Including a daily graphic of macro scores.

5. Automatic Daily Report

Generated as Markdown:
	•	Macro score summary
	•	Graphs (articles count, sentiment, macro heatmap)
	•	Alerts of the day
	•	Per-commodity analysis (bias, risks, outlook)
	•	Price-impact ranges derived from historical relationships
	•	Macro-theme breakdown
	•	Backtest performance section (optional)

6. Backtester (optional)
	•	Fetches futures prices via Yahoo Finance
	•	Computes forward returns (1–20 days)
	•	Evaluates signal quality:
	•	mean impact
	•	bullish/bearish split
	•	per-commodity stats
	•	Saves a JSON summary for the report

⸻

Project Structure
grain_news_ai/
│
├── configs/
│   └── sources.yaml               # Full source list (grains, macro, fx, energy…)
│
├── src/
│   ├── main_daily.py              # Main daily pipeline
│   ├── scraping.py                # News fetching
│   ├── parsing.py                 # HTML / RSS parsing
│   ├── llm_summarizer.py          # LLM summaries + event extraction
│   ├── scoring.py                 # Sentiment + signal scoring
│   ├── scoring_macro.py           # Macro-grains scoring logic
│   ├── price_impact.py            # Quantified impact from historical patterns
│   ├── alerts.py                  # Early-warning system
│   ├── storage.py                 # CSV saving
│   ├── reports.py                 # Daily markdown report
│   ├── plots.py                   # Chart generation
│   └── backtest.py                # Backtest engine
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── backtest_summary.json      # Generated after running backtester
│
├── figures/                       # Auto-generated charts
├── reports/                       # Auto-generated daily reports
└── README.md

Installation

1. Clone the repo
git clone https://github.com/francois-finance/grain_news_ai.git
cd grain_news_ai
2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
4. Configure your API keys
GROQ_API_KEY=your_key_here
Running the Daily Pipeline
python -m src.main_daily
Running the Backtest
python -m src.backtest
Output is saved to:
data/backtest_summary.json

LLM Model

Currently using:
	•	Groq Llama-3, extremely fast inference
	•	Configurable generation mode
	•	Extracts structured JSON from raw market text
