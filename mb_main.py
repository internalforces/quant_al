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
TICKER = "AAPL"               # 분석할 티커
ROLLING_WINDOW = 15                 # MB스케일(표준편차) 산출 구간
LOWER_Q = 0.20                      # 하위 20% → 매수 시그널
UPPER_Q = 0.90                      # 상위 10% → 매도 시그널
STOP_LOSS = -0.015                  # -1.5% 손절
TAKE_PROFIT = 0.05                  # +5% 익절
BACK_YEARS = 2                      # 2년 백데스트

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
    # .info는 느리거나 Deprecated 경고가 있을 수 있어 예외 처리
    try:
        t = yf.Ticker(ticker)
        info = getattr(t, "fast_info", None)
        if info and getattr(info, "shortName", None):
            return info.shortName
        # fallback
        info2 = t.info or {}
        return info2.get("shortName", ticker)
    except Exception:
        return ticker


# -----------------------------
# 데이터 로드
# -----------------------------
end = datetime.now()
start = end - timedelta(days=BACK_YEARS * 365 + 7)  # 여유 일수 포함

df = yf.download(TICKER, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), auto_adjust=True)
if df.empty:
    raise SystemExit("yfinance 다운로드 실패 또는 데이터 없음")

company = get_company_name(TICKER)

# 수익률 계산
df["return"] = df["Close"].pct_change()
df.dropna(inplace=True)

# -----------------------------
# MB 분포 기반 시그널
# -----------------------------
# scale(=표준편차) 추정: 최근 ROLLING_WINDOW의 수익률 표준편차
scale = df['return'].rolling(ROLLING_WINDOW).std()
# MB pdf는 |r|에 대해 계산
mb_pdf = maxwell.pdf(np.abs(df['return']), scale=scale)
df['mb_pdf'] = mb_pdf

# 롤링 구간에서의 분위수 경계선 (하위 20%, 상위 90%)
lower_thr = df['mb_pdf'].rolling(ROLLING_WINDOW).quantile(LOWER_Q)
upper_thr = df['mb_pdf'].rolling(ROLLING_WINDOW).quantile(UPPER_Q)

# 시그널: 낮은 pdf(=드문 큰 움직임) → 매수, 높은 pdf → 매도
# (설계에 따라 반대로 정의 가능하나, 제공 예제 로직을 준수)
df['signal'] = 0
# 매수: 급락 등 비정상 큰 움직임 가정 → pdf < 하위 경계
buy_idx = df['mb_pdf'] < lower_thr
sell_idx = df['mb_pdf'] > upper_thr

df.loc[buy_idx, 'signal'] = 1
df.loc[sell_idx, 'signal'] = -1

# 포지션 유지(직전 신호 유지)
df['position'] = df['signal'].replace(to_replace=0, method='ffill').fillna(0)

# -----------------------------
# 전략 수익률(시가 기준, 다음날 오픈으로 전개) + 손절/익절
# -----------------------------
df['current_open'] = df['Open']
df['next_open']    = df['Open'].shift(-1)
df['raw_return']   = (df['next_open'] - df['current_open']) / df['current_open']

active = df['position'] != 0

# 포지션 있는 날에만 손절/익절 클립 적용
strategy_ret = np.zeros(len(df))
clipped = df.loc[active, 'raw_return'].clip(lower=STOP_LOSS, upper=TAKE_PROFIT)
strategy_ret[active.values] = clipped

df['strategy_return'] = strategy_ret

# 누적
df['cumulative_strategy'] = (1 + df['strategy_return']).cumprod()
df['cumulative_market']   = (1 + df['return']).cumprod()

# -----------------------------
# 성과 지표 (월/연 수익률, 샤프)
# -----------------------------
def evaluate_strategy(frame: pd.DataFrame):
    # 거래일 데이터 → 월말 리샘플: 수익률 합산 근사 (추정치)
    monthly = frame['strategy_return'].resample('ME').sum(min_count=1)
    mean_m = monthly.mean()
    ann = mean_m * 12
    std_m = monthly.std(ddof=1)
    sharpe = (mean_m / std_m * math.sqrt(12)) if std_m and not np.isnan(std_m) and std_m != 0 else float('nan')
    return mean_m, ann, sharpe

mean_m, ann, sharpe = evaluate_strategy(df)

# -----------------------------
# 오늘(가장 최근 완료 캔들) 시그널 요약 및 메일 본문
# -----------------------------
latest_date = df.index[-1].strftime('%Y-%m-%d')
last_sig = int(df['signal'].iloc[-1])
last_pos = int(df['position'].iloc[-1])
last_raw = float(df['raw_return'].iloc[-2]) if len(df) > 1 else 0.0  # 직전일 수익률 참고

if last_sig == 1:
    today_msg = f"✅ {latest_date}: 급락(매수) 시그널 → 매수 관찰/분할매수 고려"
elif last_sig == -1:
    today_msg = f"🚨 {latest_date}: 급등(매도) 시그널 → 차익 실현/분할매도 고려"
elif last_pos == 1:
    today_msg = f"ℹ️  {latest_date}: 보유 포지션 유지"
else:
    today_msg = f"ℹ️  {latest_date}: 시그널 없음(관망)"

summary = (
    f"[MB 전략 성과]\n"                     # 헤더 출력
    f"월 수익률: {mean_m*100:.2f}%\n"        # 평균 월 수익률(% 단위)
    f"연 수익률: {ann*100:.2f}%\n"           # 연 환산 수익률
    f"샤프: {sharpe:.2f}\n\n"                # 샤프비율(위험 대비 수익률)
    f"신호: {last_sig}, 포지션: {last_pos}\n" # 최근 신호와 현재 포지션
    f"전략 누적: {df['cumulative_strategy'].iloc[-1]:.3f}, 시장 누적: {df['cumulative_market'].iloc[-1]:.3f}\n\n"
    # → 누적 수익률 (전략 vs 시장)
    f"샤프 비율\n"
    f"< 1.0 : 비효율적 (리스크 대비 수익 낮음)\n"
    f"1.0 ~ 2.0 : 양호 (적당히 효율적)\n"
    f"2.0 ~ 3.0 : 우수 (위험 대비 수익이 매우 좋음)\n"
    f"> 3.0 : 탁월 (거의 시장 초과 수준)\n\n"
    f"전략 누적(cumulative_strategy): 전략 수익률을 일 단위로 누적한 값 \n"
    f"(매수·매도 규칙을 적용한 결과)\n"
    f"시장 누적(cumulative_market): 아무 전략 없이 단순 보유했을 때의 누적 수익률\n\n"
    f"예시: 전략 누적 > 시장 누적 → 전략이 시장 대비 초과 수익 달성\n\n"
    f"용어 설명:\n"
    f"신호(signal): 시장 움직임에 따른 매매 지시값 (1=매수, -1=매도, 0=없음)\n"
    f"포지션(position): 실제 보유 상태 (1=보유, -1=공매도, 0=관망)\n\n"
    f"예시: signal=1 → 매수 진입\n"
    f"signal=0, position=1 → 보유 유지"
)

body = f"티커: {TICKER} ({company})\n기간: {start.date()} ~ {end.date()}\n\n" + today_msg + "\n\n" + summary
print(body)

# -----------------------------
# 메일 발송
# -----------------------------
if SENDER and RECIPIENTS and SMTP_SERVER and SMTP_USER and SMTP_PASS:
    for rcpt in RECIPIENTS:
        try:
            send_email(
                subject=f"[MB 퀀트] {latest_date} 시그널 - {company}",
                body=body,
                sender=SENDER,
                recipient=rcpt,
                smtp_server=SMTP_SERVER,
                smtp_port=SMTP_PORT,
                smtp_user=SMTP_USER,
                smtp_password=SMTP_PASS,
            )
        except Exception as e:
            print(f"메일 전송 실패({rcpt}): {e}")
else:
    print("환경변수 미설정으로 메일 전송 생략")