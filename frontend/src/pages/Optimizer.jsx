import { useEffect, useState } from 'react'
import { getProducts, optimizePrice, getRevenueCurve } from '../api/client'
import PageHeader from '../components/PageHeader'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'
import { Zap } from 'lucide-react'
import clsx from 'clsx'

export default function Optimizer() {
  const [products,    setProducts]    = useState([])
  const [productId,   setProductId]   = useState('')
  const [price,       setPrice]       = useState('')
  const [rangePct,    setRangePct]    = useState(30)
  const [result,      setResult]      = useState(null)
  const [curve,       setCurve]       = useState([])
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)

  useEffect(() => {
    getProducts().then(ps => {
      setProducts(ps)
      if (ps.length) {
        setProductId(ps[0].product_id)
        setPrice(ps[0].current_price.toFixed(2))
      }
    })
  }, [])

  const handleProductChange = (e) => {
    const pid = e.target.value
    setProductId(pid)
    const p = products.find(x => x.product_id === pid)
    if (p) setPrice(p.current_price.toFixed(2))
    setResult(null)
    setCurve([])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setResult(null)
    setCurve([])
    try {
      const [res, curveData] = await Promise.all([
        optimizePrice({ product_id: productId, current_price: parseFloat(price), price_range_pct: rangePct / 100 }),
        getRevenueCurve(productId, parseFloat(price), rangePct),
      ])
      setResult(res)
      setCurve(curveData.curve || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }

  const fmt = (n) =>
    n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(2)}M` : `$${(n / 1_000).toFixed(1)}K`

  return (
    <div>
      <PageHeader
        title="Price Optimizer"
        subtitle="Run ML-powered price optimization for any product"
      />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-5">Optimization Parameters</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">Product</label>
              <select
                className="bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={productId}
                onChange={handleProductChange}
              >
                {products.map(p => (
                  <option key={p.product_id} value={p.product_id}>
                    {p.product_id} — {p.category}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Current Price ($)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                className="bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-500"
                value={price}
                onChange={e => setPrice(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Search Range: ±{rangePct}%
              </label>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                className="w-full accent-blue-500"
                value={rangePct}
                onChange={e => setRangePct(Number(e.target.value))}
              />
              <div className="flex justify-between text-xs text-gray-600 mt-1">
                <span>5%</span><span>50%</span>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !productId || !price}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Zap size={16} />
              {loading ? 'Optimizing…' : 'Run Optimization'}
            </button>

            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
          </form>

          {/* Result card */}
          {result && (
            <div className="mt-6 border border-gray-700 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Optimization Result</span>
                <span className={clsx(
                  'text-xs font-medium px-2 py-0.5 rounded-full',
                  Math.abs(result.elasticity) > 1
                    ? 'bg-red-500/20 text-red-300'
                    : 'bg-green-500/20 text-green-300'
                )}>
                  {Math.abs(result.elasticity) > 1 ? 'Elastic' : 'Inelastic'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Optimal Price',   value: `$${result.optimal_price.toFixed(2)}`,         color: 'text-green-400' },
                  { label: 'Revenue Uplift',  value: `+${result.expected_revenue_increase.toFixed(2)}%`, color: 'text-blue-400' },
                  { label: 'Current Revenue', value: fmt(result.current_revenue),                   color: 'text-gray-200' },
                  { label: 'Optimal Revenue', value: fmt(result.optimal_revenue),                   color: 'text-emerald-400' },
                ].map(({ label, value, color }) => (
                  <div key={label} className="bg-gray-800/60 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-0.5">{label}</p>
                    <p className={clsx('text-base font-bold', color)}>{value}</p>
                  </div>
                ))}
              </div>

              <p className="text-xs text-gray-400 italic">{result.interpretation}</p>
            </div>
          )}
        </div>

        {/* Revenue curve */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Revenue Curve</h2>
          {curve.length === 0 ? (
            <div className="h-72 flex items-center justify-center text-gray-600 text-sm">
              Run optimization to see the revenue curve
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={curve} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="price"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickFormatter={v => `$${v}`}
                />
                <YAxis
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickFormatter={v => `$${(v / 1000).toFixed(0)}K`}
                />
                <Tooltip
                  contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                  labelFormatter={v => `Price: $${v}`}
                  formatter={(v) => [fmt(v), 'Revenue']}
                />
                {result && (
                  <ReferenceLine
                    x={result.optimal_price}
                    stroke="#10b981"
                    strokeDasharray="4 2"
                    label={{ value: 'Optimal', fill: '#10b981', fontSize: 11 }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
