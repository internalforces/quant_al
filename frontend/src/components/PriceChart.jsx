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
    title: 'Price',
    gridcolor: '#2a3545',
    linecolor: '#2a3545',
    zerolinecolor: '#2a3545',
  },
  legend: { orientation: 'h', y: -0.2, font: { color: '#8892a0' } },
  margin: { t: 12, r: 16, b: 56, l: 56 },
  autosize: true,
};

export default function PriceChart({ chartData }) {
  const { dates, close, signal } = chartData;

  const buyDates = [], buyPrices = [];
  const sellDates = [], sellPrices = [];
  for (let i = 0; i < dates.length; i++) {
    if (signal[i] === 1) {
      buyDates.push(dates[i]);
      buyPrices.push(close[i]);
    } else if (signal[i] === -1) {
      sellDates.push(dates[i]);
      sellPrices.push(close[i]);
    }
  }

  return (
    <div className="panel chart-panel">
      <div className="panel-header">Price & Signals</div>
      <div className="panel-body">
        <Plot
          data={[
            {
              x: dates,
              y: close,
              type: 'scatter',
              mode: 'lines',
              name: 'Close Price',
              line: { color: '#3b82f6', width: 1.5 },
            },
            {
              x: buyDates,
              y: buyPrices,
              type: 'scatter',
              mode: 'markers',
              name: 'Buy Signal',
              marker: { symbol: 'triangle-up', size: 10, color: '#00c896' },
            },
            {
              x: sellDates,
              y: sellPrices,
              type: 'scatter',
              mode: 'markers',
              name: 'Sell Signal',
              marker: { symbol: 'triangle-down', size: 10, color: '#ff4757' },
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
