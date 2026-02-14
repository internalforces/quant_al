function fmtPrice(value) {
  if (value == null) return 'N/A (데이터 없음)';
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtPercent(value) {
  if (value == null) return 'N/A (데이터 없음)';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function fmtFactor(value) {
  if (value == null) return 'N/A (데이터 없음)';
  return `${value.toFixed(2)}x`;
}

export default function StockPrice({ data, analysisData }) {
  const isPositive = data && data.change != null && data.change >= 0;
  const changeClass = data && data.change != null
    ? (isPositive ? 'positive' : 'negative')
    : '';
  const currentClass = changeClass || 'neutral';

  const dayRange = (data?.day_high != null && data?.day_low != null)
    ? data.day_high - data.day_low
    : null;
  const rangeProgress = (dayRange && data.current_price != null)
    ? Math.min(100, Math.max(0, ((data.current_price - data.day_low) / dayRange) * 100))
    : null;

  const strategyEdge = (analysisData?.stats?.cumulative_strategy != null && analysisData?.stats?.cumulative_market != null)
    ? analysisData.stats.cumulative_strategy - analysisData.stats.cumulative_market
    : null;
  const strategyEdgeClass = strategyEdge != null ? (strategyEdge >= 0 ? 'positive' : 'negative') : '';

  const signalText = analysisData?.last_signal === 1
    ? 'BUY (매수)'
    : analysisData?.last_signal === -1
      ? 'SELL (매도)'
      : analysisData?.last_position === 1
        ? 'HOLD (보유)'
        : 'NONE (없음)';
  const signalClass = analysisData?.last_signal === 1
    ? 'positive'
    : analysisData?.last_signal === -1
      ? 'negative'
      : 'neutral';

  const momentumHint = data.change_percent == null
    ? 'N/A (데이터 없음)'
    : data.change_percent >= 2
      ? 'Strong upside momentum (강한 상승 모멘텀)'
      : data.change_percent <= -2
        ? 'Strong downside pressure (강한 하락 압력)'
        : 'Neutral daily momentum (중립적인 일간 모멘텀)';
  const momentumClass = data.change_percent == null
    ? 'neutral'
    : data.change_percent >= 2
      ? 'positive'
      : data.change_percent <= -2
        ? 'negative'
        : 'neutral';

  return (
    <div className="price-section">
      <div className="price-card panel">
        <div className="panel-body">
          <div className="price-header">
            <span className="price-company">{data.company}</span>
            <span className="price-ticker">{data.ticker}</span>
          </div>

          <div className="price-display">
            <span className={`price-current ${currentClass}`}>{fmtPrice(data.current_price)}</span>
            <span className="price-currency">{data.currency}</span>
          </div>

          {data.change != null && (
            <div className={`price-change ${changeClass}`}>
              <span>{isPositive ? '+' : ''}{data.change.toFixed(2)}</span>
              <span>({fmtPercent(data.change_percent)})</span>
            </div>
          )}

          <div className="price-details-grid">
            <div className="price-detail">
              <span className="price-detail-label">Previous Close (전일 종가)</span>
              <span className="price-detail-value neutral">{fmtPrice(data.previous_close)}</span>
            </div>
            <div className="price-detail">
              <span className="price-detail-label">Open (시가)</span>
              <span className="price-detail-value neutral">{fmtPrice(data.open)}</span>
            </div>
            <div className="price-detail">
              <span className="price-detail-label">Day High (당일 고가)</span>
              <span className="price-detail-value positive">{fmtPrice(data.day_high)}</span>
            </div>
            <div className="price-detail">
              <span className="price-detail-label">Day Low (당일 저가)</span>
              <span className="price-detail-value negative">{fmtPrice(data.day_low)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="insights-grid">
        <div className="panel insight-card">
          <div className="panel-header">Intraday Range (장중 변동폭)</div>
            <div className="panel-body">
            <div className="insight-main">{dayRange == null ? 'N/A (데이터 없음)' : fmtPrice(dayRange)}</div>
            <p className="insight-sub">High - Low spread for the current session. (현재 세션의 고가-저가 차이)</p>
            <div className="range-track">
              <span style={{ width: `${rangeProgress ?? 0}%` }} />
            </div>
          </div>
        </div>

        <div className="panel insight-card">
          <div className="panel-header">Signal Context (신호 맥락)</div>
          <div className="panel-body">
            <div className={`insight-main ${signalClass}`}>{signalText}</div>
            <p className={`insight-sub ${momentumClass}`}>{momentumHint}</p>
            <div className="insight-kv">
              <span>Latest Signal Date (최신 신호 일자)</span>
              <strong>{analysisData?.latest_date ?? 'N/A (데이터 없음)'}</strong>
            </div>
          </div>
        </div>

        <div className="panel insight-card">
          <div className="panel-header">Strategy Edge (전략 우위)</div>
          <div className="panel-body">
            <div className={`insight-main ${strategyEdgeClass}`}>{fmtFactor(strategyEdge)}</div>
            <p className="insight-sub">Strategy cumulative return minus market cumulative return. (전략 누적수익률 - 시장 누적수익률)</p>
            <div className="insight-kv">
              <span>Annual Return (연환산 수익률)</span>
              <strong>{fmtPercent(analysisData?.stats?.annual_return_pct)}</strong>
            </div>
          </div>
        </div>

        <div className="panel insight-card">
          <div className="panel-header">Risk Snapshot (리스크 요약)</div>
          <div className="panel-body">
            <div className="insight-main">{fmtPercent(analysisData?.stats?.monthly_return_pct)}</div>
            <p className="insight-sub">Current monthly return profile from the model. (모델 기준 현재 월간 수익률 프로파일)</p>
            <div className="insight-kv">
              <span>Sharpe Ratio (샤프 비율)</span>
              <strong>{analysisData?.stats?.sharpe_ratio?.toFixed(2) ?? 'N/A (데이터 없음)'}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
