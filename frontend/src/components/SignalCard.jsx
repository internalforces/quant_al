export default function SignalCard({ lastSignal, lastPosition, latestDate }) {
  let label, className, description;

  if (lastSignal === 1) {
    label = 'BUY';
    className = 'signal-buy';
    description = 'Dip detected (buy signal) — consider accumulating';
  } else if (lastSignal === -1) {
    label = 'SELL';
    className = 'signal-sell';
    description = 'Spike detected (sell signal) — consider taking profit';
  } else if (lastPosition === 1) {
    label = 'HOLD';
    className = 'signal-hold';
    description = 'Maintaining existing position';
  } else {
    label = 'NONE';
    className = 'signal-none';
    description = 'No signal — wait and observe';
  }

  return (
    <div className={`signal-card ${className}`}>
      <div className="signal-date">{latestDate}</div>
      <div className="signal-label">{label}</div>
      <div className="signal-desc">{description}</div>
    </div>
  );
}
