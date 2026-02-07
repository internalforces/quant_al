import { useState, useRef, useEffect, useCallback } from 'react';
import { searchTickers } from '../api/client';

export default function SearchBar({ onAnalyze, loading }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const timerRef = useRef(null);
  const wrapperRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const debouncedSearch = useCallback((value) => {
    clearTimeout(timerRef.current);
    if (!value.trim()) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const results = await searchTickers(value);
        setSuggestions(results);
        setShowDropdown(results.length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }, []);

  function handleChange(e) {
    const value = e.target.value;
    setQuery(value);
    debouncedSearch(value);
  }

  function handleSelect(symbol) {
    setQuery(symbol);
    setShowDropdown(false);
    onAnalyze(symbol);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && query.trim()) {
      setShowDropdown(false);
      onAnalyze(query.trim());
    }
  }

  return (
    <div className="search-bar" ref={wrapperRef}>
      <input
        type="text"
        value={query}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder="Search ticker (e.g. AAPL, 005930.KS)"
        disabled={loading}
      />
      <button onClick={() => query.trim() && onAnalyze(query.trim())} disabled={loading || !query.trim()}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
      {showDropdown && (
        <ul className="suggestions">
          {suggestions.map((s) => (
            <li key={s.symbol} onClick={() => handleSelect(s.symbol)}>
              <strong>{s.symbol}</strong> <span>{s.name}</span> <small>{s.exchange}</small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
