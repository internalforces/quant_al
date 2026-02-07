import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export async function searchTickers(query) {
  const { data } = await api.get('/search', { params: { q: query } });
  return data.results;
}

export async function analyzeTicker(ticker) {
  const { data } = await api.get(`/analyze/${encodeURIComponent(ticker)}`);
  return data;
}
