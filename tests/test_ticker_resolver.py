import asyncio

from backend.services import ticker_resolver


def test_direct_us_ticker_does_not_load_krx_records(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("KRX lookup should not run for a direct US ticker")

    monkeypatch.setattr(ticker_resolver, "_krx_matches", fail_if_called)

    result = asyncio.run(ticker_resolver.resolve_ticker("AAPL"))

    assert result.ticker == "AAPL"
    assert result.exchange == "US"
