from fastapi.testclient import TestClient

from backend.main import app
from backend.routers import analysis as analysis_router
from backend.services.ticker_resolver import TickerResolution, TickerResolutionError

client = TestClient(app)


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
    assert response.json()["detail"] == "Price fetch failed: provider unavailable"
