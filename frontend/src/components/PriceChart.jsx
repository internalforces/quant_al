import Plot from 'react-plotly.js';

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
    <Plot
      data={[
        {
          x: dates,
          y: close,
          type: 'scatter',
          mode: 'lines',
          name: 'Close Price',
          line: { color: '#2196F3', width: 1.5 },
        },
        {
          x: buyDates,
          y: buyPrices,
          type: 'scatter',
          mode: 'markers',
          name: 'Buy Signal',
          marker: { symbol: 'triangle-up', size: 10, color: '#4CAF50' },
        },
        {
          x: sellDates,
          y: sellPrices,
          type: 'scatter',
          mode: 'markers',
          name: 'Sell Signal',
          marker: { symbol: 'triangle-down', size: 10, color: '#F44336' },
        },
      ]}
      layout={{
        title: 'Price & Signals',
        xaxis: { title: 'Date' },
        yaxis: { title: 'Price' },
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
