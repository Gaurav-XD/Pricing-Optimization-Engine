import { useEffect, useState } from 'react'
import { getStats, getProducts } from '../api/client'
import KpiCard from '../components/KpiCard'
import PageHeader from '../components/PageHeader'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid
} from 'recharts'
import { TrendingUp, Package, Activity, DollarSign } from 'lucide-react'

const COLORS = {
  elastic:   '#f87171',
  inelastic: '#4ade80',
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getStats(), getProducts()])
      .then(([s, p]) => { setStats(s); setProducts(p) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-400 text-sm">Loading dashboard…</div>
  if (error)   return <div className="text-red-400 text-sm">Error: {error}</div>

  const elasticityData = products.map(p => ({
    name: p.product_id,
    elasticity: Math.abs(parseFloat(p.elasticity.toFixed(2))),
    isElastic: p.price_elasticity_category === 'Elastic',
  }))

  const revenueData = products.map(p => ({
    name: p.product_id,
    current:  parseFloat((p.current_revenue / 1000).toFixed(1)),
    optimal:  parseFloat((p.optimal_revenue / 1000).toFixed(1)),
  }))

  const fmt = (n) =>
    n >= 1_000_000
      ? `$${(n / 1_000_000).toFixed(2)}M`
      : `$${(n / 1_000).toFixed(1)}K`

  return (
    <div>
      <PageHeader
        title="Portfolio Dashboard"
        subtitle="Real-time overview of pricing performance across all products"
      />

      {/* KPI cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
        <KpiCard
          title="Total Products"
          value={stats.total_products}
          icon={Package}
          color="blue"
          subtitle="Active in portfolio"
        />
        <KpiCard
          title="Avg Elasticity"
          value={Math.abs(stats.avg_elasticity).toFixed(2)}
          icon={Activity}
          color="purple"
          subtitle={`${stats.elastic_products} elastic · ${stats.inelastic_products} inelastic`}
        />
        <KpiCard
          title="Current Revenue"
          value={fmt(stats.portfolio_current_revenue)}
          icon={DollarSign}
          color="amber"
          subtitle="Portfolio total"
        />
        <KpiCard
          title="Revenue Uplift"
          value={`+${stats.portfolio_uplift_pct.toFixed(1)}%`}
          icon={TrendingUp}
          color="green"
          subtitle={`Optimal: ${fmt(stats.portfolio_optimal_revenue)}`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Elasticity chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Price Elasticity by Product</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={elasticityData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#f9fafb' }}
                formatter={(v) => [`|${v}|`, 'Elasticity']}
              />
              <Bar dataKey="elasticity" radius={[4, 4, 0, 0]}>
                {elasticityData.map((d, i) => (
                  <Cell key={i} fill={d.isElastic ? COLORS.elastic : COLORS.inelastic} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-3">
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400" />Elastic (&gt;1)
            </span>
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2.5 h-2.5 rounded-full bg-green-400" />Inelastic (≤1)
            </span>
          </div>
        </div>

        {/* Revenue comparison chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Revenue: Current vs Optimal (K$)</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={revenueData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#f9fafb' }}
                formatter={(v) => [`$${v}K`]}
              />
              <Bar dataKey="current" name="Current" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="optimal" name="Optimal" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-3">
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-blue-500" />Current
            </span>
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />Optimal
            </span>
          </div>
        </div>
      </div>

      {/* Extremes */}
      {stats.most_elastic && (
        <div className="grid grid-cols-2 gap-4 mt-6">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Most Elastic</p>
            <p className="text-lg font-bold text-red-400">{stats.most_elastic.product_id}</p>
            <p className="text-sm text-gray-400">
              ε = {stats.most_elastic.elasticity.toFixed(3)} · {stats.most_elastic.category}
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">Most Inelastic</p>
            <p className="text-lg font-bold text-green-400">{stats.most_inelastic.product_id}</p>
            <p className="text-sm text-gray-400">
              ε = {stats.most_inelastic.elasticity.toFixed(3)} · {stats.most_inelastic.category}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
