import clsx from 'clsx'

export default function KpiCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue:   'bg-blue-500/10 text-blue-400',
    green:  'bg-green-500/10 text-green-400',
    amber:  'bg-amber-500/10 text-amber-400',
    purple: 'bg-purple-500/10 text-purple-400',
    red:    'bg-red-500/10 text-red-400',
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-start gap-4">
      {Icon && (
        <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0', colorMap[color])}>
          <Icon size={20} />
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{title}</p>
        <p className="text-2xl font-bold text-white mt-1 truncate">{value}</p>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </div>
    </div>
  )
}
