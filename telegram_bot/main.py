from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes

from telegram_bot.aliases import AliasEntry, AliasStore, VALID_MARKETS


API_BASE_URL = os.getenv("MB_QUANT_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
API_TIMEOUT_SECONDS = float(os.getenv("MB_QUANT_API_TIMEOUT", "90"))
ALIAS_DB_PATH = os.getenv("TELEGRAM_ALIAS_DB_PATH", "data/telegram_aliases.sqlite3")
ALLOWED_CHAT_IDS = {
    item.strip()
    for item in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if item.strip()
}
ALIAS_STORE = AliasStore(ALIAS_DB_PATH)


class MbQuantApiError(RuntimeError):
    pass


def _query_from_args(context: ContextTypes.DEFAULT_TYPE) -> str:
    return " ".join(context.args or []).strip()


def _chat_id(update: Update) -> Optional[str]:
    if not update.effective_chat:
        return None
    return str(update.effective_chat.id)


def _is_allowed(update: Update) -> bool:
    chat_id = _chat_id(update)
    return not ALLOWED_CHAT_IDS or (chat_id in ALLOWED_CHAT_IDS)


async def _guard_chat(update: Update) -> bool:
    if _is_allowed(update):
        return True
    if update.effective_message:
        await update.effective_message.reply_text("이 봇을 사용할 권한이 없습니다.")
    return False


def _normalize_market(value: str) -> Optional[str]:
    normalized = value.strip().casefold()
    if normalized in {"국장", "한국", "한국장", "국내", "kr", "krx", "kospi", "kosdaq"}:
        return "국장"
    if normalized in {"미장", "미국", "미국장", "해외", "us", "usa", "nasdaq", "nyse"}:
        return "미장"
    return None


def _is_kr_market_resolution(resolution: dict[str, Any]) -> bool:
    ticker = resolution.get("ticker", "")
    exchange = resolution.get("exchange", "")
    return exchange == "KRX" or ticker.endswith((".KS", ".KQ"))


def _validate_alias(alias: str) -> Optional[str]:
    if not alias.strip():
        return "별명을 입력해 주세요."
    if alias.startswith("/"):
        return "별명은 / 로 시작할 수 없습니다."
    if any(ch.isspace() for ch in alias):
        return "별명은 공백 없이 한 단어로 입력해 주세요."
    if len(alias) > 32:
        return "별명은 32자 이하로 입력해 주세요."
    return None


def _get_alias_entry(update: Update, alias: str) -> AliasEntry | None:
    chat_id = _chat_id(update)
    if not chat_id:
        return None
    return ALIAS_STORE.get(chat_id, alias)


def _apply_alias_resolution(payload: dict[str, Any], entry: AliasEntry) -> dict[str, Any]:
    resolution = payload.get("resolution", {})
    resolution.update(
        {
            "query": entry.alias,
            "ticker": entry.ticker,
            "name": entry.name,
            "market": entry.market,
            "exchange": entry.exchange,
            "source": "stored_alias",
        }
    )
    payload["resolution"] = resolution
    return payload


def _bot_api_headers(update: Update) -> dict[str, str]:
    chat_id = _chat_id(update)
    bot_api_token = os.getenv("MB_QUANT_BOT_API_TOKEN", "")
    if not chat_id or not bot_api_token:
        return {}
    return {
        "X-MB-Quant-Bot-Token": bot_api_token,
        "X-MB-Quant-Telegram-Chat-ID": chat_id,
    }


async def _api_get(
    path: str,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
        resp = await client.get(url, params=params, headers=headers)

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise MbQuantApiError(_format_api_error(detail))

    return resp.json()


def _format_api_error(detail: Any) -> str:
    if isinstance(detail, dict):
        message = detail.get("message") or "요청 처리에 실패했습니다."
        suggestions = detail.get("suggestions") or []
        if suggestions:
            lines = [message, "", "검색 후보:"]
            for item in suggestions[:5]:
                lines.append(
                    f"- {item.get('name', '-')}: {item.get('ticker', '-')}"
                )
            return "\n".join(lines)
        return message
    return str(detail or "요청 처리에 실패했습니다.")


def _fmt_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return f"{number:,.0f}"
    return f"{number:,.{digits}f}".rstrip("0").rstrip(".")


def _fmt_price(value: Any, currency: str) -> str:
    digits = 0 if currency == "KRW" else 2
    return _fmt_number(value, digits=digits)


def _fmt_change(change: Any, percent: Any) -> str:
    if change is None or percent is None:
        return "-"
    sign = "+" if float(change) > 0 else ""
    return f"{sign}{_fmt_number(change)} ({sign}{_fmt_number(percent)}%)"


def _has_hangul(value: str) -> bool:
    return any("가" <= char <= "힣" for char in value)


def _display_name(resolution: dict[str, Any]) -> str:
    query = resolution.get("query") or ""
    name = resolution.get("name") or ""
    ticker = resolution.get("ticker") or ""
    if resolution.get("source") == "stored_alias" and query and name and query != name:
        return f"{query} ({name})"
    if query and name and query != name and _has_hangul(query):
        return f"{query} ({name})"
    return name or query or ticker


def _format_price_response(payload: dict[str, Any]) -> str:
    resolution = payload["resolution"]
    price = payload["price"]
    currency = price.get("currency", "")

    return "\n".join(
        [
            f"{_display_name(resolution)} 현재 주가",
            f"{resolution['ticker']} | {resolution['market']}",
            "",
            f"현재가: {_fmt_price(price.get('current_price'), currency)} {currency}",
            f"전일대비: {_fmt_change(price.get('change'), price.get('change_percent'))}",
            f"전일종가: {_fmt_price(price.get('previous_close'), currency)} {currency}",
            f"시가: {_fmt_price(price.get('open'), currency)} {currency}",
            f"고가/저가: {_fmt_price(price.get('day_high'), currency)} / {_fmt_price(price.get('day_low'), currency)} {currency}",
        ]
    )


def _signal_label(last_signal: int, last_position: int) -> str:
    if last_signal == 1:
        return "급락 매수 관찰 신호"
    if last_signal == -1:
        return "급등 매도/차익실현 관찰 신호"
    if last_position == 1:
        return "보유 포지션 유지"
    if last_position == -1:
        return "매도 포지션 유지"
    return "관망"


def _format_signal_response(payload: dict[str, Any]) -> str:
    resolution = payload["resolution"]
    analysis = payload["analysis"]
    stats = analysis["stats"]
    label = _signal_label(
        int(analysis.get("last_signal", 0)),
        int(analysis.get("last_position", 0)),
    )

    return "\n".join(
        [
            f"{_display_name(resolution)} MB 퀀트 시그널",
            f"{resolution['ticker']} | 기준일 {analysis['latest_date']}",
            "",
            f"신호: {label}",
            f"월 수익률: {_fmt_number(stats.get('monthly_return_pct'))}%",
            f"연 수익률: {_fmt_number(stats.get('annual_return_pct'))}%",
            f"샤프: {_fmt_number(stats.get('sharpe_ratio'))}",
            f"전략 누적: {_fmt_number(stats.get('cumulative_strategy'), digits=3)}",
            f"시장 누적: {_fmt_number(stats.get('cumulative_market'), digits=3)}",
            "",
            "교육/연구용 정보이며 투자 권유가 아닙니다.",
        ]
    )


def _help_text() -> str:
    return "\n".join(
        [
            "MB Quant 봇 사용법",
            "",
            "조회",
            "/price 삼성전자",
            "/price AAPL",
            "/signal 삼성전자",
            "/signal 엔비디아",
            "",
            "별명 등록",
            "/add 국장 005930.KS 삼전",
            "/add 국장 028300.KQ HLB",
            "/add 미장 NVDA 엔비",
            "/add 미장 AAPL 애플",
            "",
            "별명 조회/삭제",
            "/list 국장",
            "/list 미장",
            "/price 삼전",
            "/signal 엔비",
            "/remove 삼전",
            "",
            "운영",
            "/whoami - 현재 chat_id 확인",
            "",
            "교육/연구용 정보이며 투자 권유가 아닙니다.",
        ]
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    if not update.effective_message:
        return

    await update.effective_message.reply_text(_help_text())


async def add_alias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat = update.effective_chat
    chat_id = _chat_id(update)
    if not message or not chat or not chat_id:
        return

    args = context.args or []
    if len(args) != 3:
        await message.reply_text("사용법: /add 국장 005930.KS 삼전")
        return

    market = _normalize_market(args[0])
    ticker_query = args[1].strip()
    alias = args[2].strip()
    if market not in VALID_MARKETS:
        await message.reply_text("시장 구분은 국장 또는 미장으로 입력해 주세요.")
        return

    alias_error = _validate_alias(alias)
    if alias_error:
        await message.reply_text(alias_error)
        return

    await chat.send_action(ChatAction.TYPING)
    try:
        resolution = (
            await _api_get(
                "/resolve", {"q": ticker_query}, _bot_api_headers(update)
            )
        )["result"]
    except Exception as e:
        await message.reply_text(f"티커 확인 실패: {e}")
        return

    is_kr = _is_kr_market_resolution(resolution)
    if market == "국장" and not is_kr:
        await message.reply_text("국장에는 KRX 종목만 추가할 수 있습니다.")
        return
    if market == "미장" and is_kr:
        await message.reply_text("미장에는 미국/해외 종목 티커를 입력해 주세요.")
        return

    entry = AliasEntry(
        chat_id=chat_id,
        market=market,
        alias=alias,
        ticker=resolution["ticker"],
        name=resolution["name"],
        exchange=resolution["exchange"],
    )
    ALIAS_STORE.upsert(entry)
    await message.reply_text(
        f"추가했습니다: [{market}] {alias} -> {entry.ticker} ({entry.name})"
    )


async def list_aliases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat_id = _chat_id(update)
    if not message or not chat_id:
        return

    args = context.args or []
    if len(args) != 1:
        await message.reply_text("사용법: /list 국장 또는 /list 미장")
        return

    market = _normalize_market(args[0])
    if market not in VALID_MARKETS:
        await message.reply_text("시장 구분은 국장 또는 미장으로 입력해 주세요.")
        return

    entries = ALIAS_STORE.list_by_market(chat_id, market)
    if not entries:
        await message.reply_text(f"추가된 {market} 별명이 없습니다.")
        return

    lines = [f"{market} 별명 목록"]
    for entry in entries:
        lines.append(f"- {entry.alias}: {entry.ticker} ({entry.name})")
    await message.reply_text("\n".join(lines))


async def remove_alias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat_id = _chat_id(update)
    if not message or not chat_id:
        return

    args = context.args or []
    if len(args) != 1:
        await message.reply_text("사용법: /remove 삼전")
        return

    removed = ALIAS_STORE.delete(chat_id, args[0])
    if not removed:
        await message.reply_text(f"'{args[0]}' 별명을 찾지 못했습니다.")
        return

    await message.reply_text(
        f"삭제했습니다: [{removed.market}] {removed.alias} -> {removed.ticker}"
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    if not update.effective_message:
        return

    chat_id = _chat_id(update)
    await update.effective_message.reply_text(f"chat_id: {chat_id}")


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    query = _query_from_args(context)
    if not query:
        await message.reply_text("사용법: /price 삼성전자 또는 /price 삼전")
        return

    alias_entry = _get_alias_entry(update, query)
    api_query = alias_entry.ticker if alias_entry else query

    await chat.send_action(ChatAction.TYPING)
    try:
        payload = await _api_get("/price", {"q": api_query}, _bot_api_headers(update))
        if alias_entry:
            payload = _apply_alias_resolution(payload, alias_entry)
        await message.reply_text(_format_price_response(payload))
    except Exception as e:
        await message.reply_text(f"주가 조회 실패: {e}")


async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    query = _query_from_args(context)
    if not query:
        await message.reply_text("사용법: /signal 삼성전자 또는 /signal 삼전")
        return

    alias_entry = _get_alias_entry(update, query)
    api_query = alias_entry.ticker if alias_entry else query

    await chat.send_action(ChatAction.TYPING)
    try:
        payload = await _api_get("/signal", {"q": api_query}, _bot_api_headers(update))
        if alias_entry:
            payload = _apply_alias_resolution(payload, alias_entry)
        await message.reply_text(_format_signal_response(payload))
    except Exception as e:
        await message.reply_text(f"시그널 조회 실패: {e}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 필요합니다.")
    if not os.getenv("MB_QUANT_BOT_API_TOKEN"):
        raise RuntimeError("MB_QUANT_BOT_API_TOKEN 환경변수가 필요합니다.")

    app = Application.builder().token(token).concurrent_updates(True).build()
    app.add_handler(CommandHandler(["start", "help"], help_command))
    app.add_handler(CommandHandler("add", add_alias))
    app.add_handler(CommandHandler("list", list_aliases))
    app.add_handler(CommandHandler("remove", remove_alias))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.run_polling()


if __name__ == "__main__":
    main()
