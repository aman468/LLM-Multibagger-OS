# Multibagger Screener — User Guide

Find 100-bagger candidates in the Indian market using two screening modes, then research each stock through an AI interview session. All insights are auto-saved to an Obsidian Wiki.

---

## First-Time Setup

### 1. Install the CLI
```bash
cd ~/Documents/LLM-Multibagger-OS
pip install -e .
```

### 2. Configure credentials
```bash
cp .env.example .env
```
Edit `.env` and fill in:
```
SCREENER_USERNAME=your_screener_email@example.com
SCREENER_PASSWORD=your_screener_password
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
```
- **Screener.in** — your login at screener.in
- **Anthropic API key** — from console.anthropic.com
- **Tavily API key** — from app.tavily.com (free tier: 1,000 searches/month)

---

## Commands

### `multibagger hunt` — Recommended daily workflow

```bash
multibagger hunt
multibagger hunt --top 15     # show top 15 instead of 10
```

Runs the **Catch Them Young v3.0** framework end-to-end in one command:

1. Screens for small-cap hidden gems (₹200–5,000 Cr market cap)
2. Scores each company on a 43-point conviction scorecard:
   - **Growth Quality** (17 pts) — 5yr revenue + profit CAGR, acceleration, margin expansion
   - **Capital Efficiency** (11 pts) — ROCE, ROCE 5yr average, asset turnover
   - **Promoter Quality** (10 pts) — promoter holding %
   - **Valuation** (5 pts) — PEG ratio
3. Displays top 10 ranked by score
4. Prompts you to pick a stock to interview — type the **rank number** or **symbol**:

```
Interview (#/symbol, Enter to quit): 1       ← interviews rank #1
Interview (#/symbol, Enter to quit): NPST    ← interviews by symbol
Interview (#/symbol, Enter to quit):         ← press Enter to exit
```

After each interview the shortlist reappears so you can pick the next one.

---

### `multibagger screen` — Large-cap screener

```bash
multibagger screen
```

Screens the broader market (large + mid caps) using filters from `config.yaml`.
Shows 50 candidates sorted by market cap with: `Name | CMP | PEG | ROCE% | Promo% | MCap Cr`

Tune the filters in `config.yaml`:
```yaml
filters:
  market_cap_min_cr: 1000     # min market cap in crores
  peg_max: 2.5                # max PEG ratio
  peg_min: 0                  # exclude negative earnings
  roic_min: 15                # min ROCE %
  promoter_holding_min: 40    # min promoter holding %
```

---

### `multibagger interview SYMBOL` — Standalone interview

```bash
multibagger interview NPST
multibagger interview "GVT&D"     # use quotes for symbols with special characters
multibagger interview POLYCAB
```

Fetches full 10-year financials from Screener.in, augments with live web search (Tavily), and opens an interactive Q&A session where Claude answers your questions. Type `done` or press Enter on an empty line to finish.

---

## The v3.0 Framework (Catch Them Young)

`multibagger hunt` applies these hard filters via Screener.in:

| Filter | Threshold |
|--------|-----------|
| Market Cap | ₹200–5,000 Cr |
| PEG Ratio | 0 – 1.5x |
| ROCE | > 15% |
| Promoter Holding | > 40% |
| Debt/Equity | < 1.0x |

Companies that pass are then scored on 9-stage criteria from the **Catch Them Young** framework. The conviction score separates the truly exceptional from merely passing companies.

**Score interpretation:**
- **38–43** — Maximum conviction, research immediately
- **30–37** — Strong candidate, worth interviewing
- **20–29** — Tracking position, monitor for improvement
- **< 20** — Pass

---

## Good Questions to Ask in an Interview

```
What is their core competitive moat?
How has ROCE trended over the last 5–10 years?
What is the total addressable market and how much have they penetrated?
Who are the key competitors and what is this company's advantage?
What are the biggest risks to the thesis?
Is management known for good capital allocation?
What does the balance sheet look like — debt, working capital, pledging?
Has revenue growth been consistent or lumpy?
What has free cash flow looked like over the last 5 years?
Is there any risk of promoter dilution?
Does any single customer account for more than 30% of revenue?
Is operating margin expanding or contracting?
```

---

## Wiki Output (Obsidian)

Open `~/Documents/LLM-Multibagger-OS/Wiki/` as an Obsidian vault.

Each researched stock gets its own folder:
```
Wiki/
├── index.md            ← master table of all researched stocks + verdict
├── NPST/
│   ├── financials.md   ← key ratios snapshot, pros/cons, peers
│   ├── qa.md           ← full Q&A transcript from your session
│   └── thesis.md       ← AI-generated investment thesis with scorecard
└── POLYCAB/
    └── ...
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `login failed` error | Check credentials in `.env`; wait 2 min if rate-limited |
| `command not found: multibagger` | Run `pip install -e .` from the project folder |
| Session expired | Delete `.screener_session` — it will re-login automatically |
| No candidates in `hunt` | Filters are strict by design; try `multibagger screen` for broader results |
| Symbol not found | Use exact Screener.in URL symbol — search at screener.in/api/company/search/?q=name |
| Special character in symbol | Wrap in quotes: `multibagger interview "GVT&D"` |
| Output collapsed in Claude Code | Press `ctrl+o` to expand, or run in your Mac terminal |

---

## Project Structure

```
LLM-Multibagger-OS/
├── GUIDE.md              ← this file
├── config.yaml           ← filters for multibagger screen
├── .env                  ← credentials (never commit)
├── .env.example          ← template for .env
├── pyproject.toml        ← makes `multibagger` a CLI command
├── screener/
│   ├── main.py           ← CLI entry point (screen, interview, hunt)
│   ├── scraper.py        ← Screener.in login + data fetch
│   ├── screen.py         ← large-cap filter pipeline + display
│   ├── v3screen.py       ← v3.0 conviction scoring + hunt logic
│   ├── interview.py      ← Q&A loop + thesis generation
│   ├── search.py         ← Tavily web search
│   └── wiki.py           ← Obsidian Markdown writer
└── Wiki/
    ├── index.md          ← master candidate index
    └── <SYMBOL>/         ← one folder per researched stock
```
