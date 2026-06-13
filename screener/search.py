"""Tavily web search — augments stock research with recent news and analysis."""

from tavily import TavilyClient


class StockSearcher:
    def __init__(self, api_key: str, max_results: int = 5):
        self.client = TavilyClient(api_key=api_key)
        self.max_results = max_results

    def search(self, query: str, company_name: str = "") -> str:
        """Search and return a formatted string of results for LLM context."""
        full_query = f"{company_name} {query}".strip() if company_name else query
        try:
            response = self.client.search(
                query=full_query,
                search_depth="basic",
                max_results=self.max_results,
                include_answer=True,
            )
        except Exception as e:
            return f"[Search unavailable: {e}]"

        parts = []
        if response.get("answer"):
            parts.append(f"Summary: {response['answer']}\n")

        for i, result in enumerate(response.get("results", []), 1):
            parts.append(f"[{i}] {result.get('title', '')}")
            parts.append(f"Source: {result.get('url', '')}")
            content = result.get("content", "")
            if content:
                parts.append(content[:500])
            parts.append("")

        return "\n".join(parts) if parts else "No results found."
