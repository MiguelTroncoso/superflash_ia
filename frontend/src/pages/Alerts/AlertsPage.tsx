import { BellRing, ShieldAlert, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useAlertsData } from '../../hooks/useAlertsData'
import { usePageTitle } from '../../hooks/usePageTitle'
import type { ApiAlertStatus, ApiAlertSeverity } from '../../types/api'
import type { HealthState } from '../../types/monitoring'
import { formatDateTime, formatNullablePercent } from '../../utils/formatters'

type AlertFilter = 'all' | ApiAlertStatus

export function AlertsPage(): React.JSX.Element {
  usePageTitle('Alerts')
  const data = useAlertsData()
  const [filter, setFilter] = useState<AlertFilter>('all')
  const alerts = useMemo(
    () => data.alerts.filter((alert) => filter === 'all' || alert.status === filter),
    [data.alerts, filter],
  )

  if (data.isLoading) {
    return <DashboardState state="loading" message="Loading persisted alerts from the read-only API." />
  }
  if (data.isError) {
    return <DashboardState state="error" message="The alert center could not be loaded." onRetry={() => void data.refetch()} />
  }

  const critical = data.alerts.filter((alert) => alert.severity === 'critical').length
  const warning = data.alerts.filter((alert) => alert.severity === 'warning').length
  const acknowledged = data.alerts.filter((alert) => alert.status === 'acknowledged').length

  return (
    <>
      <PageHeader
        eyebrow="Signal center"
        title="Alerts"
        description="Persisted rule evaluations from the monitor API. This view does not execute infrastructure actions."
        action={<select aria-label="Filter alerts" value={filter} onChange={(event) => setFilter(event.target.value as AlertFilter)} className="rounded-xl border border-line bg-panel px-3 py-2.5 text-xs text-copy outline-none focus:border-brand"><option value="all">All statuses</option><option value="active">Active</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option></select>}
      />
      <DashboardFreshness
        isFetching={data.isFetching}
        isStale={data.isStale}
        lastUpdatedAt={data.lastUpdatedAt}
        onRefresh={() => void data.refetch()}
      />
      <div className="grid gap-4 md:grid-cols-3">
        <SummaryCard label="Critical" value={critical} icon={ShieldAlert} tone="critical" />
        <SummaryCard label="Warning" value={warning} icon={TriangleAlert} tone="warning" />
        <SummaryCard label="Acknowledged" value={acknowledged} icon={BellRing} tone="healthy" />
      </div>
      <Surface className="mt-5 overflow-hidden">
        {alerts.length === 0 ? (
          <DashboardState state="empty" message="No persisted alerts match the selected filter." />
        ) : (
          <div className="divide-y divide-line/70">
            {alerts.map((alert) => (
              <div key={alert.id ?? `${alert.server_id}-${alert.type}`} className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                <span className={alert.severity === 'critical' ? 'rounded-xl bg-danger/10 p-3 text-danger' : 'rounded-xl bg-warning/10 p-3 text-warning'}><TriangleAlert size={21} /></span>
                <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-semibold text-copy">{alert.message}</h2><StatusBadge state={severityState(alert.severity)} label={alert.status} compact /></div><p className="mt-1 text-xs text-muted">{alert.server_name} · {alert.type} · {formatDateTime(alert.last_seen_at ?? alert.collected_at)}</p></div>
                <div className="text-left text-xs text-muted sm:text-right"><p>{alert.value === null || alert.threshold === null ? 'No threshold value' : `${formatNullablePercent(alert.value)} / ${formatNullablePercent(alert.threshold)}`}</p><p className="mt-1 uppercase tracking-wider">{alert.severity} · {alert.status}</p></div>
              </div>
            ))}
          </div>
        )}
      </Surface>
    </>
  )
}

function SummaryCard({ label, value, icon: Icon, tone }: { label: string; value: number; icon: typeof BellRing; tone: HealthState }): React.JSX.Element {
  const iconClass = tone === 'critical' ? 'bg-danger/10 text-danger' : tone === 'warning' ? 'bg-warning/10 text-warning' : 'bg-success/10 text-success'
  return <Surface className="flex items-center justify-between p-5"><div><p className="text-sm text-muted">{label}</p><p className="mt-3 text-3xl font-semibold text-copy">{value}</p></div><span className={`rounded-xl p-3 ${iconClass}`}><Icon size={22} /></span></Surface>
}

function severityState(severity: ApiAlertSeverity): HealthState {
  return severity === 'critical' ? 'critical' : severity === 'warning' ? 'warning' : 'healthy'
}
