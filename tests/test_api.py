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
