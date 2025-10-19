"""
맥스웰-볼츠만(MB) 분포 기반 퀀트 신호 + 간단 백테스트
- 자산: AAPL (2년)
- 이상치 정의: 하위 20%(매수), 상위 10%(매도)
- 실행 시각: 매일 22:25 KST(미국 전일 종가 반영 가정)
- 포지션 유지형 + 손절/익절: -1.5%, +5%
- 결과/신호 이메일 발송

주의:
1) yfinance 데이터 시간대/지연이 있을 수 있음 → 실제 체결과 괴리 가능.
2) 본 코드는 교육/연구용 예제이며 투자 권유가 아닙니다.
"""
import os
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from scipy.stats import maxwell
import yfinance as yf
from dotenv import load_dotenv
from module.mail import send_email

# -----------------------------
# 설정값
# -----------------------------
"""
미국 주식 (예시: NASDAQ 대형주)
    1.	NVDA — NVIDIA Corporation  ￼
	2.	MSFT — Microsoft Corporation  ￼
	3.	AAPL — Apple Inc.  ￼
	4.	GOOGL / GOOG — Alphabet Inc.  ￼
	5.	AMZN — Amazon.com, Inc.  ￼
	6.	META (Facebook → Meta Platforms)
	7.	TSLA — Tesla, Inc.
	8.	BRK.B / BRK.A — Berkshire Hathaway
	9.	ORCL — Oracle
	10.	AVGO — Broadcom
	
국내 주식 (예시: KOSPI 대형주)
    1.	005930.KS — 삼성전자 (Samsung Electronics)
	2.	000660.KS — SK 하이닉스 (SK Hynix)
	3.	373220.KS — LG에너지솔루션 (LG Energy Solution)
	4.	005380.KS — 현대차 (Hyundai Motor)
	5.	207940.KS — 삼성바이오로직스 (Samsung Biologics)
	6.	000270.KS — 기아 (Kia Corp)
	7.	068270.KS — 셀트리온 (Celltrion)
	8.	051910.KS — LG화학 (LG Chem)
	9.	005490.KS — 포스코홀딩스 (POSCO Holdings)
	10.	035720.KQ — 카카오 (Kakao Corp)
"""
TICKERS = [
    "NVDA","AAPL","GOOGL","AMZN","TSLA",
    "005930.KS","000660.KS","005380.KS","000270.KS","035720.KQ"
][:10]  # 최대 10개
ROLLING_WINDOW = 15
LOWER_Q, UPPER_Q = 0.20, 0.90
STOP_LOSS, TAKE_PROFIT = -0.015, 0.05
BACK_YEARS = 2

# -----------------------------
# 환경 변수 로드 (.env)
# -----------------------------
load_dotenv()
SENDER = os.getenv("EMAIL_SENDER")
RECIPIENTS = [e.strip() for e in os.getenv("EMAIL_RECIPIENTS", "").split(',') if e.strip()]
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASSWORD")

# -----------------------------
# 유틸
# -----------------------------
def today_ymd():
    return datetime.now().strftime('%Y-%m-%d')

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

# -----------------------------
# 성과 지표 함수 (루프 이전)
# -----------------------------
def evaluate_strategy(frame: pd.DataFrame):
    monthly = frame['strategy_return'].resample('ME').sum(min_count=1)
    mean_m = monthly.mean()
    ann = mean_m * 12
    std_m = monthly.std(ddof=1)
    sharpe = (mean_m / std_m * math.sqrt(12)) if std_m and not np.isnan(std_m) and std_m != 0 else float('nan')
    return mean_m, ann, sharpe

# -----------------------------
# 멀티 티커 처리
# -----------------------------
parts = []
for TICKER in TICKERS:
    try:
        end = datetime.now()
        start = end - timedelta(days=BACK_YEARS * 365 + 7)
        df = yf.download(
            TICKER,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            auto_adjust=True,
            progress=False,
        )
        if df.empty:
            parts.append(f"티커 {TICKER}: 데이터 없음")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if not {'Open','Close'}.issubset(df.columns):
            parts.append(f"티커 {TICKER}: 필수 컬럼(Open/Close) 없음")
            continue

        df = df.copy()
        company = get_company_name(TICKER)

        # 수익률 계산
        df["return"] = df["Close"].pct_change()
        df.dropna(subset=["return"], inplace=True)

        # MB 분포 기반 시그널
        scale = df['return'].rolling(ROLLING_WINDOW).std()
        df['mb_pdf'] = maxwell.pdf(np.abs(df['return']), scale=scale)

        lower_thr = df['mb_pdf'].rolling(ROLLING_WINDOW).quantile(LOWER_Q)
        upper_thr = df['mb_pdf'].rolling(ROLLING_WINDOW).quantile(UPPER_Q)

        df['signal'] = 0
        buy_idx = df['mb_pdf'] < lower_thr
        sell_idx = df['mb_pdf'] > upper_thr
        df.loc[buy_idx, 'signal'] = 1
        df.loc[sell_idx, 'signal'] = -1

        # 포지션 유지
        df['position'] = df['signal'].replace(0, np.nan).ffill().fillna(0)

        # 전략 수익률(손절/익절)
        df['current_open'] = df['Open']
        df['next_open'] = df['Open'].shift(-1)
        df['raw_return'] = (df['next_open'] - df['current_open']) / df['current_open']

        active = df['position'] != 0
        strategy_ret = np.zeros(len(df))
        clipped = df.loc[active, 'raw_return'].clip(lower=STOP_LOSS, upper=TAKE_PROFIT)
        strategy_ret[active.values] = clipped
        df['strategy_return'] = strategy_ret

        # 누적 및 성과
        df['cumulative_strategy'] = (1 + df['strategy_return']).cumprod()
        df['cumulative_market'] = (1 + df['return']).cumprod()
        mean_m, ann, sharpe = evaluate_strategy(df)

        # 요약/본문
        latest_date = df.index[-1].strftime('%Y-%m-%d')
        last_sig = int(df['signal'].iloc[-1])
        last_pos = int(df['position'].iloc[-1])

        if last_sig == 1:
            today_msg = f"✅ {latest_date}: 급락(매수) 시그널 → 매수 관찰/분할매수 고려"
        elif last_sig == -1:
            today_msg = f"🚨 {latest_date}: 급등(매도) 시그널 → 차익 실현/분할매도 고려"
        elif last_pos == 1:
            today_msg = f"ℹ️  {latest_date}: 보유 포지션 유지"
        else:
            today_msg = f"ℹ️  {latest_date}: 시그널 없음(관망)"

        summary = (
            f"[MB 전략 성과]\n"
            f"월 수익률: {mean_m*100:.2f}%\n"
            f"연 수익률: {ann*100:.2f}%\n"
            f"샤프: {sharpe:.2f}\n\n"
            f"신호: {last_sig}, 포지션: {last_pos}\n"
            f"전략 누적: {df['cumulative_strategy'].iloc[-1]:.3f}, "
            f"시장 누적: {df['cumulative_market'].iloc[-1]:.3f}\n"
        )

        body_each = (
            f"티커: {TICKER} ({company})\n기간: {start.date()} ~ {end.date()}\n\n"
            + today_msg + "\n\n" + summary
        )
        parts.append(body_each)

    except Exception as e:
        parts.append(f"티커 {TICKER}: 처리 중 오류 - {e}")

# 통합 본문
body = "\n\n-----\n\n".join(parts) if parts else "생성된 내용이 없습니다."
print(body)

# -----------------------------
# 메일 발송
# -----------------------------
if SENDER and RECIPIENTS and SMTP_SERVER and SMTP_USER and SMTP_PASS:
    subject = f"[MB 퀀트] {today_ymd()} 통합 시그널 - {', '.join(TICKERS)}"
    for rcpt in RECIPIENTS:
        try:
            send_email(
                subject=subject, body=body, sender=SENDER, recipient=rcpt,
                smtp_server=SMTP_SERVER, smtp_port=SMTP_PORT,
                smtp_user=SMTP_USER, smtp_password=SMTP_PASS
            )
        except Exception as e:
            print(f"메일 전송 실패({rcpt}): {e}")
else:
    print("환경변수 미설정으로 메일 전송 생략")