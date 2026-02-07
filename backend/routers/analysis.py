import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.models import AnalysisResponse, TickerSearchResponse
from backend.services.analysis import analyze_ticker
from backend.services.ticker_search import search_tickers

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/search", response_model=TickerSearchResponse)
async def search(q: str = Query(..., min_length=1)):
    try:
        results = await search_tickers(q)
        return TickerSearchResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


@router.get("/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze(ticker: str):
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, partial(analyze_ticker, ticker))
        return AnalysisResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
