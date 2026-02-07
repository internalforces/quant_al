import Plot from 'react-plotly.js';

export default function ReturnChart({ chartData }) {
  const { dates, cumulative_strategy, cumulative_market } = chartData;

  return (
    <Plot
      data={[
        {
          x: dates,
          y: cumulative_strategy,
          type: 'scatter',
          mode: 'lines',
          name: 'MB Strategy',
          line: { color: '#4CAF50', width: 2 },
        },
        {
          x: dates,
          y: cumulative_market,
          type: 'scatter',
          mode: 'lines',
          name: 'Buy & Hold',
          line: { color: '#FF9800', width: 2 },
        },
      ]}
      layout={{
        title: 'Cumulative Returns: Strategy vs Market',
        xaxis: { title: 'Date' },
        yaxis: { title: 'Cumulative Return' },
        legend: { orientation: 'h', y: -0.2 },
        margin: { t: 40, r: 20, b: 60, l: 60 },
        autosize: true,
      }}
      useResizeHandler
      style={{ width: '100%', height: '400px' }}
      config={{ responsive: true }}
    />
  );
}
