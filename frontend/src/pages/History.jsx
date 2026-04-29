import { useEffect, useState, useCallback } from 'react'
import { getHistory, deleteHistoryRun, clearHistory } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Trash2, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

export default function History() {
  const [runs,    setRuns]    = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    getHistory(200)
      .then(setRuns)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const handleDelete = async (id) => {
    setDeleting(id)
    try {
      await deleteHistoryRun(id)
      setRuns(r => r.filter(x => x.id !== id))
    } catch (e) {
      setError(e.message)
    } finally {
      setDeleting(null)
    }
  }

  const handleClear = async () => {
    if (!window.confirm('Delete all optimization history?')) return
    try {
      await clearHistory()
      setRuns([])
    } catch (e) {
      setError(e.message)
    }
  }

  const fmt = (n) =>
    n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(2)}M` : `$${(n / 1_000).toFixed(1)}K`

  const fmtDate = (iso) =>
    new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    })

  return (
    <div>
      <div className="flex items-start justify-between mb-8">
        <PageHeader
          title="Optimization History"
          subtitle={`${runs.length} saved run${runs.length !== 1 ? 's' : ''}`}
        />
        <div className="flex gap-2 mt-1">
          <button
            onClick={load}
            className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium px-3 py-2 rounded-lg text-sm transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
          {runs.length > 0 && (
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 font-medium px-3 py-2 rounded-lg text-sm transition-colors"
            >
              <Trash2 size={14} /> Clear All
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-4">
          {error}
        </p>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm">Loading history…</div>
      ) : runs.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
          <p className="text-gray-500 text-sm">No optimization runs yet.</p>
          <p className="text-gray-600 text-xs mt-1">Head to the Optimizer to get started.</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/60 border-b border-gray-800">
                <tr>
                  {['#', 'Product', 'Category', 'Current Price', 'Optimal Price', 'Uplift', 'Revenue', 'Date', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((r, i) => (
                  <tr
                    key={r.id}
                    className={clsx(
                      'border-b border-gray-800/50 transition-colors',
                      i % 2 === 0 ? 'bg-transparent' : 'bg-gray-800/20',
                      'hover:bg-gray-800/40'
                    )}
                  >
                    <td className="px-4 py-3 text-gray-600 font-mono text-xs">{r.id}</td>
                    <td className="px-4 py-3 font-semibold text-white">{r.product_id}</td>
                    <td className="px-4 py-3 text-gray-400">{r.category}</td>
                    <td className="px-4 py-3 text-gray-300">${r.current_price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-green-400 font-medium">${r.optimal_price.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      <span className={clsx(
                        'font-medium',
                        r.expected_revenue_increase_pct >= 0 ? 'text-green-400' : 'text-red-400'
                      )}>
                        {r.expected_revenue_increase_pct >= 0 ? '+' : ''}
                        {r.expected_revenue_increase_pct.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{fmt(r.current_revenue)}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {r.created_at ? fmtDate(r.created_at) : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDelete(r.id)}
                        disabled={deleting === r.id}
                        className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
