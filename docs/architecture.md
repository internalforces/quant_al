# 아키텍처와 설계 판단

## 구성

```mermaid
flowchart TB
    FE["React + Plotly"] -->|"/api/search, /api/signal, /api/price"| API["FastAPI"]
    BOT["Telegram Bot"] -->|"HTTP"| API
    API --> RES["Ticker Resolver"]
    API --> ANALYSIS["Analysis Service"]
    API --> PRICE["Price Service"]
    RES --> KRX["KRX 기업 목록"]
    RES --> YSEARCH["Yahoo Finance Search"]
    ANALYSIS --> YF["yfinance"]
    PRICE --> YF
    BOT --> ALIAS[("SQLite")]
    SCHEDULE["GitHub Actions\n평일 23:00 KST"] --> REPORT["mb_main.py\n정기 신호 리포트"]
    REPORT --> STRATEGY["Strategy Service"]
    REPORT --> SMTP["SMTP"]
    SMTP --> RECIPIENTS["수신자"]
```

## 책임 분리

| 구성 요소 | 책임 |
| --- | --- |
| `frontend/` | 검색 자동완성, 분석·가격 대시보드, 오류 메시지 표시 |
| `backend/routers/` | HTTP 요청 검증, 응답 스키마, 외부 공급자 오류의 HTTP 상태 변환 |
| `backend/services/ticker_resolver.py` | 별칭·KRX·Yahoo를 조합한 종목 해석 |
| `backend/services/strategy.py` | 신호·포지션·수익률·성과 지표의 단일 구현 |
| `backend/services/analysis.py` | 시세 다운로드와 API 응답용 변환 |
| `telegram_bot/` | 조회 명령, 채팅별 별칭 관리, 응답 포맷 |
| `mb_main.py`, `module/mail.py` | 최대 10개 종목의 신호·포지션·성과 요약 생성과 SMTP 정기 발송 |

## 주요 설계 판단

### 이름과 티커를 분리해 해석

사용자는 `삼성전자`처럼 이름을, 데이터 공급자는 `005930.KS`처럼 티커를 요구합니다. 고정 별칭을 먼저 확인하고, 국내 종목은 KRX 목록, 영문 검색은 Yahoo 후보를 사용합니다. **KRX에서 여러 후보가 나오면** 404와 후보 목록을 반환합니다. 영문 Yahoo 후보는 현재 첫 번째 결과를 사용하므로, 모호한 영문 검색은 검색 자동완성에서 명시적 티커를 선택하는 것이 안전합니다.

### 외부 I/O가 API를 멈추지 않게 처리

KRX 목록은 동기 호출이므로 `asyncio.to_thread`로 이벤트 루프 밖에서 실행합니다. KRX와 Yahoo 검색에는 짧은 타임아웃과 1회 재시도를 둡니다. 실패한 KRX 목록은 캐시하지 않아 다음 요청에서 회복 기회를 남깁니다.

### 전략 계산을 한 곳에 둠

초기에는 웹 API와 정기 이메일 스크립트에 비슷한 계산이 각각 존재했습니다. 현재는 `strategy.py`가 공통 계산을 담당해 전략 규칙 수정 시 두 채널의 결과가 달라지는 위험을 줄였습니다.

### 요청형 조회와 정기 알림을 분리

웹은 차트와 비교 정보를, Telegram은 빠른 텍스트 조회를 담당합니다. 반면 이메일은 GitHub Actions가 평일 23:00 KST에 실행하는 배치 리포트 채널로 분리해, 사용자의 요청 없이도 종목별 신호·포지션·성과 요약을 전달합니다. Telegram 별칭은 채팅 단위 SQLite에 저장하여 그룹 간 데이터를 분리합니다.

## 신뢰성 장치

- Pydantic 응답 모델로 API 형태를 고정
- `/api/health` 및 `/healthz` 헬스체크
- Docker 컨테이너 헬스체크와 재시작 정책
- 전략 시점·종목 해석·API 오류를 검증하는 pytest
- Pull Request에서 테스트, ESLint, 프로덕션 빌드를 실행하는 GitHub Actions
- SMTP 전송은 587 포트의 STARTTLS와 465 포트의 SSL을 지원하며, 모든 수신자 전송이 실패하면 정기 워크플로를 실패 처리

## 트레이드오프

공개 데이터 공급자를 사용해 구현 비용을 낮췄지만 데이터 품질 SLA는 제공하지 않습니다. 별도 데이터베이스·사용자 인증보다 종목 해석과 분석 결과 전달이라는 핵심 흐름을 먼저 완성하는 범위를 선택했습니다.
