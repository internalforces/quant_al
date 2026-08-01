from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from functools import lru_cache
from io import BytesIO
import re
import time
from typing import Iterable, Optional

import httpx
import pandas as pd

from backend.services.ticker_search import search_tickers

KRX_CORP_LIST_URL = (
    "https://kind.krx.co.kr/corpgeneral/corpList.do"
    "?method=download&searchType=13"
)
KRX_TIMEOUT_SECONDS = 5.0
KRX_RETRY_DELAY_SECONDS = 0.2


class KrxDataUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class TickerResolution:
    query: str
    ticker: str
    name: str
    market: str
    exchange: str
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


class TickerResolutionError(ValueError):
    def __init__(
        self,
        message: str,
        suggestions: Optional[list[TickerResolution]] = None,
    ):
        super().__init__(message)
        self.suggestions = suggestions or []


@dataclass(frozen=True)
class _KrxRecord:
    code: str
    ticker: str
    name: str
    market: str
    exchange: str
    compact_name: str

    def to_resolution(self, query: str, source: str) -> TickerResolution:
        return TickerResolution(
            query=query,
            ticker=self.ticker,
            name=self.name,
            market=self.market,
            exchange=self.exchange,
            source=source,
        )


_ALIASES = {
    # Korea
    "삼성전자": ("005930.KS", "삼성전자", "KOSPI", "KRX"),
    "삼전": ("005930.KS", "삼성전자", "KOSPI", "KRX"),
    "SK하이닉스": ("000660.KS", "SK하이닉스", "KOSPI", "KRX"),
    "하이닉스": ("000660.KS", "SK하이닉스", "KOSPI", "KRX"),
    "LG에너지솔루션": ("373220.KS", "LG에너지솔루션", "KOSPI", "KRX"),
    "엘지에너지솔루션": ("373220.KS", "LG에너지솔루션", "KOSPI", "KRX"),
    "현대차": ("005380.KS", "현대차", "KOSPI", "KRX"),
    "현대자동차": ("005380.KS", "현대차", "KOSPI", "KRX"),
    "기아": ("000270.KS", "기아", "KOSPI", "KRX"),
    "포스코홀딩스": ("005490.KS", "POSCO홀딩스", "KOSPI", "KRX"),
    "포스코": ("005490.KS", "POSCO홀딩스", "KOSPI", "KRX"),
    "카카오": ("035720.KS", "카카오", "KOSPI", "KRX"),
    "네이버": ("035420.KS", "NAVER", "KOSPI", "KRX"),
    "NAVER": ("035420.KS", "NAVER", "KOSPI", "KRX"),
    "셀트리온": ("068270.KS", "셀트리온", "KOSPI", "KRX"),
    "LG화학": ("051910.KS", "LG화학", "KOSPI", "KRX"),
    "엘지화학": ("051910.KS", "LG화학", "KOSPI", "KRX"),
    # US
    "애플": ("AAPL", "Apple Inc.", "NASDAQ", "NASDAQ"),
    "APPLE": ("AAPL", "Apple Inc.", "NASDAQ", "NASDAQ"),
    "엔비디아": ("NVDA", "NVIDIA Corporation", "NASDAQ", "NASDAQ"),
    "NVIDIA": ("NVDA", "NVIDIA Corporation", "NASDAQ", "NASDAQ"),
    "마이크로소프트": ("MSFT", "Microsoft Corporation", "NASDAQ", "NASDAQ"),
    "MICROSOFT": ("MSFT", "Microsoft Corporation", "NASDAQ", "NASDAQ"),
    "구글": ("GOOGL", "Alphabet Inc.", "NASDAQ", "NASDAQ"),
    "알파벳": ("GOOGL", "Alphabet Inc.", "NASDAQ", "NASDAQ"),
    "GOOGLE": ("GOOGL", "Alphabet Inc.", "NASDAQ", "NASDAQ"),
    "아마존": ("AMZN", "Amazon.com, Inc.", "NASDAQ", "NASDAQ"),
    "AMAZON": ("AMZN", "Amazon.com, Inc.", "NASDAQ", "NASDAQ"),
    "테슬라": ("TSLA", "Tesla, Inc.", "NASDAQ", "NASDAQ"),
    "TESLA": ("TSLA", "Tesla, Inc.", "NASDAQ", "NASDAQ"),
    "메타": ("META", "Meta Platforms, Inc.", "NASDAQ", "NASDAQ"),
    "페이스북": ("META", "Meta Platforms, Inc.", "NASDAQ", "NASDAQ"),
    "넷플릭스": ("NFLX", "Netflix, Inc.", "NASDAQ", "NASDAQ"),
    "브로드컴": ("AVGO", "Broadcom Inc.", "NASDAQ", "NASDAQ"),
    "오라클": ("ORCL", "Oracle Corporation", "NYSE", "NYSE"),
}

_COMPACT_ALIAS_MAP = {
    re.sub(r"[\s._\-\(\)]+", "", key).upper(): value
    for key, value in _ALIASES.items()
}


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


def _compact(value: str) -> str:
    compacted = value.strip().upper()
    for token in ("주식회사", "(주)", "㈜", " ", "\t", "\n", ".", "-", "_"):
        compacted = compacted.replace(token, "")
    return compacted


def _contains_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value))


def _alias_resolution(query: str) -> Optional[TickerResolution]:
    alias = _COMPACT_ALIAS_MAP.get(_compact(query))
    if not alias:
        return None
    ticker, name, market, exchange = alias
    return TickerResolution(
        query=query,
        ticker=ticker,
        name=name,
        market=market,
        exchange=exchange,
        source="alias",
    )


def _market_suffix(market_name: str) -> Optional[str]:
    if market_name in {"유가", "코스피", "KOSPI"}:
        return "KS"
    if market_name in {"코스닥", "KOSDAQ"}:
        return "KQ"
    return None


def _market_label(market_name: str) -> str:
    if market_name in {"유가", "코스피", "KOSPI"}:
        return "KOSPI"
    if market_name in {"코스닥", "KOSDAQ"}:
        return "KOSDAQ"
    if market_name in {"코넥스", "KONEX"}:
        return "KONEX"
    return market_name or "KRX"


@lru_cache(maxsize=1)
def _load_krx_records() -> tuple[_KrxRecord, ...]:
    headers = {"User-Agent": "Mozilla/5.0"}
    last_error: Exception | None = None
    frames = []
    for attempt in range(2):
        try:
            resp = httpx.get(
                KRX_CORP_LIST_URL,
                headers=headers,
                timeout=KRX_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            frames = pd.read_html(BytesIO(resp.content), header=0, encoding="euc-kr")
            break
        except (httpx.HTTPError, ValueError, OSError) as error:
            last_error = error
            if attempt == 0:
                time.sleep(KRX_RETRY_DELAY_SECONDS)

    if not frames:
        raise KrxDataUnavailable("KRX 종목 목록을 불러오지 못했습니다.") from last_error

    df = frames[0]
    records: list[_KrxRecord] = []
    for _, row in df.iterrows():
        name = str(row.get("회사명", "")).strip()
        code = str(row.get("종목코드", "")).strip().zfill(6)
        market_name = str(row.get("시장구분", "")).strip()
        suffix = _market_suffix(market_name)
        if not name or not re.fullmatch(r"\d{6}", code) or not suffix:
            continue

        market = _market_label(market_name)
        records.append(
            _KrxRecord(
                code=code,
                ticker=f"{code}.{suffix}",
                name=name,
                market=market,
                exchange="KRX",
                compact_name=_compact(name),
            )
        )
    return tuple(records)


def _krx_matches(query: str, max_results: int = 8) -> list[_KrxRecord]:
    compacted = _compact(query)
    if not compacted:
        return []

    try:
        records = list(_load_krx_records())
    except KrxDataUnavailable:
        return []
    exact = [r for r in records if r.compact_name == compacted]
    if exact:
        return exact[:max_results]

    starts = [r for r in records if r.compact_name.startswith(compacted)]
    if starts:
        return sorted(starts, key=lambda r: (len(r.name), r.name))[:max_results]

    contains = [r for r in records if compacted in r.compact_name]
    return sorted(contains, key=lambda r: (len(r.name), r.name))[:max_results]


def _find_krx_by_code(code: str) -> Optional[_KrxRecord]:
    normalized = code[:6]
    try:
        records = _load_krx_records()
    except KrxDataUnavailable:
        return None
    return next((record for record in records if record.code == normalized), None)


def _bare_krx_code(query: str) -> Optional[str]:
    match = re.fullmatch(r"(\d{6})", query.strip())
    return match.group(1) if match else None


async def _resolve_direct_krx_code(
    query: str,
    fallback: TickerResolution,
) -> TickerResolution:
    """Use the KRX list for bare codes without blocking the event loop."""
    code = _bare_krx_code(query)
    if not code:
        return fallback
    record = await asyncio.to_thread(_find_krx_by_code, code)
    return record.to_resolution(query=query, source="direct") if record else fallback


def _direct_symbol_resolution(query: str) -> Optional[TickerResolution]:
    raw = query.strip()
    upper = query.upper()
    krx_match = re.fullmatch(r"(\d{6})(?:\.(KS|KQ))?", upper)
    if krx_match:
        suffix = krx_match.group(2) or "KS"
        return TickerResolution(
            query=query,
            ticker=f"{krx_match.group(1)}.{suffix}",
            name=f"{krx_match.group(1)}.{suffix}",
            market="KRX",
            exchange="KRX",
            source="direct",
        )

    is_ticker_like = (
        raw == upper
        or any(ch in raw for ch in (".", "-"))
        or any(ch.isdigit() for ch in raw)
    )
    if not is_ticker_like:
        return None

    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", upper):
        return TickerResolution(
            query=query,
            ticker=upper,
            name=upper,
            market="US",
            exchange="US",
            source="direct",
        )
    return None


def _dedupe_resolutions(items: Iterable[TickerResolution]) -> list[TickerResolution]:
    seen = set()
    deduped = []
    for item in items:
        if item.ticker in seen:
            continue
        seen.add(item.ticker)
        deduped.append(item)
    return deduped


async def search_ticker_candidates(query: str, max_results: int = 8) -> list[dict]:
    normalized = _normalize_query(query)
    if not normalized:
        return []

    candidates: list[TickerResolution] = []
    alias = _alias_resolution(normalized)
    if alias:
        candidates.append(alias)

    direct = _direct_symbol_resolution(normalized)
    if direct and direct.exchange != "KRX":
        candidates.append(direct)
    else:
        if direct:
            candidates.append(await _resolve_direct_krx_code(normalized, direct))
        else:
            candidates.extend(
                record.to_resolution(query=normalized, source="krx")
                for record in await asyncio.to_thread(
                    _krx_matches,
                    normalized,
                    max_results,
                )
            )

    if len(candidates) < max_results and not _contains_hangul(normalized):
        try:
            yahoo_results = await search_tickers(
                normalized,
                max_results=max_results - len(candidates),
            )
        except Exception:
            yahoo_results = []
        for result in yahoo_results:
            symbol = result.get("symbol") or ""
            name = result.get("name") or symbol
            exchange = result.get("exchange") or ""
            quote_type = result.get("type") or ""
            if not symbol or quote_type not in {"EQUITY", "ETF"}:
                continue
            candidates.append(
                TickerResolution(
                    query=normalized,
                    ticker=symbol,
                    name=name,
                    market=exchange or "US",
                    exchange=exchange or "US",
                    source="yahoo",
                )
            )

    return [
        {
            "symbol": item.ticker,
            "name": item.name,
            "exchange": item.exchange,
            "type": "EQUITY",
        }
        for item in _dedupe_resolutions(candidates)[:max_results]
    ]


async def resolve_ticker(query: str) -> TickerResolution:
    normalized = _normalize_query(query)
    if not normalized:
        raise TickerResolutionError("종목명 또는 티커를 입력해 주세요.")

    alias = _alias_resolution(normalized)
    if alias:
        return alias

    direct = _direct_symbol_resolution(normalized)
    if direct and direct.exchange != "KRX":
        return direct
    if direct:
        return await _resolve_direct_krx_code(normalized, direct)

    krx_matches = [
        record.to_resolution(query=normalized, source="krx")
        for record in await asyncio.to_thread(_krx_matches, normalized)
    ]
    exact_krx = [
        item for item in krx_matches if _compact(item.name) == _compact(normalized)
    ]
    if len(exact_krx) == 1:
        return exact_krx[0]
    if len(krx_matches) == 1:
        return krx_matches[0]
    if len(krx_matches) > 1:
        raise TickerResolutionError(
            "여러 종목이 검색되었습니다. 더 정확한 회사명을 입력해 주세요.",
            suggestions=krx_matches[:5],
        )

    if direct:
        return direct

    if not _contains_hangul(normalized):
        candidates = await search_ticker_candidates(normalized, max_results=5)
        if candidates:
            first = candidates[0]
            return TickerResolution(
                query=normalized,
                ticker=first["symbol"],
                name=first["name"],
                market=first["exchange"] or "US",
                exchange=first["exchange"] or "US",
                source="yahoo",
            )

    raise TickerResolutionError(f"'{normalized}'에 해당하는 종목을 찾지 못했습니다.")
