from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class StrategyStats(BaseModel):
    monthly_return_pct: Optional[float]
    annual_return_pct: Optional[float]
    sharpe_ratio: Optional[float]
    cumulative_strategy: Optional[float]
    cumulative_market: Optional[float]


class ChartData(BaseModel):
    dates: List[str]
    close: List[Optional[float]]
    cumulative_strategy: List[Optional[float]]
    cumulative_market: List[Optional[float]]
    mb_pdf: List[Optional[float]]
    signal: List[int]


class AnalysisResponse(BaseModel):
    ticker: str
    company: str
    period_start: str
    period_end: str
    latest_date: str
    last_signal: int
    last_position: int
    stats: StrategyStats
    chart_data: ChartData


class TickerSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str
    type: str


class TickerSearchResponse(BaseModel):
    results: List[TickerSearchResult]


class TickerResolutionResult(BaseModel):
    query: str
    ticker: str
    name: str
    market: str
    exchange: str
    source: str


class TickerResolveResponse(BaseModel):
    result: TickerResolutionResult


class StockPriceResponse(BaseModel):
    ticker: str
    company: str
    current_price: Optional[float]
    previous_close: Optional[float]
    open: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    change: Optional[float]
    change_percent: Optional[float]
    currency: str


class ResolvedStockPriceResponse(BaseModel):
    resolution: TickerResolutionResult
    price: StockPriceResponse


class ResolvedAnalysisResponse(BaseModel):
    resolution: TickerResolutionResult
    analysis: AnalysisResponse
