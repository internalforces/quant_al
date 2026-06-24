import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query

from backend.schemas.models import (
    AnalysisResponse,
    ResolvedAnalysisResponse,
    ResolvedStockPriceResponse,
    StockPriceResponse,
    TickerResolveResponse,
    TickerSearchResponse,
)
from backend.services.analysis import analyze_ticker
from backend.services.price import get_stock_price
from backend.services.ticker_resolver import (
    TickerResolutionError,
    resolve_ticker,
    search_ticker_candidates,
)

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/search", response_model=TickerSearchResponse)
async def search(q: str = Query(..., min_length=1)):
    try:
        results = await search_ticker_candidates(q)
        return TickerSearchResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


def _resolution_error_detail(error: TickerResolutionError) -> dict:
    return {
        "message": str(error),
        "suggestions": [item.to_dict() for item in error.suggestions],
    }


@router.get("/resolve", response_model=TickerResolveResponse)
async def resolve(q: str = Query(..., min_length=1)):
    try:
        result = await resolve_ticker(q)
        return TickerResolveResponse(result=result.to_dict())
    except TickerResolutionError as e:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ticker resolve failed: {e}")


@router.get("/price", response_model=ResolvedStockPriceResponse)
async def price_by_query(q: str = Query(..., min_length=1)):
    loop = asyncio.get_running_loop()
    try:
        resolution = await resolve_ticker(q)
        result = await loop.run_in_executor(
            None,
            partial(get_stock_price, resolution.ticker),
        )
        return ResolvedStockPriceResponse(
            resolution=resolution.to_dict(),
            price=StockPriceResponse(**result),
        )
    except TickerResolutionError as e:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price fetch failed: {e}")


@router.get("/price/{ticker}", response_model=StockPriceResponse)
async def price(ticker: str):
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, partial(get_stock_price, ticker))
        return StockPriceResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Price fetch failed: {e}")


@router.get("/signal", response_model=ResolvedAnalysisResponse)
async def signal_by_query(q: str = Query(..., min_length=1)):
    loop = asyncio.get_running_loop()
    try:
        resolution = await resolve_ticker(q)
        result = await loop.run_in_executor(
            None,
            partial(analyze_ticker, resolution.ticker),
        )
        return ResolvedAnalysisResponse(
            resolution=resolution.to_dict(),
            analysis=AnalysisResponse(**result),
        )
    except TickerResolutionError as e:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal fetch failed: {e}")


@router.get("/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze(ticker: str):
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, partial(analyze_ticker, ticker))
        return AnalysisResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")
