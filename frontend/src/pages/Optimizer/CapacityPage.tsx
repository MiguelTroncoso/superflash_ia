import { Activity, Network, Server, ShieldCheck } from 'lucide-react'
import { MetricCard } from '../../components/common/MetricCard'
import { PageHeader } from '../../components/common/PageHeader'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useCapacityData } from '../../hooks/useCapacityData'
import { usePageTitle } from '../../hooks/usePageTitle'
import type { CapacityState } from '../../types/api'
import { formatDateTime, formatNullablePercent, formatNullableThroughput } from '../../utils/formatters'

export function CapacityPage(): React.JSX.Element {
  usePageTitle('Optimizer · Capacity')
  const data = useCapacityData()

  if (data.isLoading) return <DashboardState state="loading" message="Loading configured capacity and latest samples." />
  if (data.isError || !data.capacity) return <DashboardState state="error" message="Capacity data could not be loaded. No simulated values are shown." onRetry={() => void data.refetch()} />
  const capacity = data.capacity
  if (capacity.server_count === 0) return <DashboardState state="empty" message="No enabled servers are available for capacity planning." />

  return (
    <>
      <PageHeader eyebrow="Optimizer" title="Capacity" description="Configured network limits compared with the latest observed output. Missing samples remain explicit." />
      <DashboardFreshness isFetching={data.isFetching} isStale={data.isStale} lastUpdatedAt={data.lastUpdatedAt} onRefresh={() => void data.refetch()} />
      {capacity.data_quality === 'insufficient_data' && <DataQualityNotice missing={capacity.missing_data.length} />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Physical capacity" value={formatNullableThroughput(capacity.total_physical_capacity_mbps)} detail="Configured inventory" icon={Server} tone="cyan" />
        <MetricCard label="Operational target" value={formatNullableThroughput(capacity.total_operational_limit_mbps)} detail="Per-server limits" icon={ShieldCheck} tone="emerald" />
        <MetricCard label="Observed load" value={formatNullableThroughput(capacity.total_observed_load_mbps)} detail="Latest output samples" icon={Activity} tone="amber" />
        <MetricCard label="Operational free" value={formatNullableThroughput(capacity.total_operational_free_mbps)} detail="Clamped at zero" icon={Network} tone="violet" />
      </div>
      <Surface className="mt-5 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div><h2 className="text-sm font-semibold text-copy">Server capacity view</h2><p className="mt-1 text-xs text-muted">{capacity.sampled_server_count}/{capacity.server_count} servers with latest samples.</p></div>
          <span className="text-xs text-muted">{formatDateTime(capacity.generated_at)}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted"><tr><th className="px-5 py-3">Server</th><th className="px-5 py-3">State</th><th className="px-5 py-3">Current</th><th className="px-5 py-3">P95</th><th className="px-5 py-3">Operational</th><th className="px-5 py-3">Headroom</th><th className="px-5 py-3">Samples</th><th className="px-5 py-3">Updated</th></tr></thead>
            <tbody className="divide-y divide-line/70">{capacity.servers.map((server) => <tr key={server.server_id}><td className="px-5 py-3"><p className="font-medium text-copy">{server.name}</p><p className="mt-1 text-[11px] text-muted">{server.provider ?? 'Provider not configured'}</p></td><td className="px-5 py-3"><CapacityStateBadge state={server.state} /></td><td className="px-5 py-3 text-copy">{formatNullableThroughput(server.observed_load_mbps)}</td><td className="px-5 py-3 text-copy">{formatNullableThroughput(server.p95_load_mbps ?? null)}</td><td className="px-5 py-3 text-muted">{formatNullablePercent(server.operational_utilization_percent)}</td><td className="px-5 py-3 text-copy">{formatNullableThroughput(server.headroom_mbps ?? null)}</td><td className="px-5 py-3 text-muted">{server.sample_count ?? 0}</td><td className="px-5 py-3 text-muted">{formatDateTime(server.last_collected_at)}</td></tr>)}</tbody>
          </table>
        </div>
      </Surface>
      <p className="mt-4 text-[11px] text-muted">This view is read-only. Capacity defaults are derived from each server configuration; no hardcoded server-type limits are applied.</p>
    </>
  )
}

function DataQualityNotice({ missing }: { missing: number }): React.JSX.Element {
  return <div className="mb-5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning">Preliminary capacity view: {missing} server(s) lack a metric or capacity configuration. No numbers are invented.</div>
}

function CapacityStateBadge({ state }: { state: CapacityState }): React.JSX.Element {
  const styles: Record<CapacityState, string> = { normal: 'bg-success/10 text-success', warning: 'bg-warning/10 text-warning', high: 'bg-warning/15 text-warning', critical: 'bg-danger/10 text-danger', no_data: 'bg-panel-raised text-muted' }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${styles[state]}`}>{state.replace('_', ' ')}</span>
}
