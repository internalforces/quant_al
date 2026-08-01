export default function SignalCard({ lastSignal, lastPosition, latestDate }) {
  let label, signalType, description, krDescription;

  if (lastSignal === 1) {
    label = 'BUY (매수)';
    signalType = 'signal-buy';
    description = 'Dip detected (buy signal) — consider accumulating';
    krDescription = '하락 감지 (매수 신호) — 매수 고려';
  } else if (lastSignal === -1) {
    label = 'SELL (매도)';
    signalType = 'signal-sell';
    description = 'Spike detected (sell signal) — consider taking profit';
    krDescription = '급등 감지 (매도 신호) — 이익 실현 고려';
  } else if (lastPosition === 1) {
    label = 'HOLD (보유)';
    signalType = 'signal-hold';
    description = 'Maintaining existing position';
    krDescription = '기존 포지션 유지';
  } else if (lastPosition === -1) {
    label = 'SHORT (숏)';
    signalType = 'signal-sell';
    description = 'Maintaining short position';
    krDescription = '숏 포지션 유지';
  } else {
    label = 'NONE (없음)';
    signalType = 'signal-none';
    description = 'No signal — wait and observe';
    krDescription = '신호 없음 — 대기 및 관찰';
  }

  return (
    <div className={`panel ${signalType}`}>
      <div className="panel-header">Latest Signal (최신 신호)</div>
      <div className="signal-card">
        <div className="signal-label">{label}</div>
        <div className="signal-info">
          <div className="signal-date">{latestDate}</div>
          <div className="signal-desc">{description}</div>
          <div className="signal-desc-kr">{krDescription}</div>
        </div>
      </div>
    </div>
  );
}
