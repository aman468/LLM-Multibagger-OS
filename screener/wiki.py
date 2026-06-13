"""Wiki writer — creates and updates Obsidian-compatible Markdown files."""

import os
from datetime import datetime
from pathlib import Path


def _wiki_root(wiki_dir: str) -> Path:
    root = Path(wiki_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def stock_dir(wiki_dir: str, symbol: str) -> Path:
    d = _wiki_root(wiki_dir) / symbol.upper()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_financials(wiki_dir: str, symbol: str, company_data: dict) -> Path:
    d = stock_dir(wiki_dir, symbol)
    path = d / "financials.md"
    ratios = company_data.get("ratios", {})
    peers = company_data.get("peers", [])
    pros = company_data.get("pros", [])
    cons = company_data.get("cons", [])

    lines = [
        f"# {company_data.get('name', symbol)} — Financials Snapshot",
        f"*Fetched: {datetime.now().strftime('%Y-%m-%d')}*",
        "",
        "## Key Ratios",
        "",
    ]
    for k, v in ratios.items():
        lines.append(f"- **{k}**: {v}")

    if pros:
        lines += ["", "## Pros (Screener.in)", ""]
        for p in pros:
            lines.append(f"- {p}")

    if cons:
        lines += ["", "## Cons (Screener.in)", ""]
        for c in cons:
            lines.append(f"- {c}")

    if peers:
        lines += ["", "## Peer Comparison", ""]
        headers = list(peers[0].keys()) if peers else []
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for peer in peers:
            lines.append("| " + " | ".join(str(peer.get(h, "-")) for h in headers) + " |")

    if company_data.get("about"):
        lines += ["", "## About", "", company_data["about"]]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def save_qa(wiki_dir: str, symbol: str, qa_pairs: list[dict]) -> Path:
    d = stock_dir(wiki_dir, symbol)
    path = d / "qa.md"
    lines = [
        f"# {symbol.upper()} — Research Q&A",
        f"*Session: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]
    for i, pair in enumerate(qa_pairs, 1):
        lines.append(f"## Q{i}: {pair['question']}")
        lines.append("")
        lines.append(pair["answer"])
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def save_thesis(wiki_dir: str, symbol: str, thesis: str) -> Path:
    d = stock_dir(wiki_dir, symbol)
    path = d / "thesis.md"
    path.write_text(thesis, encoding="utf-8")
    return path


def update_index(wiki_dir: str, symbol: str, company_name: str, verdict: str, ratios: dict) -> None:
    root = _wiki_root(wiki_dir)
    index_path = root / "index.md"

    # Read existing index
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    # Remove old entry for this symbol if present
    lines = existing.splitlines()
    lines = [l for l in lines if f"[[{symbol.upper()}/" not in l]

    # Rebuild header if missing
    if not any("# 100-Bagger Candidates" in l for l in lines):
        lines = [
            "# 100-Bagger Candidates — Master Index",
            "",
            "| Symbol | Name | Date | Market Cap | ROCE | PE | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ] + [l for l in lines if l.startswith("|") and "Symbol" not in l]

    date = datetime.now().strftime("%Y-%m-%d")
    market_cap = ratios.get("Market Cap", ratios.get("Mkt Cap", "-"))
    roce = ratios.get("ROCE %", ratios.get("Return on capital employed", "-"))
    pe = ratios.get("Stock P/E", ratios.get("P/E", "-"))
    entry = f"| [[{symbol.upper()}/thesis|{symbol.upper()}]] | {company_name} | {date} | {market_cap} | {roce} | {pe} | {verdict} |"

    # Find table end and append
    table_end = max((i for i, l in enumerate(lines) if l.startswith("|")), default=len(lines))
    lines.insert(table_end + 1, entry)

    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
