import { useState } from 'react';
import SearchBar from './components/SearchBar';
import AnalysisResult from './components/AnalysisResult';
import StockPrice from './components/StockPrice';
import { analyzeTicker, fetchStockPrice } from './api/client';

export default function App() {
  const [analysisData, setAnalysisData] = useState(null);
  const [priceData, setPriceData] = useState(null);
  const [analysisError, setAnalysisError] = useState(null);
  const [priceError, setPriceError] = useState(null);
  const [searchedTicker, setSearchedTicker] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleAnalyze(ticker) {
    setLoading(true);
    setSearchedTicker(ticker);
    setAnalysisData(null);
    setPriceData(null);
    setAnalysisError(null);
    setPriceError(null);

    const [analysisResult, priceResult] = await Promise.allSettled([
      analyzeTicker(ticker),
      fetchStockPrice(ticker),
    ]);

    if (analysisResult.status === 'fulfilled') {
      setAnalysisData(analysisResult.value);
    } else {
      const msg = analysisResult.reason?.response?.data?.detail
        || analysisResult.reason?.message
        || 'Analysis failed (분석에 실패했습니다)';
      setAnalysisError(msg);
    }

    if (priceResult.status === 'fulfilled') {
      setPriceData(priceResult.value);
    } else {
      const msg = priceResult.reason?.response?.data?.detail
        || priceResult.reason?.message
        || 'Failed to fetch price (주가 조회에 실패했습니다)';
      setPriceError(msg);
    }

    setLoading(false);
  }

  const hasSearched = Boolean(searchedTicker);

  return (
    <div className="app">
      <header>
        <h1>MB Quant</h1>
        <span className="subtitle">Maxwell-Boltzmann Distribution Analysis (맥스웰-볼츠만 분포 분석)</span>
      </header>

      <div className="dashboard-search">
        <SearchBar onAnalyze={handleAnalyze} loading={loading} />
      </div>

      {loading && <div className="loading">Building dashboard... this may take a few seconds. (대시보드를 구성 중입니다... 잠시만 기다려주세요.)</div>}

      {!loading && !hasSearched && (
        <div className="dashboard-empty panel">
          <div className="panel-body">
            <p>Search a ticker to open the full dashboard. (티커를 검색하면 통합 대시보드가 열립니다.)</p>
            <small>Analysis appears first, then stock price and extra insights. (분석 섹션이 먼저 보이고, 그 아래 주가 및 추가 인사이트가 표시됩니다.)</small>
          </div>
        </div>
      )}

      {hasSearched && (
        <div className="dashboard-sections">
          <section className="dashboard-section">
            <div className="section-heading">
              <h2>1. Analysis (분석)</h2>
              <span>{searchedTicker.toUpperCase()}</span>
            </div>
            {analysisError && <div className="error">{analysisError}</div>}
            {analysisData && <AnalysisResult data={analysisData} />}
          </section>

          <section className="dashboard-section">
            <div className="section-heading">
              <h2>2. Stock Price (주가)</h2>
              <span>Live market snapshot (실시간 시장 스냅샷)</span>
            </div>
            {priceError && <div className="error">{priceError}</div>}
            {priceData && <StockPrice data={priceData} analysisData={analysisData} />}
          </section>
        </div>
      )}
    </div>
  );
}
