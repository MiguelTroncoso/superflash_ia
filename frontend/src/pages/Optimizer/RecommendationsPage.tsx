import { Lightbulb, RefreshCw } from 'lucide-react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useIntelligenceRecommendationsData } from '../../hooks/useIntelligenceRecommendationsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import type { ApiAlertSeverity } from '../../types/api'
import type { HealthState } from '../../types/monitoring'

export function RecommendationsPage(): React.JSX.Element {
  usePageTitle('Optimizer · Recommendations')
  const data = useIntelligenceRecommendationsData()
  if (data.isLoading) return <DashboardState state="loading" message="Evaluating explainable infrastructure rules." />
  if (data.isError) return <DashboardState state="error" message="Intelligence recommendations could not be loaded." onRetry={() => void data.refetch()} />

  return <><PageHeader eyebrow="Optimizer" title="Recommendations" description="Deterministic suggestions based on capacity, cost and data quality. No action is executed." /><DashboardFreshness isFetching={data.isFetching} isStale={data.isStale} lastUpdatedAt={data.lastUpdatedAt} onRefresh={() => void data.refetch()} />{data.dataQuality === 'insufficient_data' && <div className="mb-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning">Some recommendations have low confidence because metrics or capacity inputs are missing.</div>}<Surface className="overflow-hidden">{data.recommendations.length === 0 ? <DashboardState state="empty" message="No deterministic recommendation is active." /> : <div className="divide-y divide-line/70">{data.recommendations.map((recommendation, index) => <article key={`${recommendation.code}-${recommendation.server_id ?? 'global'}-${index}`} className="flex gap-4 p-5"><span className="rounded-xl bg-brand/10 p-3 text-brand"><Lightbulb size={19} /></span><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-semibold text-copy">{recommendation.title}</h2><StatusBadge state={severityState(recommendation.severity)} label={recommendation.severity} compact /></div><p className="mt-2 text-xs leading-5 text-muted">{recommendation.explanation}</p><p className="mt-2 text-xs leading-5 text-copy">Suggested: {recommendation.suggested_action}</p><p className="mt-2 text-[11px] text-muted">{recommendation.server_name ?? 'Global'} · confidence {(recommendation.confidence * 100).toFixed(0)}% · {recommendation.data_used.join(', ')}</p></div></article>)}</div>}</Surface><button type="button" onClick={() => void data.refetch()} className="mt-4 inline-flex items-center gap-2 text-xs font-semibold text-muted hover:text-copy"><RefreshCw size={14} />Retry evaluation</button></>
}

function severityState(severity: ApiAlertSeverity): HealthState { return severity === 'critical' ? 'critical' : severity === 'warning' ? 'warning' : 'healthy' }
