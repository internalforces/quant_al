import Plot from 'react-plotly.js';

const darkLayout = {
  paper_bgcolor: '#1a2332',
  plot_bgcolor: '#131d29',
  font: { color: '#8892a0', size: 11 },
  xaxis: {
    title: 'Date',
    gridcolor: '#2a3545',
    linecolor: '#2a3545',
    zerolinecolor: '#2a3545',
  },
  yaxis: {
    title: 'Cumulative Return',
    gridcolor: '#2a3545',
    linecolor: '#2a3545',
    zerolinecolor: '#2a3545',
  },
  legend: { orientation: 'h', y: -0.2, font: { color: '#8892a0' } },
  margin: { t: 12, r: 16, b: 56, l: 56 },
  autosize: true,
};

export default function ReturnChart({ chartData }) {
  const { dates, cumulative_strategy, cumulative_market } = chartData;

  return (
    <div className="panel chart-panel">
      <div className="panel-header">Cumulative Returns</div>
      <div className="panel-body">
        <Plot
          data={[
            {
              x: dates,
              y: cumulative_strategy,
              type: 'scatter',
              mode: 'lines',
              name: 'MB Strategy',
              line: { color: '#00c896', width: 2 },
            },
            {
              x: dates,
              y: cumulative_market,
              type: 'scatter',
              mode: 'lines',
              name: 'Buy & Hold',
              line: { color: '#f0b90b', width: 2 },
            },
          ]}
          layout={darkLayout}
          useResizeHandler
          style={{ width: '100%', height: '400px' }}
          config={{ responsive: true, displayModeBar: false }}
        />
      </div>
    </div>
  );
}
