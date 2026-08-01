import { Lightbulb, TriangleAlert } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useRecommendationsData } from '../../hooks/useRecommendationsData'
import type { ApiAlertSeverity } from '../../types/api'
import type { HealthState } from '../../types/monitoring'
import { formatDateTime, formatNullablePercent } from '../../utils/formatters'

export function RecommendationsPage(): React.JSX.Element {
  usePageTitle('Recommendations')
  const data = useRecommendationsData()
  if (data.isLoading) return <DashboardState state="loading" message="Evaluating deterministic infrastructure rules." />
  if (data.isError) return <DashboardState state="error" message="Recommendations could not be loaded." onRetry={() => void data.refetch()} />

  return (
    <>
      <PageHeader eyebrow="Deterministic rules" title="Recommendations" description="Read-only recommendations derived from thresholds. No AI or infrastructure actions are executed." />
      <DashboardFreshness isFetching={data.isFetching} isStale={data.isStale} lastUpdatedAt={data.lastUpdatedAt} onRefresh={() => void data.refetch()} />
      <Surface className="overflow-hidden">
        {data.recommendations.length === 0 ? <DashboardState state="empty" message="No recommendation rules are currently triggered." /> : <div className="divide-y divide-line/70">{data.recommendations.map((recommendation) => <div key={`${recommendation.server_id}-${recommendation.type}`} className="flex flex-col gap-4 p-5 sm:flex-row sm:items-start"><span className="rounded-xl bg-brand/10 p-3 text-brand"><Lightbulb size={20} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-semibold text-copy">{recommendation.title}</h2><StatusBadge state={severityState(recommendation.severity)} label={recommendation.severity} compact /></div><p className="mt-2 text-xs leading-5 text-muted">{recommendation.server_name} · {recommendation.message}</p><p className="mt-2 text-[11px] text-muted">{recommendation.value === null ? 'No numeric sample' : `Observed ${formatNullablePercent(recommendation.value)}${recommendation.threshold === null ? '' : ` · threshold ${formatNullablePercent(recommendation.threshold)}`}`} · {formatDateTime(recommendation.generated_at)}</p></div><TriangleAlert className={recommendation.severity === 'critical' ? 'text-danger' : 'text-warning'} size={18} /></div>)}</div>}
      </Surface>
    </>
  )
}

function severityState(severity: ApiAlertSeverity): HealthState { return severity === 'critical' ? 'critical' : severity === 'warning' ? 'warning' : 'healthy' }
