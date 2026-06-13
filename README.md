# LLM-Multibagger-OS

An AI-powered stock research tool for finding 100-bagger candidates in the Indian market. Screens Screener.in for high-conviction small-caps, scores them against the Christopher Mayer framework, and lets you interview Claude about any stock — with insights saved to an Obsidian Wiki.

---

## What it does

1. **Screens** Screener.in for companies with high ROCE, low PEG, high promoter holding, and strong growth
2. **Scores** each candidate on a 43-point conviction scorecard (growth quality, capital efficiency, promoter quality, valuation)
3. **Interviews** — you ask questions, Claude answers using 10 years of financial data + live web search
4. **Saves** a full Q&A transcript and a structured investment thesis to your Wiki after each session

---

## Setup

```bash
git clone https://github.com/aman468/LLM-Multibagger-OS
cd LLM-Multibagger-OS
pip install -e .
cp .env.example .env
```

Fill in `.env`:

```
SCREENER_USERNAME=your_screener_email
SCREENER_PASSWORD=your_screener_password
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...        # optional — enables live web search
```

- **Screener.in** account — [screener.in](https://www.screener.in)
- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **Tavily API key** — [app.tavily.com](https://app.tavily.com) (free tier: 1,000 searches/month)

---

## Commands

### `multibagger hunt` — recommended daily workflow

```bash
multibagger hunt
multibagger hunt --top 15
```

Runs the **Catch Them Young v3.0** screen end-to-end: filters small-caps (₹200–5,000 Cr), scores and ranks them, then lets you pick any to interview immediately.

**Score interpretation:**
| Score | Signal |
|-------|--------|
| 38–43 | Maximum conviction — research now |
| 30–37 | Strong candidate |
| 20–29 | Watch list |
| < 20  | Pass |

### `multibagger load <file.csv>` — research from your own screener

```bash
multibagger load my_watchlist.csv
```

Skip live scraping entirely. Export any saved screener from Screener.in → **Download → CSV**, then load it directly. Symbols are resolved automatically from company names (or instantly if you include an `NSE Code` column). Pick any company by number to start an interview.

### `multibagger interview SYMBOL`

```bash
multibagger interview DIXON
multibagger interview NPST
```

Standalone deep-dive on any stock. Fetches full financials, opens a Q&A session with Claude, and generates an investment thesis when you're done.

### `multibagger screen`

```bash
multibagger screen
```

Broader market screen using filters from `config.yaml` (large + mid caps).

---

## The Catch Them Young v3.0 Framework

Based on Christopher Mayer's *100 Baggers*. Hard filters applied via Screener.in:

| Filter | Threshold |
|--------|-----------|
| Market Cap | ₹200–5,000 Cr |
| PEG Ratio | 0 – 1.5× |
| ROCE | > 15% |
| Promoter Holding | > 40% |
| Debt/Equity | < 1.0× |

Passing companies are scored across growth quality, capital efficiency, promoter quality, and valuation — separating genuine compounders from companies that merely pass the filter.

---

## Wiki output

Each interview saves to `Wiki/<SYMBOL>/` — open the folder as an [Obsidian](https://obsidian.md) vault:

```
Wiki/
├── index.md          ← master table: all researched stocks + verdict
├── DIXON/
│   ├── financials.md ← key ratios, pros/cons, peer comparison
│   ├── qa.md         ← full Q&A transcript
│   └── thesis.md     ← AI investment thesis with 100-bagger scorecard
└── NPST/
    └── ...
```

---

## Project structure

```
screener/
├── main.py       — CLI (hunt, load, screen, interview)
├── scraper.py    — Screener.in login, scraping, symbol search
├── loader.py     — CSV import and display
├── v3screen.py   — v3.0 conviction scoring
├── interview.py  — streaming Q&A loop + thesis generation
├── screen.py     — large-cap filter pipeline
├── search.py     — Tavily web search
└── wiki.py       — Obsidian Markdown writer
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `login failed` | Check credentials in `.env`; wait 2 min if rate-limited |
| `command not found: multibagger` | Run `pip install -e .` from the project folder |
| Session expired | Delete `.screener_session` — it re-logins automatically |
| Symbol not found | Use the exact Screener.in URL slug (e.g. `DIXON`, not `Dixon Technologies`) |
| Special character in symbol | Wrap in quotes: `multibagger interview "GVT&D"` |
