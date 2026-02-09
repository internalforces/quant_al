function fmt(v, suffix = '') {
  if (v == null) return 'N/A';
  return v.toFixed(2) + suffix;
}

function valueClass(v) {
  if (v == null) return '';
  return v >= 0 ? 'positive' : 'negative';
}

const metrics = [
  { key: 'monthly_return_pct', label: 'Monthly Return', suffix: '%', colored: true },
  { key: 'annual_return_pct', label: 'Annual Return', suffix: '%', colored: true },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio', suffix: '', colored: true },
  { key: 'cumulative_strategy', label: 'Strategy Cum.', suffix: 'x', colored: false },
  { key: 'cumulative_market', label: 'Market Cum.', suffix: 'x', colored: false },
];

export default function StatsTable({ stats }) {
  return (
    <div className="panel">
      <div className="panel-header">Performance Metrics</div>
      <div className="panel-body">
        <div className="metrics-grid">
          {metrics.map((m) => (
            <div className="metric-card" key={m.key}>
              <div className="metric-label">{m.label}</div>
              <div className={`metric-value ${m.colored ? valueClass(stats[m.key]) : ''}`}>
                {fmt(stats[m.key], m.suffix)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
