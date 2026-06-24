from __future__ import annotations

import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from scipy.stats import maxwell
import yfinance as yf

ROLLING_WINDOW = 15
LOWER_Q = 0.20
UPPER_Q = 0.90
STOP_LOSS = -0.015
TAKE_PROFIT = 0.05
BACK_YEARS = 2


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


def evaluate_strategy(frame: pd.DataFrame):
    monthly = frame["strategy_return"].resample("ME").sum(min_count=1)
    mean_m = monthly.mean()
    ann = mean_m * 12
    std_m = monthly.std(ddof=1)
    sharpe = (
        (mean_m / std_m * math.sqrt(12))
        if std_m and not np.isnan(std_m) and std_m != 0
        else float("nan")
    )
    return mean_m, ann, sharpe


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

    df = df.copy()
    company = get_company_name(ticker)

    df["return"] = df["Close"].pct_change()
    df.dropna(subset=["return"], inplace=True)

    scale = df["return"].rolling(ROLLING_WINDOW).std()
    scale = scale.clip(lower=1e-8)
    df["mb_pdf"] = maxwell.pdf(np.abs(df["return"]), scale=scale)

    lower_thr = df["mb_pdf"].rolling(ROLLING_WINDOW).quantile(LOWER_Q)
    upper_thr = df["mb_pdf"].rolling(ROLLING_WINDOW).quantile(UPPER_Q)

    df["signal"] = 0
    buy_idx = df["mb_pdf"] < lower_thr
    sell_idx = df["mb_pdf"] > upper_thr
    df.loc[buy_idx, "signal"] = 1
    df.loc[sell_idx, "signal"] = -1

    df["position"] = df["signal"].replace(0, np.nan).ffill().fillna(0)

    df["current_open"] = df["Open"]
    df["next_open"] = df["Open"].shift(-1)
    df["raw_return"] = (df["next_open"] - df["current_open"]) / df["current_open"]

    active = df["position"] != 0
    strategy_ret = np.zeros(len(df))
    clipped = (
        df.loc[active, "raw_return"]
        .clip(lower=STOP_LOSS, upper=TAKE_PROFIT)
        .fillna(0)
    )
    strategy_ret[active.values] = clipped
    df["strategy_return"] = strategy_ret

    df["cumulative_strategy"] = (1 + df["strategy_return"]).cumprod()
    df["cumulative_market"] = (1 + df["return"]).cumprod()
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
