from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import yfinance as yf

from backend.services.strategy import BACK_YEARS, build_strategy_frame, evaluate_strategy


def get_company_name(ticker: str) -> str:
    try:
        t = yf.Ticker(ticker)
        info = getattr(t, "fast_info", None)
        if info and getattr(info, "shortName", None):
            return info.shortName
        info2 = t.info or {}
        return info2.get("shortName", ticker)
    except Exception:
        return ticker


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    f = float(v)
    if np.isnan(f) or np.isinf(f):
        return None
    return f


def _series_to_list(s: pd.Series) -> list:
    return [_safe_float(v) for v in s]


def analyze_ticker(ticker: str) -> dict:
    end = datetime.now()
    start = end - timedelta(days=BACK_YEARS * 365 + 7)

    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        raise ValueError(f"No data available for ticker {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if not {"Open", "Close"}.issubset(df.columns):
        raise ValueError(f"Required columns (Open/Close) missing for {ticker}")

    company = get_company_name(ticker)
    df = build_strategy_frame(df)
    mean_m, ann, sharpe = evaluate_strategy(df)

    latest_date = df.index[-1].strftime("%Y-%m-%d")
    last_sig = int(df["signal"].iloc[-1])
    last_pos = int(df["position"].iloc[-1])

    return {
        "ticker": ticker,
        "company": company,
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end": end.strftime("%Y-%m-%d"),
        "latest_date": latest_date,
        "last_signal": last_sig,
        "last_position": last_pos,
        "stats": {
            "monthly_return_pct": _safe_float(mean_m * 100),
            "annual_return_pct": _safe_float(ann * 100),
            "sharpe_ratio": _safe_float(sharpe),
            "cumulative_strategy": _safe_float(df["cumulative_strategy"].iloc[-1]),
            "cumulative_market": _safe_float(df["cumulative_market"].iloc[-1]),
        },
        "chart_data": {
            "dates": [d.strftime("%Y-%m-%d") for d in df.index],
            "close": _series_to_list(df["Close"]),
            "cumulative_strategy": _series_to_list(df["cumulative_strategy"]),
            "cumulative_market": _series_to_list(df["cumulative_market"]),
            "mb_pdf": _series_to_list(df["mb_pdf"]),
            "signal": [int(v) for v in df["signal"]],
        },
    }
