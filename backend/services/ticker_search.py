import asyncio

import httpx

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
SEARCH_TIMEOUT_SECONDS = 5.0
SEARCH_RETRY_DELAY_SECONDS = 0.2


async def search_tickers(query: str, max_results: int = 8) -> list[dict]:
    params = {
        "q": query,
        "quotesCount": max_results,
        "newsCount": 0,
        "listsCount": 0,
        "enableFuzzyQuery": False,
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    last_error: httpx.HTTPError | None = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT_SECONDS) as client:
                resp = await client.get(SEARCH_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            break
        except httpx.HTTPError as error:
            last_error = error
            if attempt == 0:
                await asyncio.sleep(SEARCH_RETRY_DELAY_SECONDS)
    else:
        raise RuntimeError("Yahoo 종목 검색을 완료하지 못했습니다.") from last_error

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
