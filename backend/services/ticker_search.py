import httpx

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"


async def search_tickers(query: str, max_results: int = 8) -> list[dict]:
    params = {
        "q": query,
        "quotesCount": max_results,
        "newsCount": 0,
        "listsCount": 0,
        "enableFuzzyQuery": False,
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(SEARCH_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for q in data.get("quotes", []):
        results.append(
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            }
        )
    return results
