# API 사용법

개발 서버 기준 주소는 `http://127.0.0.1:8000`입니다. 실행 중인 API의 전체 스키마는 `/docs`에서 확인할 수 있습니다.

## 종목 검색

```http
GET /api/search?q=삼성전자
```

응답은 선택 가능한 티커 후보를 반환합니다.

```json
{
  "results": [
    {
      "symbol": "005930.KS",
      "name": "삼성전자",
      "exchange": "KRX",
      "type": "EQUITY"
    }
  ]
}
```

## 종목 해석

```http
GET /api/resolve?q=삼전
```

```json
{
  "result": {
    "query": "삼전",
    "ticker": "005930.KS",
    "name": "삼성전자",
    "market": "KOSPI",
    "exchange": "KRX",
    "source": "alias"
  }
}
```

검색 결과가 여러 개인 경우 HTTP 404와 함께 `message`, `suggestions`를 반환합니다. 프론트엔드는 이 값을 사람이 읽을 수 있는 오류와 후보 목록으로 표시합니다.

## 가격 조회

이름 또는 티커를 권장합니다.

```http
GET /api/price?q=애플
```

```json
{
  "resolution": { "ticker": "AAPL", "name": "Apple Inc." },
  "price": {
    "ticker": "AAPL",
    "current_price": 0.0,
    "previous_close": 0.0,
    "change": 0.0,
    "change_percent": 0.0,
    "currency": "USD"
  }
}
```

기존 티커 전용 경로도 제공합니다.

```http
GET /api/price/AAPL
```

## 신호 조회

```http
GET /api/signal?q=005930.KS
```

응답에는 종목 해석 결과, 최신 신호·포지션, 성과 지표, 차트 데이터가 포함됩니다.

```json
{
  "resolution": { "ticker": "005930.KS", "name": "삼성전자" },
  "analysis": {
    "last_signal": 0,
    "last_position": 1,
    "stats": {
      "monthly_return_pct": 0.0,
      "annual_return_pct": 0.0,
      "sharpe_ratio": 0.0,
      "cumulative_strategy": 1.0,
      "cumulative_market": 1.0
    },
    "chart_data": { "dates": [], "close": [], "signal": [] }
  }
}
```

티커 전용 분석 경로는 `/api/analyze/{ticker}`입니다.

## 오류 규약

| 상태 | 의미 |
| --- | --- |
| 404 | 종목을 찾지 못했거나 제공자가 가격 데이터를 반환하지 않음 |
| 422 | 필수 질의값 누락 또는 형식 오류 |
| 502 | KRX, Yahoo, yfinance 등 외부 공급자 조회 실패 |

외부 공급자 응답은 변할 수 있으므로 클라이언트는 성공 응답만 가정하지 말고 오류 메시지를 표시해야 합니다.
