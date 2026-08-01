import asyncio

import httpx
import pytest

from backend.services import ticker_resolver


def test_direct_us_ticker_does_not_load_krx_records(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("KRX lookup should not run for a direct US ticker")

    monkeypatch.setattr(ticker_resolver, "_krx_matches", fail_if_called)

    result = asyncio.run(ticker_resolver.resolve_ticker("AAPL"))

    assert result.ticker == "AAPL"
    assert result.exchange == "US"


def test_bare_kosdaq_code_uses_krx_market_suffix(monkeypatch):
    record = ticker_resolver._KrxRecord(
        code="028300",
        ticker="028300.KQ",
        name="HLB",
        market="KOSDAQ",
        exchange="KRX",
        compact_name="HLB",
    )
    monkeypatch.setattr(ticker_resolver, "_find_krx_by_code", lambda _code: record)

    result = asyncio.run(ticker_resolver.resolve_ticker("028300"))

    assert result.ticker == "028300.KQ"
    assert result.name == "HLB"


def test_suffixed_krx_code_uses_krx_metadata(monkeypatch):
    record = ticker_resolver._KrxRecord(
        code="005930",
        ticker="005930.KS",
        name="삼성전자",
        market="KOSPI",
        exchange="KRX",
        compact_name="삼성전자",
    )
    monkeypatch.setattr(ticker_resolver, "_find_krx_by_code", lambda _code: record)

    result = asyncio.run(ticker_resolver.resolve_ticker("005930.KS"))

    assert result.ticker == "005930.KS"
    assert result.name == "삼성전자"
    assert result.market == "KOSPI"


def test_krx_load_failure_is_not_cached(monkeypatch):
    attempts = 0

    def fail_request(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline")

    ticker_resolver._load_krx_records.cache_clear()
    monkeypatch.setattr(ticker_resolver.httpx, "get", fail_request)
    monkeypatch.setattr(ticker_resolver.time, "sleep", lambda _seconds: None)

    with pytest.raises(ticker_resolver.KrxDataUnavailable):
        ticker_resolver._load_krx_records()
    with pytest.raises(ticker_resolver.KrxDataUnavailable):
        ticker_resolver._load_krx_records()

    assert attempts == 4
