import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const getStats = () => api.get('/stats').then(r => r.data)

export const getProducts = () => api.get('/products').then(r => r.data)

export const optimizePrice = (payload) =>
  api.post('/optimize-price', payload).then(r => r.data)

export const getRevenueCurve = (productId, currentPrice, rangePctInt) =>
  api
    .get(`/revenue-curve/${productId}`, {
      params: { current_price: currentPrice, range_pct: rangePctInt / 100 },
    })
    .then(r => ({ ...r.data, curve: r.data.data }))

export const getHistory = (limit = 200, productId = null) => {
  const params = { limit }
  if (productId) params.product_id = productId
  return api.get('/history', { params }).then(r => r.data)
}

export const deleteHistoryRun = (runId) =>
  api.delete(`/history/${runId}`).then(r => r.data)

export const clearHistory = () => api.delete('/history').then(r => r.data)
