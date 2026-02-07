function fmt(v, suffix = '') {
  if (v == null) return 'N/A';
  return v.toFixed(2) + suffix;
}

export default function StatsTable({ stats }) {
  return (
    <table className="stats-table">
      <thead>
        <tr>
          <th>Metric</th>
          <th>Value</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Monthly Return</td>
          <td>{fmt(stats.monthly_return_pct, '%')}</td>
        </tr>
        <tr>
          <td>Annual Return</td>
          <td>{fmt(stats.annual_return_pct, '%')}</td>
        </tr>
        <tr>
          <td>Sharpe Ratio</td>
          <td>{fmt(stats.sharpe_ratio)}</td>
        </tr>
        <tr>
          <td>Strategy Cumulative</td>
          <td>{fmt(stats.cumulative_strategy, 'x')}</td>
        </tr>
        <tr>
          <td>Market Cumulative</td>
          <td>{fmt(stats.cumulative_market, 'x')}</td>
        </tr>
      </tbody>
    </table>
  );
}
