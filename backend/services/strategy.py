from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import maxwell

ROLLING_WINDOW = 15
LOWER_Q = 0.20
UPPER_Q = 0.90
STOP_LOSS = -0.015
TAKE_PROFIT = 0.05
BACK_YEARS = 2


def evaluate_strategy(frame: pd.DataFrame) -> tuple[float, float, float]:
    monthly = frame["strategy_return"].resample("ME").sum(min_count=1)
    mean_m = monthly.mean()
    annual_return = mean_m * 12
    std_m = monthly.std(ddof=1)
    sharpe = (
        (mean_m / std_m * math.sqrt(12))
        if std_m and not np.isnan(std_m) and std_m != 0
        else float("nan")
    )
    return mean_m, annual_return, sharpe


def apply_strategy_returns(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply end-of-day signals to the next tradable open-to-open return.

    A signal on date ``t`` uses that day's close, so it cannot affect the return
    from ``open[t]`` to ``open[t + 1]``. A negative position is a short position
    and therefore inverts the underlying return before risk limits are applied.
    """
    result = frame.copy()
    result["position"] = result["signal"].replace(0, np.nan).ffill().fillna(0)
    result["applied_position"] = result["position"].shift(1).fillna(0)
    result["current_open"] = result["Open"]
    result["next_open"] = result["Open"].shift(-1)
    result["raw_return"] = (
        result["next_open"] - result["current_open"]
    ) / result["current_open"]

    gross_return = result["applied_position"] * result["raw_return"]
    result["strategy_return"] = gross_return.clip(
        lower=STOP_LOSS,
        upper=TAKE_PROFIT,
    ).fillna(0)
    return result


def build_strategy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Create all signal, position, and return columns from OHLC input data."""
    if not {"Open", "Close"}.issubset(frame.columns):
        raise ValueError("Required columns (Open/Close) are missing")

    result = frame.copy()
    result["return"] = result["Close"].pct_change()
    result.dropna(subset=["return"], inplace=True)
    if result.empty:
        raise ValueError("Not enough price data to calculate returns")

    scale = result["return"].rolling(ROLLING_WINDOW).std().clip(lower=1e-8)
    result["mb_pdf"] = maxwell.pdf(np.abs(result["return"]), scale=scale)
    lower_threshold = result["mb_pdf"].rolling(ROLLING_WINDOW).quantile(LOWER_Q)
    upper_threshold = result["mb_pdf"].rolling(ROLLING_WINDOW).quantile(UPPER_Q)

    result["signal"] = 0
    result.loc[result["mb_pdf"] < lower_threshold, "signal"] = 1
    result.loc[result["mb_pdf"] > upper_threshold, "signal"] = -1
    result = apply_strategy_returns(result)
    result["cumulative_strategy"] = (1 + result["strategy_return"]).cumprod()
    result["cumulative_market"] = (1 + result["return"]).cumprod()
    return result
