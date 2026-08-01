import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
});

export async function searchTickers(query) {
  const { data } = await api.get('/search', { params: { q: query } });
  return data.results;
}

export async function analyzeTicker(query) {
  const { data } = await api.get('/signal', { params: { q: query } });
  return data.analysis;
}

export async function fetchStockPrice(query) {
  const { data } = await api.get('/price', { params: { q: query } });
  return data.price;
}
