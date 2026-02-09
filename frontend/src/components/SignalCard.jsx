export default function SignalCard({ lastSignal, lastPosition, latestDate }) {
  let label, signalType, description;

  if (lastSignal === 1) {
    label = 'BUY';
    signalType = 'signal-buy';
    description = 'Dip detected (buy signal) — consider accumulating';
  } else if (lastSignal === -1) {
    label = 'SELL';
    signalType = 'signal-sell';
    description = 'Spike detected (sell signal) — consider taking profit';
  } else if (lastPosition === 1) {
    label = 'HOLD';
    signalType = 'signal-hold';
    description = 'Maintaining existing position';
  } else {
    label = 'NONE';
    signalType = 'signal-none';
    description = 'No signal — wait and observe';
  }

  return (
    <div className={`panel ${signalType}`}>
      <div className="panel-header">Latest Signal</div>
      <div className="signal-card">
        <div className="signal-label">{label}</div>
        <div className="signal-info">
          <div className="signal-date">{latestDate}</div>
          <div className="signal-desc">{description}</div>
        </div>
      </div>
    </div>
  );
}
