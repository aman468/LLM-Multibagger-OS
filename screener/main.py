"""CLI entrypoint — `screen` and `interview` commands."""

import os
import sys
from pathlib import Path

import click
import anthropic
import yaml
from dotenv import load_dotenv
from rich.console import Console

# Load .env from project root (parent of screener/)
_root = Path(__file__).parent.parent
load_dotenv(_root / ".env")

from .scraper import ScreenerClient
from .screen import run_screen, load_config
from .interview import run_interview
from .search import StockSearcher
from .v3screen import run_v3_screen, display_v3_results
from .loader import load_csv, display_watchlist, find_symbol_col

console = Console()


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        console.print(f"[red]Missing environment variable: {key}[/red]")
        console.print(f"[dim]Copy .env.example → .env and fill in your credentials.[/dim]")
        sys.exit(1)
    return val


def _get_clients(config_path: str):
    username = _require_env("SCREENER_USERNAME")
    password = _require_env("SCREENER_PASSWORD")
    anthropic_key = _require_env("ANTHROPIC_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    config = load_config(config_path)
    search_cfg = config.get("search", {})

    screener = ScreenerClient(username, password)
    ai = anthropic.Anthropic(api_key=anthropic_key)
    searcher = StockSearcher(tavily_key, max_results=search_cfg.get("max_results", 5)) if tavily_key else None

    if not tavily_key:
        console.print("[yellow]TAVILY_API_KEY not set — web search disabled.[/yellow]")

    return screener, ai, searcher, config


@click.group()
def cli():
    """100-Bagger Stock Screener — find candidates, interview the AI, build your Wiki."""


@cli.command()
@click.option("--config", default=str(_root / "config.yaml"), help="Path to config.yaml")
def screen(config):
    """Screen Screener.in for 100-bagger candidates based on config filters."""
    screener, _, _, _ = _get_clients(config)
    run_screen(screener, config)


@cli.command()
@click.argument("symbol")
@click.option("--config", default=str(_root / "config.yaml"), help="Path to config.yaml")
def interview(symbol, config):
    """Start an interactive research session for SYMBOL (e.g. RELIANCE, DIXON)."""
    screener, ai_client, searcher, cfg = _get_clients(config)

    interview_cfg = cfg.get("interview", {})
    wiki_dir = str(_root / interview_cfg.get("wiki_dir", "Wiki"))
    model = interview_cfg.get("model", "claude-sonnet-4-6")
    max_tokens = interview_cfg.get("max_tokens", 2048)

    console.print(f"\n[bold]Fetching data for [cyan]{symbol.upper()}[/cyan] from Screener.in...[/bold]")
    with console.status("[dim]Loading company data...[/dim]"):
        try:
            company_data = screener.get_company_data(symbol)
        except Exception as e:
            console.print(f"[red]Could not fetch data for {symbol}: {e}[/red]")
            console.print("[dim]Check the symbol matches Screener.in's URL (e.g. DIXON, RELAXO)[/dim]")
            sys.exit(1)

    run_interview(
        symbol=symbol,
        company_data=company_data,
        anthropic_client=ai_client,
        searcher=searcher,
        wiki_dir=wiki_dir,
        model=model,
        max_tokens=max_tokens,
    )


@cli.command()
@click.option("--config", default=str(_root / "config.yaml"), help="Path to config.yaml")
@click.option("--top", default=10, show_default=True, help="Number of candidates to show")
def hunt(config, top):
    """V3.0 'Catch Them Young' screen + interview in one flow.

    Screens for small-cap 100-bagger candidates, ranks them by conviction score,
    then lets you pick any by number or symbol to interview immediately.
    """
    screener, ai_client, searcher, cfg = _get_clients(config)
    interview_cfg = cfg.get("interview", {})
    wiki_dir = str(_root / interview_cfg.get("wiki_dir", "Wiki"))
    model = interview_cfg.get("model", "claude-sonnet-4-6")
    max_tokens = interview_cfg.get("max_tokens", 2048)

    console.print("\n[bold green]Running Catch Them Young v3.0 screen...[/bold green]")
    scored = run_v3_screen(screener)

    if not scored:
        console.print("[yellow]No candidates found. Try relaxing v3.0 filters.[/yellow]")
        return

    display_v3_results(scored, top_n=top)

    # Build lookup tables: rank → symbol, symbol → symbol (case-insensitive)
    rank_to_sym = {str(i): row.get('symbol', '') for i, (_, row, _) in enumerate(scored[:top], 1)}
    sym_to_sym  = {row.get('symbol', '').upper(): row.get('symbol', '') for _, row, _ in scored[:top]}

    while True:
        try:
            raw = input("Interview (#/symbol, Enter to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            break

        # Resolve: number → symbol, or direct symbol
        sym = rank_to_sym.get(raw) or sym_to_sym.get(raw.upper()) or raw.upper()

        console.print(f"\n[bold]Fetching data for [cyan]{sym}[/cyan] from Screener.in...[/bold]")
        try:
            with console.status("[dim]Loading company data...[/dim]"):
                company_data = screener.get_company_data(sym)
        except Exception as e:
            console.print(f"[red]Could not fetch {sym}: {e}[/red]")
            console.print("[dim]Use the exact symbol shown in the table above.[/dim]")
            continue

        run_interview(
            symbol=sym,
            company_data=company_data,
            anthropic_client=ai_client,
            searcher=searcher,
            wiki_dir=wiki_dir,
            model=model,
            max_tokens=max_tokens,
        )

        # Re-show the shortlist after each interview so the user remembers their options
        display_v3_results(scored, top_n=top)


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--config", default=str(_root / "config.yaml"), help="Path to config.yaml")
def load(csv_file, config):
    """Research stocks from your own Screener.in CSV export.

    Export any screener from Screener.in → Download → CSV, then:

        multibagger load my_screener.csv
    """
    try:
        rows = load_csv(csv_file)
    except Exception as e:
        console.print(f"[red]Could not read CSV: {e}[/red]")
        return

    if not rows:
        console.print("[yellow]CSV is empty.[/yellow]")
        return

    display_watchlist(rows)

    headers = list(rows[0].keys())
    sym_col = find_symbol_col(headers)
    name_col = next((h for h in headers if "name" in h.lower()), headers[0])

    # Defer Screener.in login until the user actually picks a company
    screener: ScreenerClient | None = None

    cfg = load_config(config)
    interview_cfg = cfg.get("interview", {})
    wiki_dir = str(_root / interview_cfg.get("wiki_dir", "Wiki"))
    model = interview_cfg.get("model", "claude-sonnet-4-6")
    max_tokens = interview_cfg.get("max_tokens", 2048)
    tavily_key = os.getenv("TAVILY_API_KEY")
    searcher = StockSearcher(tavily_key, max_results=cfg.get("search", {}).get("max_results", 5)) if tavily_key else None

    while True:
        try:
            raw = input(f"Interview # (1–{len(rows)}, Enter to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            break

        # Resolve selection to a row
        selected_row: dict | None = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(rows):
                selected_row = rows[idx]
        if selected_row is None:
            console.print(f"[red]Invalid selection.[/red]")
            continue

        # Resolve symbol — prefer a dedicated column, else search by name
        if screener is None:
            console.print("\n[dim]Connecting to Screener.in...[/dim]")
            username = _require_env("SCREENER_USERNAME")
            password = _require_env("SCREENER_PASSWORD")
            screener = ScreenerClient(username, password)

        anthropic_key = _require_env("ANTHROPIC_API_KEY")
        ai_client = anthropic.Anthropic(api_key=anthropic_key)

        sym = ""
        if sym_col:
            sym = selected_row.get(sym_col, "").strip()

        if not sym:
            company_name = selected_row.get(name_col, "").strip()
            console.print(f"[dim]Resolving symbol for '{company_name}'...[/dim]")
            sym = screener.search_symbol(company_name)
            if not sym:
                console.print(f"[red]Could not resolve symbol for '{company_name}'. Try adding a Symbol/NSE Code column to your screener export.[/red]")
                continue

        console.print(f"\n[bold]Fetching full data for [cyan]{sym}[/cyan] from Screener.in...[/bold]")
        try:
            with console.status("[dim]Loading company data...[/dim]"):
                company_data = screener.get_company_data(sym)
        except Exception as e:
            console.print(f"[red]Could not fetch {sym}: {e}[/red]")
            continue

        run_interview(
            symbol=sym,
            company_data=company_data,
            anthropic_client=ai_client,
            searcher=searcher,
            wiki_dir=wiki_dir,
            model=model,
            max_tokens=max_tokens,
        )

        display_watchlist(rows)


if __name__ == "__main__":
    cli()
