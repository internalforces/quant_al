import SignalCard from './SignalCard';
import StatsTable from './StatsTable';
import PriceChart from './PriceChart';
import ReturnChart from './ReturnChart';

export default function AnalysisResult({ data }) {
  return (
    <div className="analysis-result">
      <h2>
        {data.ticker} — {data.company}
      </h2>
      <p className="period">
        Period: {data.period_start} ~ {data.period_end}
      </p>

      <SignalCard
        lastSignal={data.last_signal}
        lastPosition={data.last_position}
        latestDate={data.latest_date}
      />

      <StatsTable stats={data.stats} />

      <div className="charts">
        <PriceChart chartData={data.chart_data} />
        <ReturnChart chartData={data.chart_data} />
      </div>
    </div>
  );
}
