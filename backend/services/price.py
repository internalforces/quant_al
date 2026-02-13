from __future__ import annotations

from typing import Optional

import numpy as np
import yfinance as yf


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    f = float(v)
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def get_stock_price(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}

    if not info or info.get("regularMarketPrice") is None:
        raise ValueError(f"No price data available for ticker {ticker}")

    current_price = _safe_float(info.get("regularMarketPrice"))
    previous_close = _safe_float(info.get("regularMarketPreviousClose"))
    open_price = _safe_float(info.get("regularMarketOpen"))
    day_high = _safe_float(info.get("regularMarketDayHigh"))
    day_low = _safe_float(info.get("regularMarketDayLow"))
    currency = info.get("currency", "USD")
    company = info.get("shortName") or info.get("longName") or ticker

    change = None
    change_percent = None
    if current_price is not None and previous_close is not None:
        change = round(current_price - previous_close, 4)
        change_percent = round(change / previous_close * 100, 4)

    return {
        "ticker": ticker,
        "company": company,
        "current_price": current_price,
        "previous_close": previous_close,
        "open": open_price,
        "day_high": day_high,
        "day_low": day_low,
        "change": _safe_float(change),
        "change_percent": _safe_float(change_percent),
        "currency": currency,
    }
