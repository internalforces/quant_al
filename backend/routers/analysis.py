from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

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


class _ClientRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, deque[float]] = {}

    def retry_after(self, client_id: str) -> int | None:
        now = time.monotonic()
        requests = self._requests.setdefault(client_id, deque())
        while requests and now - requests[0] >= 60:
            requests.popleft()
        if len(requests) >= self.requests_per_minute:
            return max(1, int(60 - (now - requests[0])) + 1)
        requests.append(now)
        return None

    def clear(self) -> None:
        self._requests.clear()


class _TtlCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._values.get(key)
        if not value or value[0] <= time.monotonic():
            self._values.pop(key, None)
            return None
        return value[1]

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._values[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._values.clear()


def _positive_env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


_rate_limiter = _ClientRateLimiter(
    _positive_env_int("MB_QUANT_REQUESTS_PER_MINUTE", 30)
)
_price_cache = _TtlCache(ttl_seconds=60)
_analysis_cache = _TtlCache(ttl_seconds=900)


def _client_id(request: Request) -> str:
    if os.getenv("MB_QUANT_TRUST_PROXY_HEADERS", "").lower() == "true":
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            return forwarded_for.rsplit(",", maxsplit=1)[-1].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request) -> None:
    retry_after = _rate_limiter.retry_after(_client_id(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )


@router.get("/health", dependencies=[Depends(_enforce_rate_limit)])
async def health():
    return {"status": "ok"}


@router.get("/search", response_model=TickerSearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(_enforce_rate_limit),
):
    try:
        results = await search_ticker_candidates(q)
        return TickerSearchResponse(results=results)
    except Exception:
        raise HTTPException(status_code=502, detail="Search provider is unavailable.")


def _resolution_error_detail(error: TickerResolutionError) -> dict:
    return {
        "message": str(error),
        "suggestions": [item.to_dict() for item in error.suggestions],
    }


@router.get("/resolve", response_model=TickerResolveResponse)
async def resolve(
    q: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(_enforce_rate_limit),
):
    try:
        result = await resolve_ticker(q)
        return TickerResolveResponse(result=result.to_dict())
    except TickerResolutionError as error:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Ticker resolver is unavailable.")


@router.get("/price", response_model=ResolvedStockPriceResponse)
async def price_by_query(
    q: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(_enforce_rate_limit),
):
    loop = asyncio.get_running_loop()
    try:
        resolution = await resolve_ticker(q)
        result = _price_cache.get(resolution.ticker)
        if result is None:
            result = await loop.run_in_executor(
                None,
                partial(get_stock_price, resolution.ticker),
            )
            _price_cache.set(resolution.ticker, result)
        return ResolvedStockPriceResponse(
            resolution=resolution.to_dict(),
            price=StockPriceResponse(**result),
        )
    except TickerResolutionError as error:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Price data provider is unavailable.")


@router.get("/price/{ticker}", response_model=StockPriceResponse)
async def price(
    ticker: str = Path(..., min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.-]+$"),
    _: None = Depends(_enforce_rate_limit),
):
    loop = asyncio.get_running_loop()
    try:
        result = _price_cache.get(ticker)
        if result is None:
            result = await loop.run_in_executor(None, partial(get_stock_price, ticker))
            _price_cache.set(ticker, result)
        return StockPriceResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Price data provider is unavailable.")


@router.get("/signal", response_model=ResolvedAnalysisResponse)
async def signal_by_query(
    q: str = Query(..., min_length=1, max_length=64),
    _: None = Depends(_enforce_rate_limit),
):
    loop = asyncio.get_running_loop()
    try:
        resolution = await resolve_ticker(q)
        result = _analysis_cache.get(resolution.ticker)
        if result is None:
            result = await loop.run_in_executor(
                None,
                partial(analyze_ticker, resolution.ticker),
            )
            _analysis_cache.set(resolution.ticker, result)
        return ResolvedAnalysisResponse(
            resolution=resolution.to_dict(),
            analysis=AnalysisResponse(**result),
        )
    except TickerResolutionError as error:
        raise HTTPException(status_code=404, detail=_resolution_error_detail(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Analysis provider is unavailable.")


@router.get("/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze(
    ticker: str = Path(..., min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.-]+$"),
    _: None = Depends(_enforce_rate_limit),
):
    loop = asyncio.get_running_loop()
    try:
        result = _analysis_cache.get(ticker)
        if result is None:
            result = await loop.run_in_executor(None, partial(analyze_ticker, ticker))
            _analysis_cache.set(ticker, result)
        return AnalysisResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Analysis provider is unavailable.")
