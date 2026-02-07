import { useState } from 'react';
import SearchBar from './components/SearchBar';
import AnalysisResult from './components/AnalysisResult';
import { analyzeTicker } from './api/client';

export default function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleAnalyze(ticker) {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await analyzeTicker(ticker);
      setData(result);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Analysis failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>MB Quant</h1>
        <p className="subtitle">Maxwell-Boltzmann Distribution Stock Analysis</p>
      </header>

      <SearchBar onAnalyze={handleAnalyze} loading={loading} />

      {loading && <div className="loading">Analyzing... this may take a few seconds.</div>}
      {error && <div className="error">{error}</div>}
      {data && <AnalysisResult data={data} />}
    </div>
  );
}
