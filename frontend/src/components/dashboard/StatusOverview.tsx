import { Activity, ArrowUpRight, CircleAlert, CircleCheck, Clock3 } from 'lucide-react'
import { Surface } from '../common/Surface'
import { StatusBadge } from '../common/StatusBadge'
import type { CollectionStatusResponse, HealthResponse } from '../../types/api'
import type { DashboardSummary } from '../../utils/dashboardMetrics'

interface StatusOverviewProps {
  health: HealthResponse
  collectionStatus: CollectionStatusResponse
  summary: DashboardSummary
}

export function StatusOverview({
  health,
  collectionStatus,
  summary,
}: StatusOverviewProps): React.JSX.Element {
  const isHealthy = summary.generalState === 'healthy'

  return (
    <Surface className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-copy">General status</p>
          <p className="mt-1 text-xs text-muted">Read-only API health snapshot</p>
        </div>
        <StatusBadge state={summary.generalState} label={summary.generalLabel} />
      </div>

      <div className="mt-7 space-y-4">
        <div className="flex items-center gap-2 text-xs text-muted">
          {isHealthy ? (
            <CircleCheck size={15} className="text-success" />
          ) : (
            <CircleAlert size={15} className="text-warning" />
          )}
          API health: {health.status} · database: {health.database}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <Clock3 size={15} className="text-brand" /> {summary.collectionLabel}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <Activity size={15} className="text-violet-300" />
          {collectionStatus.next_run_at
            ? `Next scheduler cycle ${new Date(collectionStatus.next_run_at).toLocaleString()}`
            : 'Scheduler next cycle unavailable'}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between border-t border-line pt-4 text-xs">
        <span className="text-muted">Source: {collectionStatus.source ?? 'unknown'}</span>
        <ArrowUpRight size={15} className="text-brand" />
      </div>
    </Surface>
  )
}
