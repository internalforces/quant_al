import { useState } from 'react';
import SearchBar from './SearchBar';
import { fetchStockPrice } from '../api/client';

export default function StockPrice() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSearch(ticker) {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const result = await fetchStockPrice(ticker);
      setData(result);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch price';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  const isPositive = data && data.change != null && data.change >= 0;
  const changeClass = data && data.change != null
    ? (isPositive ? 'positive' : 'negative')
    : '';

  return (
    <>
      <SearchBar onAnalyze={handleSearch} loading={loading} />

      {loading && <div className="loading">Fetching price data...</div>}
      {error && <div className="error">{error}</div>}

      {data && (
        <div className="price-card panel">
          <div className="panel-body">
            <div className="price-header">
              <span className="price-company">{data.company}</span>
              <span className="price-ticker">{data.ticker}</span>
            </div>

            <div className="price-display">
              <span className="price-current">
                {data.current_price != null ? data.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'N/A'}
              </span>
              <span className="price-currency">{data.currency}</span>
            </div>

            {data.change != null && (
              <div className={`price-change ${changeClass}`}>
                <span>{isPositive ? '+' : ''}{data.change.toFixed(2)}</span>
                <span>({isPositive ? '+' : ''}{data.change_percent?.toFixed(2)}%)</span>
              </div>
            )}

            <div className="price-details-grid">
              <div className="price-detail">
                <span className="price-detail-label">Previous Close</span>
                <span className="price-detail-value">{data.previous_close?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}</span>
              </div>
              <div className="price-detail">
                <span className="price-detail-label">Open</span>
                <span className="price-detail-value">{data.open?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}</span>
              </div>
              <div className="price-detail">
                <span className="price-detail-label">Day High</span>
                <span className="price-detail-value">{data.day_high?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}</span>
              </div>
              <div className="price-detail">
                <span className="price-detail-label">Day Low</span>
                <span className="price-detail-value">{data.day_low?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
