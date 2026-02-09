import SignalCard from './SignalCard';
import StatsTable from './StatsTable';
import PriceChart from './PriceChart';
import ReturnChart from './ReturnChart';

export default function AnalysisResult({ data }) {
  return (
    <div className="analysis-result">
      <div className="result-header">
        <h2>
          {data.ticker} — {data.company}
        </h2>
        <p className="period">
          {data.period_start} ~ {data.period_end}
        </p>
      </div>

      <div className="dashboard-top">
        <SignalCard
          lastSignal={data.last_signal}
          lastPosition={data.last_position}
          latestDate={data.latest_date}
        />
        <StatsTable stats={data.stats} />
      </div>

      <div className="dashboard-charts">
        <PriceChart chartData={data.chart_data} />
        <ReturnChart chartData={data.chart_data} />
      </div>
    </div>
  );
}
