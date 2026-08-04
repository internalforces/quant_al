import asyncio
import time

from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import analysis as analysis_router
from backend.services.ticker_resolver import TickerResolution, TickerResolutionError

client = TestClient(app)


def setup_function():
    analysis_router._rate_limiter.clear()
    analysis_router._price_cache.clear()
    analysis_router._analysis_cache.clear()


def _resolution(query: str) -> TickerResolution:
    return TickerResolution(
        query=query,
        ticker="AAPL",
        name="Apple Inc.",
        market="NASDAQ",
        exchange="NASDAQ",
        source="alias",
    )


def _analysis_result() -> dict:
    return {
        "ticker": "AAPL",
        "company": "Apple Inc.",
        "period_start": "2024-01-01",
        "period_end": "2026-01-01",
        "latest_date": "2026-01-01",
        "last_signal": 0,
        "last_position": 1,
        "stats": {
            "monthly_return_pct": 1.0,
            "annual_return_pct": 12.0,
            "sharpe_ratio": 1.2,
            "cumulative_strategy": 1.2,
            "cumulative_market": 1.1,
        },
        "chart_data": {
            "dates": ["2026-01-01"],
            "close": [100.0],
            "cumulative_strategy": [1.2],
            "cumulative_market": [1.1],
            "mb_pdf": [0.1],
            "signal": [0],
        },
    }


def test_signal_endpoint_returns_resolved_analysis(monkeypatch):
    async def resolve_ticker(query: str):
        return _resolution(query)

    monkeypatch.setattr(analysis_router, "resolve_ticker", resolve_ticker)
    monkeypatch.setattr(analysis_router, "analyze_ticker", lambda _ticker: _analysis_result())

    response = client.get("/api/signal", params={"q": "애플"})

    assert response.status_code == 200
    assert response.json()["resolution"]["ticker"] == "AAPL"
    assert response.json()["analysis"]["company"] == "Apple Inc."


def test_signal_endpoint_preserves_structured_resolution_errors(monkeypatch):
    async def resolve_ticker(_query: str):
        raise TickerResolutionError("여러 종목이 검색되었습니다.", [_resolution("애플")])

    monkeypatch.setattr(analysis_router, "resolve_ticker", resolve_ticker)

    response = client.get("/api/signal", params={"q": "애플"})

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "message": "여러 종목이 검색되었습니다.",
        "suggestions": [_resolution("애플").to_dict()],
    }


def test_price_endpoint_returns_bad_gateway_for_provider_failure(monkeypatch):
    async def resolve_ticker(query: str):
        return _resolution(query)

    def fetch_price(_ticker: str):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(analysis_router, "resolve_ticker", resolve_ticker)
    monkeypatch.setattr(analysis_router, "get_stock_price", fetch_price)

    response = client.get("/api/price", params={"q": "애플"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Price data provider is unavailable."


def test_price_endpoint_uses_short_lived_cache(monkeypatch):
    async def resolve_ticker(query: str):
        return _resolution(query)

    calls = 0

    def fetch_price(_ticker: str):
        nonlocal calls
        calls += 1
        return {
            "ticker": "AAPL",
            "company": "Apple Inc.",
            "current_price": 100.0,
            "previous_close": 99.0,
            "open": 99.5,
            "day_high": 101.0,
            "day_low": 98.0,
            "change": 1.0,
            "change_percent": 1.01,
            "currency": "USD",
        }

    monkeypatch.setattr(analysis_router, "resolve_ticker", resolve_ticker)
    monkeypatch.setattr(analysis_router, "get_stock_price", fetch_price)

    assert client.get("/api/price", params={"q": "애플"}).status_code == 200
    assert client.get("/api/price", params={"q": "애플"}).status_code == 200
    assert calls == 1


def test_price_endpoint_coalesces_concurrent_cache_misses(monkeypatch):
    calls = 0

    def fetch_price(_ticker: str):
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return {
            "ticker": "AAPL",
            "company": "Apple Inc.",
            "current_price": 100.0,
            "previous_close": 99.0,
            "open": 99.5,
            "day_high": 101.0,
            "day_low": 98.0,
            "change": 1.0,
            "change_percent": 1.01,
            "currency": "USD",
        }

    async def request_prices():
        return await asyncio.gather(
            *(analysis_router.price("AAPL") for _ in range(5))
        )

    monkeypatch.setattr(analysis_router, "get_stock_price", fetch_price)

    assert len(asyncio.run(request_prices())) == 5
    assert calls == 1


def test_cors_allows_only_configured_local_origin():
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_api_rate_limit_returns_retry_header():
    limiter = analysis_router._rate_limiter
    original_limit = limiter.requests_per_minute
    limiter.requests_per_minute = 1
    try:
        assert client.get("/api/health").status_code == 200
        limited = client.get("/api/health")
    finally:
        limiter.requests_per_minute = original_limit

    assert limited.status_code == 429
    assert limited.headers["retry-after"]


def test_rate_limit_uses_authenticated_telegram_chat_identity(monkeypatch):
    class RequestStub:
        headers = {
            "x-mb-quant-bot-token": "bot-api-secret",
            "x-mb-quant-telegram-chat-id": "-1001234567890",
        }

        class client:
            host = "127.0.0.1"

    monkeypatch.setenv("MB_QUANT_BOT_API_TOKEN", "bot-api-secret")

    assert analysis_router._client_id(RequestStub()) == "telegram:-1001234567890"


def test_rate_limit_ignores_untrusted_telegram_identity(monkeypatch):
    class RequestStub:
        headers = {
            "x-mb-quant-bot-token": "incorrect",
            "x-mb-quant-telegram-chat-id": "123456789",
        }

        class client:
            host = "127.0.0.1"

    monkeypatch.setenv("MB_QUANT_BOT_API_TOKEN", "bot-api-secret")

    assert analysis_router._client_id(RequestStub()) == "127.0.0.1"


def test_direct_endpoints_allow_yahoo_index_and_futures_symbols(monkeypatch):
    def fetch_price(ticker: str):
        return {
            "ticker": ticker,
            "company": "Gold Futures",
            "current_price": 100.0,
            "previous_close": 99.0,
            "open": 99.5,
            "day_high": 101.0,
            "day_low": 98.0,
            "change": 1.0,
            "change_percent": 1.01,
            "currency": "USD",
        }

    monkeypatch.setattr(analysis_router, "get_stock_price", fetch_price)
    monkeypatch.setattr(analysis_router, "analyze_ticker", lambda ticker: _analysis_result() | {"ticker": ticker})

    futures = client.get("/api/price/GC=F")
    index = client.get("/api/analyze/%5EGSPC")

    assert futures.status_code == 200
    assert futures.json()["ticker"] == "GC=F"
    assert index.status_code == 200
    assert index.json()["ticker"] == "^GSPC"


def test_async_rate_limit_dependency_serializes_concurrent_requests():
    class RequestStub:
        headers: dict[str, str] = {}

        class client:
            host = "test-client"

    limiter = analysis_router._rate_limiter
    original_limit = limiter.requests_per_minute
    limiter.requests_per_minute = 1

    async def enforce_once():
        try:
            await analysis_router._enforce_rate_limit(RequestStub())
            return 200
        except analysis_router.HTTPException as error:
            return error.status_code

    async def enforce_concurrently():
        return await asyncio.gather(*(enforce_once() for _ in range(5)))

    try:
        statuses = asyncio.run(enforce_concurrently())
    finally:
        limiter.requests_per_minute = original_limit

    assert statuses.count(200) == 1
    assert statuses.count(429) == 4


def test_rate_limiter_discards_inactive_client_state(monkeypatch):
    now = 0.0
    limiter = analysis_router._ClientRateLimiter(requests_per_minute=30)

    monkeypatch.setattr(analysis_router.time, "monotonic", lambda: now)
    assert limiter.retry_after("old-client") is None
    assert "old-client" in limiter._requests

    now = 60.0
    assert limiter.retry_after("active-client") is None

    assert "old-client" not in limiter._requests


def test_ttl_cache_discards_expired_keys_globally(monkeypatch):
    now = 0.0
    cache = analysis_router._TtlCache(ttl_seconds=60)

    monkeypatch.setattr(analysis_router.time, "monotonic", lambda: now)
    cache.set("old-key", {"value": "old"})
    assert "old-key" in cache._values

    now = 60.0
    assert cache.get("other-key") is None

    assert "old-key" not in cache._values
