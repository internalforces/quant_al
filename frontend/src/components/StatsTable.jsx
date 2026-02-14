function fmt(v, suffix = '') {
  if (v == null) return 'N/A (데이터 없음)';
  return v.toFixed(2) + suffix;
}

function valueClass(v) {
  if (v == null) return '';
  return v >= 0 ? 'positive' : 'negative';
}

const metrics = [
  { key: 'monthly_return_pct', label: 'Monthly Return (월간 수익률)', suffix: '%', colored: true },
  { key: 'annual_return_pct', label: 'Annual Return (연환산 수익률)', suffix: '%', colored: true },
  { key: 'sharpe_ratio', label: 'Sharpe Ratio (샤프 비율)', suffix: '', colored: true },
  { key: 'cumulative_strategy', label: 'Strategy Cum. (전략 누적)', suffix: 'x', colored: false },
  { key: 'cumulative_market', label: 'Market Cum. (시장 누적)', suffix: 'x', colored: false },
];

export default function StatsTable({ stats }) {
  return (
    <div className="panel">
      <div className="panel-header">Performance Metrics(성과 지표)</div>
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
