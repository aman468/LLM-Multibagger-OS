"""Interview session — user questions Claude about a stock, insights saved to Wiki."""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .wiki import save_financials, save_qa, save_thesis, update_index

console = Console()

SYSTEM_PROMPT = """You are a seasoned equity research analyst specialising in identifying 100-bagger stocks in the Indian market. You are deeply familiar with the framework from Christopher Mayer's book "100 Baggers":

The five characteristics of a 100-bagger candidate:
1. Catch them young — early-stage, undiscovered, or facing temporary fear
2. Profitable growth + high ROIC — twin engines, sustained competitive advantage (SCIND: Switching costs, Cost advantage, Intangibles, Network effect, Distribution)
3. Skin in the game — high promoter/owner-operator holding, aligned incentives
4. Quality management — disciplined capital allocation, consistent reinvestment at high rates
5. GARP — Growth at a Reasonable Price, margin of safety matters

You have been given detailed financial data about a specific company from Screener.in. Answer all questions using this data as your primary source. When the data is insufficient, draw on your knowledge of the company and industry. Be direct, specific, and honest about risks and weaknesses — do not be a cheerleader.

When citing numbers, always specify the time period (e.g., "FY24 ROCE of 23%"). Flag any red flags you notice even if not asked.

Company Data:
{company_data}

---

Recent web search context (if available):
{search_context}
"""

THESIS_PROMPT = """Based on the Q&A session below, write a structured investment thesis for {symbol} ({name}).

Use this exact structure:

# {symbol} — Investment Thesis
*Generated: {date}*

## One-Line Summary
[Single sentence capturing the core investment case]

## 100-Bagger Scorecard
| Criterion | Score (1-5) | Notes |
| --- | --- | --- |
| Catch them young | | |
| Profitable growth + ROIC | | |
| Skin in the game | | |
| Management quality | | |
| GARP (valuation) | | |
| **Overall** | **/25** | |

## Investment Case
[3-5 bullet points on why this could be a 100-bagger]

## Competitive Moat
[What sustains their ROIC? Which of SCIND applies?]

## Key Risks
[3-5 honest risk factors that could prevent the thesis from playing out]

## Verdict
**[BUY / WATCH / AVOID]** — [2-3 sentence reasoning]

## Key Metrics to Monitor
[What numbers to track quarterly to know if the thesis is intact]

---
Q&A Session:
{qa_text}
"""


def _format_company_data(data: dict) -> str:
    parts = [f"Company: {data.get('name', data.get('symbol', 'Unknown'))}"]
    parts.append(f"Symbol: {data.get('symbol', '')}")

    if data.get("about"):
        parts.append(f"\nBusiness Description:\n{data['about'][:800]}")

    if data.get("ratios"):
        parts.append("\nKey Ratios:")
        for k, v in data["ratios"].items():
            parts.append(f"  {k}: {v}")

    if data.get("shareholding"):
        parts.append("\nShareholding Pattern:")
        for k, v in data["shareholding"].items():
            parts.append(f"  {k}: {v}")

    if data.get("pros"):
        parts.append("\nScreener.in Pros:")
        for p in data["pros"]:
            parts.append(f"  + {p}")

    if data.get("cons"):
        parts.append("\nScreener.in Cons:")
        for c in data["cons"]:
            parts.append(f"  - {c}")

    for table_name in ["profit-loss", "balance-sheet", "cash-flow", "ratios"]:
        table = data.get("tables", {}).get(table_name)
        if table and table.get("rows"):
            parts.append(f"\n{table_name.replace('-', ' ').title()} (last 5 years):")
            headers = table.get("headers", [])
            recent_headers = headers[-5:] if len(headers) > 5 else headers
            for row_label, values in list(table["rows"].items())[:15]:
                if isinstance(values, dict):
                    recent_vals = {k: v for k, v in values.items() if k in recent_headers}
                    parts.append(f"  {row_label}: {json.dumps(recent_vals)}")
                elif isinstance(values, list):
                    parts.append(f"  {row_label}: {values[-5:]}")

    if data.get("peers"):
        parts.append("\nPeer Comparison (top 5):")
        for peer in data["peers"][:5]:
            parts.append(f"  {peer}")

    return "\n".join(parts)


def run_interview(
    symbol: str,
    company_data: dict,
    anthropic_client: anthropic.Anthropic,
    searcher,
    wiki_dir: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
):
    symbol = symbol.upper()
    name = company_data.get("name", symbol)

    console.print(Panel(
        f"[bold cyan]Research Session: {name} ({symbol})[/bold cyan]\n"
        f"[dim]Type your questions. Press [bold]Enter[/bold] on empty line or type [bold]done[/bold] to finish.[/dim]",
        expand=False,
    ))

    # Save financials snapshot
    fin_path = save_financials(wiki_dir, symbol, company_data)
    console.print(f"[dim]Financials saved → {fin_path}[/dim]\n")

    formatted_data = _format_company_data(company_data)
    conversation: list[dict] = []
    qa_pairs: list[dict] = []

    while True:
        try:
            question = Prompt.ask(f"\n[bold yellow]You[/bold yellow]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not question or question.lower() in ("done", "exit", "quit", "q"):
            break

        # Optionally augment with web search
        search_context = ""
        if searcher:
            with console.status("[dim]Searching web...[/dim]"):
                search_context = searcher.search(question, company_name=name)

        system = SYSTEM_PROMPT.format(
            company_data=formatted_data,
            search_context=search_context or "No additional search results.",
        )

        conversation.append({"role": "user", "content": question})

        console.print(f"\n[bold green]Claude[/bold green]")
        answer_parts: list[str] = []
        with anthropic_client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=conversation,
        ) as stream:
            for text in stream.text_stream:
                console.print(text, end="", markup=False, highlight=False)
                answer_parts.append(text)
        console.print()

        answer = "".join(answer_parts)
        conversation.append({"role": "assistant", "content": answer})
        qa_pairs.append({"question": question, "answer": answer})

    if not qa_pairs:
        console.print("[yellow]No questions asked — session not saved.[/yellow]")
        return

    # Save Q&A transcript
    qa_path = save_qa(wiki_dir, symbol, qa_pairs)
    console.print(f"\n[dim]Q&A saved → {qa_path}[/dim]")

    # Generate thesis
    console.print("\n[bold]Generating investment thesis...[/bold]")
    qa_text = "\n\n".join(f"Q: {p['question']}\nA: {p['answer']}" for p in qa_pairs)
    thesis_prompt = THESIS_PROMPT.format(
        symbol=symbol,
        name=name,
        date=datetime.now().strftime("%Y-%m-%d"),
        qa_text=qa_text,
    )

    with console.status("[dim]Writing thesis...[/dim]"):
        thesis_response = anthropic_client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": thesis_prompt}],
        )

    thesis = thesis_response.content[0].text
    thesis_path = save_thesis(wiki_dir, symbol, thesis)
    console.print(f"[dim]Thesis saved → {thesis_path}[/dim]")

    # Extract verdict for index
    verdict = "WATCH"
    for line in thesis.splitlines():
        if line.strip().startswith("**BUY"):
            verdict = "BUY"
            break
        elif line.strip().startswith("**AVOID"):
            verdict = "AVOID"
            break
        elif line.strip().startswith("**WATCH"):
            verdict = "WATCH"
            break

    update_index(wiki_dir, symbol, name, verdict, company_data.get("ratios", {}))
    console.print(f"\n[green]Session complete.[/green] Wiki updated with verdict: [bold]{verdict}[/bold]")
    console.print(Markdown(thesis))
