import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  HardDrive,
  HeartPulse,
  MemoryStick,
  Network,
  Server,
  TriangleAlert,
  Workflow,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useServerDetailData } from '../../hooks/useServerDetailData'
import { formatDateTime, formatNullablePercent, formatNullableThroughput, formatUptime } from '../../utils/formatters'
import type { AlertResponse } from '../../types/api'
import type { HealthState } from '../../types/monitoring'

export function ServerDetailPage(): React.JSX.Element {
  usePageTitle('Server detail')
  const { serverId } = useParams()
  const id = Number(serverId)
  const data = useServerDetailData(Number.isInteger(id) ? id : 0)

  if (data.isLoading) {
    return <DashboardState state="loading" message="Loading server detail and read-only metrics." />
  }
  if (data.isError || !data.server) {
    return <DashboardState state="error" message="The server detail could not be loaded." onRetry={() => void data.refetch()} />
  }

  const latest = data.metrics[0] ?? null
  const state = serverState(data.server.status, data.alerts, latest !== null)

  return (
    <>
      <Link to="/servers" className="mb-5 inline-flex items-center gap-2 text-xs font-semibold text-muted hover:text-copy">
        <ArrowLeft size={14} /> Back to servers
      </Link>
      <PageHeader
        eyebrow="Infrastructure detail"
        title={data.server.name}
        description={`${data.server.hostname ?? data.server.external_id} · ${data.server.provider ?? 'Provider not configured'} · ${data.server.country ?? 'Country not configured'}`}
        action={<StatusBadge state={state} label={data.server.status} />}
      />
      <DashboardFreshness
        isFetching={data.isFetching}
        isStale={data.isStale}
        lastUpdatedAt={data.lastUpdatedAt}
        onRefresh={() => void data.refetch()}
      />
      {data.diagnostic && <DiagnosticPanel diagnostic={data.diagnostic} />}
      {data.isEmpty ? (
        <DashboardState state="empty" message="This server has no collected metric samples yet. No synthetic values are shown." />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="CPU" value={formatNullablePercent(latest?.cpu_percent ?? null)} icon={Activity} />
            <MetricCard label="RAM" value={formatNullablePercent(latest?.memory_percent ?? null)} icon={MemoryStick} />
            <MetricCard label="Disk" value={formatNullablePercent(latest?.disk_percent ?? null)} icon={HardDrive} />
            <MetricCard label="Network out" value={formatNullableThroughput(latest?.output_mbps ?? null)} icon={Network} />
          </div>
          <div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
            <Surface className="p-5">
              <h2 className="text-sm font-semibold text-copy">Current infrastructure signals</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <DetailValue label="Filesystem" value={formatNullablePercent(latest?.filesystem_percent ?? null)} />
                <DetailValue label="Swap" value={formatNullablePercent(latest?.swap_percent ?? null)} />
                <DetailValue label="IO read / write" value={`${formatNullableThroughput(latest?.io_read_mbps ?? null)} / ${formatNullableThroughput(latest?.io_write_mbps ?? null)}`} />
                <DetailValue label="Load average" value={`${formatNullableNumber(latest?.load_average_1m)} / ${formatNullableNumber(latest?.load_average_5m)} / ${formatNullableNumber(latest?.load_average_15m)}`} />
                <DetailValue label="Network in / out" value={`${formatNullableThroughput(latest?.input_mbps ?? null)} / ${formatNullableThroughput(latest?.output_mbps ?? null)}`} />
                <DetailValue label="Uptime" value={formatUptime(latest?.uptime_seconds ?? null)} />
              </div>
            </Surface>
            <Surface className="p-5">
              <h2 className="text-sm font-semibold text-copy">Collection and heartbeat</h2>
              <div className="mt-5 space-y-4">
                <DetailRow icon={Clock3} label="Last collection" value={formatDateTime(data.collectionStatus?.finished_at ?? latest?.collected_at ?? null)} />
                <DetailRow icon={HeartPulse} label="Heartbeat" value={formatDateTime(data.server.last_heartbeat_at)} />
                <DetailRow icon={Workflow} label="Collection source" value={data.collectionStatus?.source ?? latest?.source ?? 'No data'} />
                <DetailRow icon={Server} label="Prometheus" value={data.server.prometheus_configured ? 'Configured' : 'Not configured'} />
              </div>
            </Surface>
          </div>
          <Surface className="mt-5 overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <h2 className="text-sm font-semibold text-copy">Active alerts</h2>
              <span className="text-xs text-muted">{data.alerts.filter((alert) => alert.status !== 'resolved').length} open</span>
            </div>
            {data.alerts.length === 0 ? (
              <p className="p-6 text-sm text-muted">No persisted alerts for this server.</p>
            ) : (
              <div className="divide-y divide-line/70">
                {data.alerts.map((alert) => (
                  <div key={alert.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
                    <TriangleAlert className={alert.severity === 'critical' ? 'text-danger' : 'text-warning'} size={18} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-copy">{alert.message}</p>
                      <p className="mt-1 text-xs text-muted">{alert.type} · {formatDateTime(alert.last_seen_at ?? alert.collected_at)}</p>
                    </div>
                    <span className="text-xs uppercase tracking-wider text-muted">{alert.status}</span>
                  </div>
                ))}
              </div>
            )}
          </Surface>
          <Surface className="mt-5 overflow-hidden">
            <div className="border-b border-line px-5 py-4">
              <h2 className="text-sm font-semibold text-copy">Recent samples</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-xs">
                <thead className="border-b border-line bg-panel-raised/40 text-[10px] uppercase tracking-wider text-muted">
                  <tr><th className="px-5 py-3">Collected</th><th className="px-5 py-3">CPU</th><th className="px-5 py-3">RAM</th><th className="px-5 py-3">Disk</th><th className="px-5 py-3">Network out</th><th className="px-5 py-3">Load</th></tr>
                </thead>
                <tbody className="divide-y divide-line/70">
                  {data.metrics.slice(0, 10).map((metric) => (
                    <tr key={metric.id}><td className="px-5 py-3 text-muted">{formatDateTime(metric.collected_at)}</td><td className="px-5 py-3 text-copy">{formatNullablePercent(metric.cpu_percent)}</td><td className="px-5 py-3 text-copy">{formatNullablePercent(metric.memory_percent)}</td><td className="px-5 py-3 text-copy">{formatNullablePercent(metric.disk_percent)}</td><td className="px-5 py-3 text-copy">{formatNullableThroughput(metric.output_mbps)}</td><td className="px-5 py-3 text-copy">{formatNullableNumber(metric.load_average_1m)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Surface>
        </>
      )}
    </>
  )
}

function DiagnosticPanel({ diagnostic }: { diagnostic: NonNullable<ReturnType<typeof useServerDetailData>['diagnostic']> }): React.JSX.Element {
  const check = (label: string, status: string, message: string): React.JSX.Element => (
    <div className="flex items-start gap-3 rounded-xl border border-line bg-panel-raised/40 p-4">
      {status === 'ok' ? <CheckCircle2 className="mt-0.5 shrink-0 text-success" size={16} /> : <TriangleAlert className="mt-0.5 shrink-0 text-warning" size={16} />}
      <div><p className="text-xs font-semibold text-copy">{label} · {status.replace('_', ' ')}</p><p className="mt-1 text-xs text-muted">{message}</p></div>
    </div>
  )

  return (
    <Surface className="mb-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-sm font-semibold text-copy">Production connection</h2><p className="mt-1 text-xs text-muted">Read-only diagnostic; no external action is executed.</p></div>
        <StatusBadge state={diagnostic.status === 'ok' ? 'healthy' : diagnostic.status === 'not_configured' ? 'warning' : 'critical'} label={diagnostic.status.replace('_', ' ')} />
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {check('Prometheus', diagnostic.prometheus.status, diagnostic.prometheus.message)}
        {check('Node Exporter', diagnostic.node_exporter.status, diagnostic.node_exporter.message)}
        {diagnostic.firewall && check('Firewall path', diagnostic.firewall.status, diagnostic.firewall.message)}
      </div>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted">
        <span>Latency: {diagnostic.latency_ms === null ? '—' : `${diagnostic.latency_ms.toFixed(1)} ms`}</span>
        <span>Last scrape: {formatDateTime(diagnostic.last_scrape_at ?? diagnostic.last_sample_at)}</span>
        <span>Node Exporter: {diagnostic.node_exporter_version ?? 'unknown version'}</span>
      </div>
      {diagnostic.errors.length > 0 && <p className="mt-3 text-xs text-warning">{diagnostic.errors.join(' · ')}</p>}
    </Surface>
  )
}

function MetricCard({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }): React.JSX.Element {
  return <Surface className="p-5"><div className="flex items-center justify-between"><p className="text-sm text-muted">{label}</p><Icon className="text-brand" size={18} /></div><p className="mt-4 text-2xl font-semibold text-copy">{value}</p></Surface>
}

function DetailValue({ label, value }: { label: string; value: string }): React.JSX.Element {
  return <div className="rounded-xl border border-line bg-panel-raised/40 p-4"><p className="text-xs text-muted">{label}</p><p className="mt-2 text-sm font-semibold text-copy">{value}</p></div>
}

function DetailRow({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }): React.JSX.Element {
  return <div className="flex items-center gap-3"><Icon className="shrink-0 text-brand" size={16} /><div className="min-w-0"><p className="text-xs text-muted">{label}</p><p className="mt-1 truncate text-sm text-copy">{value}</p></div></div>
}

function formatNullableNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toFixed(2)
}

function serverState(status: string, alerts: AlertResponse[], hasMetrics: boolean): HealthState {
  if (alerts.some((alert) => alert.severity === 'critical' && alert.status !== 'resolved')) return 'critical'
  if (alerts.some((alert) => alert.status !== 'resolved') || status === 'degraded' || status === 'maintenance') return 'warning'
  if (status === 'offline' || !hasMetrics) return 'critical'
  return 'healthy'
}
