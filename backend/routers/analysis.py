from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from functools import partial
from heapq import heappop, heappush
from typing import Any, Awaitable, Callable

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
        self._expiry: list[tuple[float, str]] = []

    def _remove_inactive_clients(self, now: float) -> None:
        while self._expiry and self._expiry[0][0] <= now:
            _, client_id = heappop(self._expiry)
            requests = self._requests.get(client_id)
            if requests is None:
                continue
            while requests and now - requests[0] >= 60:
                requests.popleft()
            if not requests:
                self._requests.pop(client_id, None)

    def retry_after(self, client_id: str) -> int | None:
        now = time.monotonic()
        self._remove_inactive_clients(now)
        requests = self._requests.setdefault(client_id, deque())
        while requests and now - requests[0] >= 60:
            requests.popleft()
        if len(requests) >= self.requests_per_minute:
            return max(1, int(60 - (now - requests[0])) + 1)
        requests.append(now)
        heappush(self._expiry, (now + 60, client_id))
        return None

    def clear(self) -> None:
        self._requests.clear()
        self._expiry.clear()


class _TtlCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, tuple[float, dict[str, Any]]] = {}
        self._expiry: list[tuple[float, str]] = []
        self._inflight: dict[str, asyncio.Task] = {}

    def _remove_expired_values(self, now: float) -> None:
        while self._expiry and self._expiry[0][0] <= now:
            _, key = heappop(self._expiry)
            value = self._values.get(key)
            if value is not None and value[0] <= now:
                self._values.pop(key, None)

    def get(self, key: str) -> dict[str, Any] | None:
        self._remove_expired_values(time.monotonic())
        value = self._values.get(key)
        if not value or value[0] <= time.monotonic():
            self._values.pop(key, None)
            return None
        return value[1]

    def set(self, key: str, value: dict[str, Any]) -> None:
        expires_at = time.monotonic() + self.ttl_seconds
        self._values[key] = (expires_at, value)
        heappush(self._expiry, (expires_at, key))

    async def get_or_load(
        self,
        key: str,
        loader: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        cached = self.get(key)
        if cached is not None:
            return cached

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._load_and_cache(key, loader))
            self._inflight[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done() and self._inflight.get(key) is task:
                self._inflight.pop(key, None)

    async def _load_and_cache(
        self,
        key: str,
        loader: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        value = await loader()
        self.set(key, value)
        return value

    def clear(self) -> None:
        self._values.clear()
        self._expiry.clear()
        self._inflight.clear()


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


async def _enforce_rate_limit(request: Request) -> None:
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
        result = await _price_cache.get_or_load(
            resolution.ticker,
            lambda: loop.run_in_executor(
                None,
                partial(get_stock_price, resolution.ticker),
            ),
        )
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
        result = await _price_cache.get_or_load(
            ticker,
            lambda: loop.run_in_executor(None, partial(get_stock_price, ticker)),
        )
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
        result = await _analysis_cache.get_or_load(
            resolution.ticker,
            lambda: loop.run_in_executor(
                None,
                partial(analyze_ticker, resolution.ticker),
            ),
        )
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
        result = await _analysis_cache.get_or_load(
            ticker,
            lambda: loop.run_in_executor(None, partial(analyze_ticker, ticker)),
        )
        return AnalysisResponse(**result)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception:
        raise HTTPException(status_code=502, detail="Analysis provider is unavailable.")
