import { useEffect, useState } from 'react'
import { getProducts } from '../api/client'
import PageHeader from '../components/PageHeader'
import clsx from 'clsx'

export default function Products() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [sort, setSort]     = useState({ key: 'product_id', dir: 1 })

  useEffect(() => {
    getProducts()
      .then(setProducts)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-400 text-sm">Loading products…</div>
  if (error)   return <div className="text-red-400 text-sm">Error: {error}</div>

  const sorted = [...products].sort((a, b) => {
    const va = a[sort.key], vb = b[sort.key]
    return typeof va === 'string'
      ? sort.dir * va.localeCompare(vb)
      : sort.dir * (va - vb)
  })

  const toggle = (key) =>
    setSort(s => ({ key, dir: s.key === key ? -s.dir : 1 }))

  const col = (key, label) => (
    <th
      key={key}
      onClick={() => toggle(key)}
      className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider cursor-pointer select-none hover:text-white whitespace-nowrap"
    >
      {label}
      {sort.key === key && (
        <span className="ml-1 text-brand-500">{sort.dir === 1 ? '↑' : '↓'}</span>
      )}
    </th>
  )

  const fmt = (n) =>
    n >= 1_000_000
      ? `$${(n / 1_000_000).toFixed(2)}M`
      : `$${(n / 1_000).toFixed(1)}K`

  return (
    <div>
      <PageHeader
        title="Product Catalog"
        subtitle={`${products.length} products · click column headers to sort`}
      />

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-800/60 border-b border-gray-800">
              <tr>
                {col('product_id',   'Product')}
                {col('category',     'Category')}
                {col('current_price','Price')}
                {col('optimal_price','Optimal Price')}
                {col('elasticity',   'Elasticity')}
                {col('price_elasticity_category', 'Type')}
                {col('current_revenue',  'Revenue')}
                {col('expected_revenue_increase_pct', 'Uplift')}
              </tr>
            </thead>
            <tbody>
              {sorted.map((p, i) => (
                <tr
                  key={p.product_id}
                  className={clsx(
                    'border-b border-gray-800/50 transition-colors',
                    i % 2 === 0 ? 'bg-transparent' : 'bg-gray-800/20',
                    'hover:bg-gray-800/50'
                  )}
                >
                  <td className="px-4 py-3 font-semibold text-white">{p.product_id}</td>
                  <td className="px-4 py-3 text-gray-300">{p.category}</td>
                  <td className="px-4 py-3 text-gray-300">${p.current_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-green-400 font-medium">${p.optimal_price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-gray-300">{p.elasticity.toFixed(3)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={clsx(
                        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
                        p.price_elasticity_category === 'Elastic'
                          ? 'bg-red-500/20 text-red-300'
                          : 'bg-green-500/20 text-green-300'
                      )}
                    >
                      {p.price_elasticity_category}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-300">{fmt(p.current_revenue)}</td>
                  <td className="px-4 py-3">
                    <span className={clsx(
                      'font-medium',
                      p.expected_revenue_increase_pct >= 0 ? 'text-green-400' : 'text-red-400'
                    )}>
                      {p.expected_revenue_increase_pct >= 0 ? '+' : ''}
                      {p.expected_revenue_increase_pct.toFixed(2)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
