"""Load and display a Screener.in CSV export without live scraping."""

import csv
from pathlib import Path

# Maps exact CSV column names to the keys expected by score_v3().
# More specific strings must come before subsets (e.g. "Average ROCE 5Years" before "ROCE").
_V3_REMAP: list[tuple[str, str]] = [
    ("Average return on capital employed 5Years", "ROCE 5Yr%"),
    ("Return on capital employed",                "ROCE%"),
    ("OPM 5Year",                                 "5Yr OPM%"),
    ("OPM",                                       "OPM%"),
    ("Sales growth 5Years",                       "Sales Var 5Yrs%"),
    ("Profit growth 5Years",                      "Profit Var 5Yrs%"),
    ("YOY Quarterly sales growth",                "Qtr Sales Var%"),
    ("Asset Turnover Ratio",                      "Asset Turnover"),
    ("PEG Ratio",                                 "PEG"),
    ("Market Capitalization",                     "Mar CapRs.Cr."),
    ("NSE Code",                                  "symbol"),
    ("Promoter holding",                          "Promoter %"),
]

# Columns to never show in the summary table (identifiers, not analytics).
_SKIP_DISPLAY = {"bse code", "isin code", "isin", "s.no.", "s.no"}

# Display priority: substrings matched case-insensitively against column names.
_PRIORITY_SUBSTRINGS = [
    "score",                  # v3 score column we add ourselves
    "market cap", "mar cap",
    "return on capital",      # ROCE
    "sales growth", "sales var 5",
    "profit growth", "profit var 5",
    "peg",
    "promoter",
    "current price", "cmp",
    "opm",
    "industry",
]


def load_csv(path: str) -> list[dict]:
    """Read a Screener.in CSV export. Returns list of row dicts (header row removed)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def normalize_row_for_v3(row: dict) -> dict:
    """Add v3 scoring keys to a row alongside original keys (non-destructive)."""
    out = dict(row)
    for csv_key, v3_key in _V3_REMAP:
        if csv_key in row and v3_key not in out:
            out[v3_key] = row[csv_key]
    return out


def can_score_v3(headers: list[str]) -> bool:
    """True if the CSV has enough columns to run meaningful v3 scoring."""
    has_roce = any("return on capital employed" in h.lower() for h in headers)
    has_peg  = any("peg" in h.lower() for h in headers)
    return has_roce and has_peg


def score_and_sort(rows: list[dict]) -> list[tuple[int, dict, list[str]]]:
    """Score rows using v3 framework. Returns (score, original_row, detail) sorted descending."""
    from .v3screen import score_v3
    scored = []
    for row in rows:
        norm = normalize_row_for_v3(row)
        pts, detail = score_v3(norm)
        scored.append((pts, row, detail))  # keep original row, not normalized
    scored.sort(key=lambda x: -x[0])
    return scored


def find_symbol_col(headers: list[str]) -> str:
    """Return the column name that holds a ticker/symbol, or empty string if none."""
    for h in headers:
        if h.lower() in ("symbol", "nse code", "nse symbol", "ticker"):
            return h
    return ""


def _name_col(headers: list[str]) -> str:
    for h in headers:
        if "name" in h.lower():
            return h
    return headers[0]


def _pick_extra_cols(headers: list[str], name_col: str, max_cols: int = 6) -> list[str]:
    skip = {name_col.lower()} | _SKIP_DISPLAY
    picked: list[str] = []
    used: set[str] = set()

    for sub in _PRIORITY_SUBSTRINGS:
        for h in headers:
            if h in used or h.lower() in skip:
                continue
            if sub in h.lower():
                picked.append(h)
                used.add(h)
                break
        if len(picked) >= max_cols:
            break

    # Fill remaining slots with whatever's left (excluding skip list)
    for h in headers:
        if len(picked) >= max_cols:
            break
        if h not in used and h.lower() not in skip:
            picked.append(h)
            used.add(h)

    return picked


def _abbrev(col: str, width: int) -> str:
    replacements = [
        ("Return on capital employed",                "ROCE%"),
        ("Average return on capital employed 5Years", "ROCE 5yr%"),
        ("Sales growth 5Years",                       "Sales 5yr%"),
        ("Profit growth 5Years",                      "Profit 5yr%"),
        ("Market Capitalization",                     "MCap Cr"),
        ("Mar Cap Rs.Cr.",                            "MCap Cr"),
        ("Mar Cap Rs.",                               "MCap Cr"),
        ("Promoter holding",                          "Promoter%"),
        ("Current Price",                             "CMP"),
        ("Asset Turnover Ratio",                      "AssetTO"),
        ("Industry Group",                            "Industry"),
        ("OPM 5Year",                                 "OPM 5yr%"),
    ]
    for long, short in replacements:
        if long.lower() in col.lower():
            col = short
            break
    return col[:width]


def display_watchlist(rows: list[dict], scored: list[tuple[int, dict, list[str]]] | None = None) -> None:
    if not rows:
        print("No rows found in CSV.")
        return

    if scored:
        _display_scored(scored)
    else:
        _display_plain(rows)


def _display_scored(scored: list[tuple[int, dict, list[str]]]) -> None:
    # Build headers from the original (un-normalized) row, inserting Score first
    raw_headers = list(scored[0][1].keys())
    nc = _name_col(raw_headers)
    extra = _pick_extra_cols(["Score"] + raw_headers, nc)

    COL_W = 10
    hdr = f"{'#':>3}  {'Name':<24}"
    for col in extra:
        hdr += f"  {_abbrev(col, COL_W):>{COL_W}}"

    width = len(hdr)
    SEP = "=" * width
    BAR = "-" * width

    print(f"\n{SEP}")
    print(f"  Your Watchlist — {len(scored)} companies  (ranked by v3.0 conviction score, 43 max)")
    print(SEP)
    print(hdr)
    print(BAR)

    for i, (pts, row, detail) in enumerate(scored, 1):
        row_with_score = {"Score": str(pts), **row}
        name = row.get(nc, "-")[:24]
        line = f"{i:>3}  {name:<24}"
        for col in extra:
            val = row_with_score.get(col, "-")[:COL_W]
            line += f"  {val:>{COL_W}}"
        print(line)

    print(SEP)
    print(f"  Score bands: 38–43 Research now  |  30–37 Strong  |  20–29 Watch  |  <20 Pass")
    print(SEP)


def _display_plain(rows: list[dict]) -> None:
    headers = list(rows[0].keys())
    nc = _name_col(headers)
    extra = _pick_extra_cols(headers, nc)

    COL_W = 10
    hdr = f"{'#':>3}  {'Name':<24}"
    for col in extra:
        hdr += f"  {_abbrev(col, COL_W):>{COL_W}}"

    width = len(hdr)
    SEP = "=" * width
    BAR = "-" * width

    print(f"\n{SEP}")
    print(f"  Your Watchlist — {len(rows)} companies")
    print(SEP)
    print(hdr)
    print(BAR)

    for i, row in enumerate(rows, 1):
        name = row.get(nc, "-")[:24]
        line = f"{i:>3}  {name:<24}"
        for col in extra:
            val = row.get(col, "-")[:COL_W]
            line += f"  {val:>{COL_W}}"
        print(line)

    print(SEP)
