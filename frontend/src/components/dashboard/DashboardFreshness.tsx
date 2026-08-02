import { RefreshCw } from 'lucide-react'
import { formatDateTime } from '../../utils/formatters'

interface DashboardFreshnessProps {
  isFetching: boolean
  isStale: boolean
  lastUpdatedAt: number
  onRefresh: () => void
}

export function DashboardFreshness({
  isFetching,
  isStale,
  lastUpdatedAt,
  onRefresh,
}: DashboardFreshnessProps): React.JSX.Element {
  const updatedAt = lastUpdatedAt > 0 ? new Date(lastUpdatedAt).toISOString() : null

  return (
    <div className="mb-5 flex flex-col gap-3 rounded-xl border border-line bg-panel/60 px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
      <p className={isStale ? 'text-warning' : 'text-muted'}>
        {isStale ? 'Data may be stale' : 'Live API data'}
        {updatedAt ? ` · Last updated ${formatDateTime(updatedAt)}` : ''}
      </p>
      <button
        type="button"
        onClick={onRefresh}
        disabled={isFetching}
        className="inline-flex items-center gap-2 self-start rounded-lg border border-line bg-panel-raised px-3 py-2 font-semibold text-copy transition hover:border-slate-600 disabled:cursor-wait disabled:opacity-60 sm:self-auto"
      >
        <RefreshCw className={isFetching ? 'animate-spin' : ''} size={13} />
        {isFetching ? 'Refreshing…' : 'Refresh data'}
      </button>
    </div>
  )
}
