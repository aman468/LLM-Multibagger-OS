"""Catch Them Young — v3.0 screening and conviction scoring."""

V3_QUERY = (
    "Market Capitalization < 5000 AND Market Capitalization > 200 AND "
    "PEG Ratio > 0 AND PEG Ratio < 1.5 AND "
    "Return on capital employed > 15 AND "
    "Promoter holding > 40 AND "
    "Debt to equity < 1"
)


def _f(row, col, default=0.0):
    try:
        return float(str(row.get(col, default)).replace(',', '').replace('%', '').strip())
    except Exception:
        return default


def score_v3(row: dict) -> tuple[int, list[str]]:
    """Score a company on v3.0 conviction criteria. Returns (score, detail_list)."""
    pts = 0
    detail = []

    # Stage 2 — Growth Quality (max 17)
    sales5  = _f(row, 'Sales Var 5Yrs%')
    profit5 = _f(row, 'Profit Var 5Yrs%')
    qtr_sal = _f(row, 'Qtr Sales Var%')
    opm_cur = _f(row, 'OPM%')
    opm_5yr = _f(row, '5Yr OPM%')

    if sales5 >= 25:    pts += 8; detail.append(f'Rev5yr:{sales5:.0f}%')
    elif sales5 >= 18:  pts += 6; detail.append(f'Rev5yr:{sales5:.0f}%')
    elif sales5 >= 12:  pts += 3; detail.append(f'Rev5yr:{sales5:.0f}%')

    if profit5 >= 25:   pts += 5; detail.append(f'Prft5yr:{profit5:.0f}%')
    elif profit5 >= 15: pts += 3; detail.append(f'Prft5yr:{profit5:.0f}%')

    if qtr_sal > sales5 > 0:  pts += 2; detail.append('AccelRev')
    if opm_cur > opm_5yr > 0: pts += 2; detail.append('ExpandOPM')

    # Stage 3 — Capital Efficiency (max 11)
    roce    = _f(row, 'ROCE%')
    roce5yr = _f(row, 'ROCE 5Yr%')
    at      = _f(row, 'Asset Turnover')

    if roce >= 35:   pts += 6; detail.append(f'ROCE:{roce:.0f}%')
    elif roce >= 25: pts += 4; detail.append(f'ROCE:{roce:.0f}%')
    elif roce >= 15: pts += 2; detail.append(f'ROCE:{roce:.0f}%')

    if roce5yr >= 20:   pts += 3; detail.append(f'ROCE5yr:{roce5yr:.0f}%')
    elif roce5yr >= 15: pts += 1; detail.append(f'ROCE5yr:{roce5yr:.0f}%')

    if at >= 1.5:   pts += 2; detail.append(f'AT:{at:.1f}')
    elif at >= 1.0: pts += 1; detail.append(f'AT:{at:.1f}')

    # Stage 4 — Promoter Quality (max 10)
    try:
        promo = float(str(row.get('Promoter %', '-')).replace('%', '').strip())
        if promo >= 65:   pts += 10; detail.append(f'Promo:{promo:.0f}%')
        elif promo >= 55: pts += 7;  detail.append(f'Promo:{promo:.0f}%')
        elif promo >= 40: pts += 4;  detail.append(f'Promo:{promo:.0f}%')
    except Exception:
        pass

    # Stage 7 — Valuation Comfort (max 5)
    peg = _f(row, 'PEG', 99)
    if peg < 0.5:   pts += 5; detail.append(f'PEG:{peg:.2f}')
    elif peg < 0.8: pts += 4; detail.append(f'PEG:{peg:.2f}')
    elif peg < 1.0: pts += 3; detail.append(f'PEG:{peg:.2f}')
    elif peg < 1.5: pts += 2; detail.append(f'PEG:{peg:.2f}')

    return pts, detail


def run_v3_screen(client, limit: int = 100) -> list[tuple[int, dict, list[str]]]:
    """Run v3.0 query, enrich, score, return sorted (score, row, detail) list."""
    results = client.run_screen(V3_QUERY, limit=limit, sort_by="Return on capital employed")
    if not results:
        return []
    enriched = client.enrich_candidates(results)
    scored = []
    for row in enriched:
        pts, detail = score_v3(row)
        scored.append((pts, row, detail))
    scored.sort(key=lambda x: -x[0])
    return scored


def display_v3_results(scored: list[tuple[int, dict, list[str]]], top_n: int = 10) -> None:
    """Print v3.0 ranked results as plain text."""
    if not scored:
        print("No candidates found under v3.0 filters.")
        return

    SEP = "=" * 84
    BAR = "-" * 84
    HDR = (
        f"{'#':>2}  {'Name':<22}  {'Score':>5}  {'ROCE':>5}  "
        f"{'Rev5yr':>6}  {'PEG':>5}  {'Promo':>6}  {'MCap Cr':>8}  Symbol"
    )

    print(f"\n{SEP}")
    print(f"  Catch Them Young — v3.0 Top {top_n}   ({len(scored)} qualified)")
    print(f"  Score: Growth(17) + Efficiency(11) + Promoter(10) + Valuation(5) = 43 max")
    print(SEP)
    print(HDR)
    print(BAR)

    for i, (pts, row, _) in enumerate(scored[:top_n], 1):
        name  = row.get('Name', '-')[:22]
        roce  = f"{_f(row, 'ROCE%'):.0f}%"
        s5    = f"{_f(row, 'Sales Var 5Yrs%'):.0f}%"
        peg   = f"{_f(row, 'PEG', 99):.2f}"
        promo = row.get('Promoter %', '-')
        mcap  = f"{_f(row, 'Mar CapRs.Cr.'):.0f}"
        sym   = row.get('symbol', '')
        print(f"{i:>2}  {name:<22}  {pts:>5}  {roce:>5}  {s5:>6}  {peg:>5}  {promo:>6}  {mcap:>8}  {sym}")

    print(SEP)
    print(f"\nEnter # (1-{top_n}) or symbol to interview. Press Enter to exit.\n")
