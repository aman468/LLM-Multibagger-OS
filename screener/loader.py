"""Load and display a Screener.in CSV export without live scraping."""

import csv
from pathlib import Path

# Columns we prefer to show, matched case-insensitively against whatever's in the CSV.
_PRIORITY_SUBSTRINGS = ["cmp", "mar cap", "market cap", "roce", "p/e", "pe ", "peg", "promoter", "sales var", "profit var"]


def load_csv(path: str) -> list[dict]:
    """Read a Screener.in CSV export. Returns list of row dicts (header row removed)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _name_col(headers: list[str]) -> str:
    for h in headers:
        if "name" in h.lower():
            return h
    return headers[0]


def _pick_extra_cols(headers: list[str], name_col: str, max_cols: int = 6) -> list[str]:
    """Pick up to max_cols non-name columns by priority, then fill from whatever's left."""
    skip = {name_col.lower(), "s.no.", "s.no"}
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

    for h in headers:
        if len(picked) >= max_cols:
            break
        if h not in used and h.lower() not in skip:
            picked.append(h)
            used.add(h)

    return picked


def find_symbol_col(headers: list[str]) -> str:
    """Return the column name that holds a ticker/symbol, or empty string if none."""
    for h in headers:
        hl = h.lower()
        if hl in ("symbol", "nse code", "nse symbol", "bse code", "ticker"):
            return h
    return ""


def _abbrev(col: str, width: int) -> str:
    """Shorten common long column names before truncating."""
    replacements = [
        ("Promoter holding", "Promoter"),
        ("Sales Var 5Yrs", "Sales 5yr"),
        ("Profit Var 5Yrs", "Profit 5yr"),
        ("Mar Cap Rs.Cr.", "MCap Cr"),
        ("Mar Cap Rs.", "MCap Cr"),
        ("Market Cap", "MCap Cr"),
    ]
    for long, short in replacements:
        if long.lower() in col.lower():
            col = short
            break
    return col[:width]


def display_watchlist(rows: list[dict]) -> None:
    if not rows:
        print("No rows found in CSV.")
        return

    headers = list(rows[0].keys())
    nc = _name_col(headers)
    extra = _pick_extra_cols(headers, nc)

    COL_W = 11
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
