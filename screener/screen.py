"""Screening logic — builds Screener.in query from config filters and displays results."""

import yaml
from rich.console import Console

console = Console()

# Maps a display label to substrings to match against actual Screener.in column names (case-insensitive).
# Order here = column order in the output table.
COLUMN_PRIORITY = [
    ("S.No.", ["s.no"]),
    ("Name", ["name"]),
    ("CMP", ["cmprs", "cmp rs", "current price"]),
    ("PEG", ["peg"]),
    ("ROCE %", ["roce%", "roce %"]),
    ("Promoter %", ["promoter"]),
    ("MCap Cr", ["mar cap", "market cap"]),
]


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_query(filters: dict) -> str:
    """Convert config filters into Screener.in query language with explicit column select."""
    conditions = []

    if filters.get("market_cap_min_cr"):
        conditions.append(f"Market Capitalization > {filters['market_cap_min_cr']}")

    peg_min = filters.get("peg_min", 0)
    peg_max = filters.get("peg_max")
    if peg_min is not None:
        conditions.append(f"PEG Ratio > {peg_min}")
    if peg_max:
        conditions.append(f"PEG Ratio < {peg_max}")

    if filters.get("roic_min"):
        conditions.append(f"Return on capital employed > {filters['roic_min']}")

    if filters.get("promoter_holding_min"):
        conditions.append(f"Promoter holding > {filters['promoter_holding_min']}")

    return " AND ".join(conditions)


def _match_columns(available: list[str]) -> list[tuple[str, str]]:
    """Return list of (display_label, actual_col_name) for columns we care about."""
    result = []
    used = set()
    for label, keywords in COLUMN_PRIORITY:
        for actual in available:
            if actual in used:
                continue
            actual_lower = actual.lower()
            if any(kw in actual_lower for kw in keywords):
                result.append((label, actual))
                used.add(actual)
                break
    return result


def display_candidates(candidates: list[dict], filters: dict) -> None:
    """Print screening results as a plain text table."""
    if not candidates:
        print("No candidates found. Try relaxing filters in config.yaml")
        return

    available_cols = [k for k in candidates[0].keys() if k != "symbol"]
    matched = _match_columns(available_cols)
    lta = {label: actual for label, actual in matched}

    def v(row, label, default="-"):
        actual = lta.get(label)
        return row.get(actual, default) if actual else default

    SEP = "=" * 74
    BAR = "-" * 74
    HDR = f"{'#':>3}  {'Name':<18}  {'CMP':>9}  {'PEG':>5}  {'ROCE%':>7}  {'Promo%':>7}  {'MCap Cr':>11}"

    print(f"\n{SEP}")
    print(f"  100-Bagger Candidates  —  {len(candidates)} found")
    print(SEP)
    print(HDR)
    print(BAR)

    for row in candidates:
        num   = v(row, "S.No.").rstrip(".")
        name  = v(row, "Name")[:18]
        cmp_  = v(row, "CMP")
        peg   = v(row, "PEG")
        roce  = v(row, "ROCE %")
        promo = row.get("Promoter %", "-")
        mcap  = v(row, "MCap Cr")
        print(f"{num:>3}  {name:<18}  {cmp_:>9}  {peg:>5}  {roce:>7}  {promo:>7}  {mcap:>11}")

    print(SEP)
    print("\nRun: multibagger interview <SYMBOL> to research any stock.\n")


def run_screen(client, config_path: str) -> list[dict]:
    """Load config, build query, run screen, display and return candidates."""
    config = load_config(config_path)
    filters = config.get("filters", {})
    screen_cfg = config.get("screen", {})

    query = build_query(filters)
    console.print(f"\n[bold]Screening query:[/bold] [dim]{query}[/dim]\n")

    with console.status("[bold green]Fetching candidates from Screener.in..."):
        candidates = client.run_screen(
            query=query,
            limit=screen_cfg.get("result_limit", 50),
            sort_by=screen_cfg.get("sort_by", "Market Capitalization"),
        )

    if candidates:
        candidates = client.enrich_candidates(candidates)

    display_candidates(candidates, filters)
    return candidates
