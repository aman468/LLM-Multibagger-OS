"""Screener.in authenticated client — login, screen, company data fetch."""

import re
import time
import requests
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

BASE_URL = "https://www.screener.in"
LOGIN_URL = f"{BASE_URL}/login/"
SCREEN_URL = f"{BASE_URL}/screen/raw/"


class ScreenerClient:
    def __init__(self, username: str, password: str, cookie_file: str = ".screener_session"):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": BASE_URL,
        })
        self._cookie_file = cookie_file
        if not self._restore_session():
            self._login(username, password)
            self._save_session()

    def _save_session(self):
        import pickle
        with open(self._cookie_file, "wb") as f:
            pickle.dump(self.session.cookies, f)

    def _restore_session(self) -> bool:
        """Try to restore a saved session. Returns True if the session is still valid."""
        import pickle, os
        if not os.path.exists(self._cookie_file):
            return False
        try:
            with open(self._cookie_file, "rb") as f:
                self.session.cookies.update(pickle.load(f))
            # Quick check — if we can reach the dashboard, session is still valid
            resp = self.session.get(f"{BASE_URL}/dash/", timeout=10, allow_redirects=False)
            if resp.status_code == 200:
                console.print("[green]Restored Screener.in session[/green]")
                return True
        except Exception:
            pass
        return False

    def _get_csrf(self, url: str) -> str:
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        token = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if not token:
            # Try cookie-based CSRF
            return self.session.cookies.get("csrftoken", "")
        return token["value"]

    def _login(self, username: str, password: str):
        csrf = self._get_csrf(LOGIN_URL)
        payload = {
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": csrf,
        }
        # Django CSRF requires Referer to match origin on HTTPS — must be the login page URL
        resp = self.session.post(
            LOGIN_URL,
            data=payload,
            timeout=15,
            headers={"Referer": LOGIN_URL},
        )
        if resp.status_code == 403:
            raise ValueError("Screener.in login returned 403 (CSRF failure) — check credentials in .env")
        if "logout" not in resp.text.lower() and resp.url == LOGIN_URL:
            raise ValueError("Screener.in login failed — check your credentials in .env")
        console.print("[green]Logged in to Screener.in[/green]")

    def run_screen(self, query: str, limit: int = 50, sort_by: str = "Market Capitalization") -> list[dict]:
        """Run a screen query and return list of company dicts with basic metrics."""
        params = {
            "sort": sort_by,
            "source": "",
            "query": query,
            "limit": limit,
        }
        resp = self.session.get(SCREEN_URL, params=params, timeout=30)
        resp.raise_for_status()
        return self._parse_screen_results(resp.text)

    def _parse_screen_results(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"class": lambda c: c and "data-table" in c})
        if not table:
            table = soup.find("table")
        if not table:
            return []

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            row = {}
            for i, td in enumerate(cells):
                key = headers[i] if i < len(headers) else f"col_{i}"
                # Extract symbol from the company link — it appears in the Name cell, not S.No.
                link = td.find("a", href=re.compile(r"/company/"))
                if link and "symbol" not in row:
                    href = link.get("href", "")
                    match = re.search(r"/company/([^/]+)/", href)
                    row["symbol"] = match.group(1) if match else ""
                row[key] = td.get_text(strip=True)
            rows.append(row)
        return rows

    def search_symbol(self, name: str) -> str:
        """Resolve a company name to its Screener.in URL slug (e.g. 'Dixon Technologies' → 'DIXON').

        Uses Screener.in's autocomplete API. Returns empty string if nothing found.
        """
        try:
            resp = self.session.get(
                f"{BASE_URL}/api/company/search/",
                params={"q": name, "fields": "symbol"},
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                url = results[0].get("url", "")
                m = re.search(r"/company/([^/]+)/", url)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return ""

    def get_company_brief(self, symbol: str) -> dict:
        """Lightweight fetch — returns promoter holding % and industry for a symbol.

        Uses the shared authenticated session. Called from threads — session is read-only here
        (no cookie mutation) so concurrent use is safe.
        """
        if not symbol:
            return {"symbol": symbol, "Promoter %": "-", "Industry": "-"}
        url = f"{BASE_URL}/company/{symbol}/"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception:
            return {"symbol": symbol, "Promoter %": "-", "Industry": "-"}

        soup = BeautifulSoup(resp.text, "lxml")
        result = {"symbol": symbol, "Promoter %": "-", "Industry": "-"}

        # Industry — Screener.in puts sector hierarchy inside p.sub next to .icon-industry.
        # First <a> = top-level sector (e.g. "Consumer Discretionary"), second = sub-sector.
        icon = soup.find(class_="icon-industry")
        if icon:
            p = icon.parent
            links = p.find_all("a")
            if len(links) >= 2:
                # Prefer sub-sector (index 1) as it's more specific
                result["Industry"] = links[1].get_text(strip=True)
            elif links:
                result["Industry"] = links[0].get_text(strip=True)

        # Promoter holding — from quarterly shareholding table inside #shareholding section.
        # Each data row is all <td>: first cell = label ("Promoters+"), rest = quarterly values.
        for tr in soup.select("#shareholding tr"):
            cells = tr.find_all("td")
            if cells and "promoter" in cells[0].get_text(strip=True).lower():
                # cells[1] = most recent quarter (Screener shows newest first after the label)
                recent = cells[1].get_text(strip=True) if len(cells) > 1 else "-"
                result["Promoter %"] = recent
                break

        return result

    def enrich_candidates(self, candidates: list[dict]) -> list[dict]:
        """Fetch promoter % and industry for each candidate sequentially.

        Sequential with a short delay avoids Screener.in rate limiting reliably.
        """
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

        briefs: dict[str, dict] = {}
        symbols_with_idx = [(i, c.get("symbol")) for i, c in enumerate(candidates) if c.get("symbol")]

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]Enriching candidates[/bold green]"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("[dim]{task.fields[name]}[/dim]"),
            transient=True,
        ) as progress:
            task = progress.add_task("enrich", total=len(symbols_with_idx), name="")
            for _, sym in symbols_with_idx:
                progress.update(task, name=sym)
                brief = self.get_company_brief(sym)
                briefs[sym] = brief
                progress.advance(task)
                time.sleep(0.4)

        enriched = []
        for c in candidates:
            sym = c.get("symbol", "")
            brief = briefs.get(sym, {})
            enriched.append({**c, "Promoter %": brief.get("Promoter %", "-"), "Industry": brief.get("Industry", "-")})
        return enriched

    def get_company_data(self, symbol: str) -> dict:
        """Fetch full company data from Screener.in for a given symbol."""
        url = f"{BASE_URL}/company/{symbol}/consolidated/"
        resp = self.session.get(url, timeout=20)
        # Fall back to standalone if consolidated not available
        if resp.status_code == 404:
            url = f"{BASE_URL}/company/{symbol}/"
            resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return self._parse_company_page(resp.text, symbol)

    def _parse_company_page(self, html: str, symbol: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        data = {"symbol": symbol}

        # Company name
        h1 = soup.find("h1", {"class": lambda c: c and "company-name" in c if c else False})
        if not h1:
            h1 = soup.find("h1")
        data["name"] = h1.get_text(strip=True) if h1 else symbol

        # Top ratios (market cap, PE, ROCE, etc.)
        data["ratios"] = {}
        for li in soup.select("#top-ratios li"):
            name_el = li.find("span", {"class": "name"})
            value_el = li.find("span", {"class": "number"})
            if name_el and value_el:
                data["ratios"][name_el.get_text(strip=True)] = value_el.get_text(strip=True)

        # About / description
        about = soup.find("div", {"class": lambda c: c and "company-profile" in c if c else False})
        if not about:
            about = soup.select_one(".about p") or soup.select_one("#about p")
        data["about"] = about.get_text(strip=True) if about else ""

        # Financial tables (P&L, Balance Sheet, Cash Flow, Ratios)
        data["tables"] = {}
        for section in soup.find_all("section", {"id": True}):
            section_id = section.get("id", "")
            table = section.find("table")
            if table:
                data["tables"][section_id] = self._parse_table(table)

        # Shareholding pattern
        data["shareholding"] = self._extract_shareholding(soup)

        # Peers
        data["peers"] = self._extract_peers(soup)

        # Pros and Cons (if present)
        data["pros"] = [li.get_text(strip=True) for li in soup.select(".pros li")]
        data["cons"] = [li.get_text(strip=True) for li in soup.select(".cons li")]

        return data

    def _parse_table(self, table) -> dict:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue
            row_label = cells[0].get_text(strip=True)
            values = [td.get_text(strip=True) for td in cells[1:]]
            rows[row_label] = dict(zip(headers[1:], values)) if len(headers) > 1 else values
        return {"headers": headers, "rows": rows}

    def _extract_shareholding(self, soup) -> dict:
        result = {}
        section = soup.find("section", {"id": "shareholding"})
        if not section:
            return result
        for tr in section.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[-1].get_text(strip=True)
                result[key] = val
        return result

    def _extract_peers(self, soup) -> list[dict]:
        peers = []
        section = soup.find("section", {"id": "peers"})
        if not section:
            return peers
        table = section.find("table")
        if not table:
            return peers
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        for tr in table.find("tbody").find_all("tr") if table.find("tbody") else []:
            cells = tr.find_all("td")
            if cells:
                peer = {headers[i]: cells[i].get_text(strip=True) for i in range(min(len(headers), len(cells)))}
                peers.append(peer)
        return peers[:10]
