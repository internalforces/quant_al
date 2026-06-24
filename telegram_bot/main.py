from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes


API_BASE_URL = os.getenv("MB_QUANT_API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
API_TIMEOUT_SECONDS = float(os.getenv("MB_QUANT_API_TIMEOUT", "90"))
ALLOWED_CHAT_IDS = {
    item.strip()
    for item in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
    if item.strip()
}


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


async def _api_get(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{API_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
        resp = await client.get(url, params=params)

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        "\n".join(
            [
                "MB Quant 봇",
                "",
                "/price 삼성전자",
                "/price AAPL",
                "/signal 삼성전자",
                "/signal 엔비디아",
            ]
        )
    )


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard_chat(update):
        return
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    query = _query_from_args(context)
    if not query:
        await message.reply_text("사용법: /price 삼성전자")
        return

    await chat.send_action(ChatAction.TYPING)
    try:
        payload = await _api_get("/price", {"q": query})
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
        await message.reply_text("사용법: /signal 삼성전자")
        return

    await chat.send_action(ChatAction.TYPING)
    try:
        payload = await _api_get("/signal", {"q": query})
        await message.reply_text(_format_signal_response(payload))
    except Exception as e:
        await message.reply_text(f"시그널 조회 실패: {e}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 필요합니다.")

    app = Application.builder().token(token).concurrent_updates(True).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("signal", signal))
    app.run_polling()


if __name__ == "__main__":
    main()
