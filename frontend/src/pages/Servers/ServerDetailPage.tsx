import {
  Activity,
  Archive,
  ArrowLeft,
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
import { useNavigate } from 'react-router'
import { useState } from 'react'
import { PageHeader } from '../../components/common/PageHeader'
import { StatusBadge } from '../../components/common/StatusBadge'
import { Surface } from '../../components/common/Surface'
import { DashboardFreshness } from '../../components/dashboard/DashboardFreshness'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { usePageTitle } from '../../hooks/usePageTitle'
import { useServerDetailData } from '../../hooks/useServerDetailData'
import { useServerOnboarding } from '../../hooks/useServerOnboarding'
import { ServerDeletionDialog } from '../../components/servers/ServerDeletionDialog'
import { formatDateTime, formatNullablePercent, formatNullableThroughput, formatUptime } from '../../utils/formatters'
import type { AlertResponse, MaintenanceAction } from '../../types/api'
import type { HealthState } from '../../types/monitoring'

export function ServerDetailPage(): React.JSX.Element {
  usePageTitle('Server detail')
  const { serverId } = useParams()
  const id = Number(serverId)
  const navigate = useNavigate()
  const data = useServerDetailData(Number.isInteger(id) ? id : 0)
  const maintenance = useServerOnboarding(null)
  const [maintenanceOpen, setMaintenanceOpen] = useState(false)
  const [authMethod, setAuthMethod] = useState<'private_key' | 'password'>('private_key')
  const [privateKey, setPrivateKey] = useState('')
  const [password, setPassword] = useState('')
  const [targetVersion, setTargetVersion] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)

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
        action={<div className="flex flex-wrap items-center gap-2"><StatusBadge state={state} label={data.server.status} /><button type="button" onClick={() => setDeleteOpen(true)} className="inline-flex items-center gap-2 rounded-xl border border-danger/40 px-3 py-2 text-xs font-semibold text-danger hover:bg-danger/10"><Archive size={14} />Archive / Delete</button></div>}
      />
      <DashboardFreshness
        isFetching={data.isFetching}
        isStale={data.isStale}
        lastUpdatedAt={data.lastUpdatedAt}
        onRefresh={() => void data.refetch()}
      />
      <Surface className="mt-5 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-sm font-semibold text-copy">Managed Node Exporter</h2><p className="mt-1 text-xs text-muted">Actions use a closed server-side catalog. No arbitrary commands or host reboot.</p></div>
          <button type="button" onClick={() => setMaintenanceOpen((value) => !value)} className="rounded-xl border border-line px-3 py-2 text-xs font-semibold text-copy">{maintenanceOpen ? 'Hide maintenance' : 'Diagnose / repair'}</button>
        </div>
        {maintenanceOpen && <MaintenanceForm authMethod={authMethod} setAuthMethod={setAuthMethod} privateKey={privateKey} setPrivateKey={setPrivateKey} password={password} setPassword={setPassword} targetVersion={targetVersion} setTargetVersion={setTargetVersion} busy={maintenance.maintenance.isPending} result={maintenance.maintenance.data?.message} error={Boolean(maintenance.maintenance.error)} onAction={(action) => { void runMaintenance(action) }} />}
      </Surface>
      {deleteOpen && <ServerDeletionDialog server={data.server} onClose={() => setDeleteOpen(false)} onDeleted={(result) => { setDeleteOpen(false); navigate('/servers', { replace: true, state: { notice: result.action === 'deleted' ? 'Server deleted.' : 'Server archived; history preserved.' } }) }} />}
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

  async function runMaintenance(action: MaintenanceAction): Promise<void> {
    await maintenance.maintenance.mutateAsync({
      serverId: id,
      action,
      payload: {
        auth_method: authMethod,
        password: authMethod === 'password' ? password : undefined,
        private_key: authMethod === 'private_key' ? privateKey : undefined,
        target_version: action === 'update' ? targetVersion || undefined : undefined,
      },
    })
  }
}

function MaintenanceForm({
  authMethod,
  setAuthMethod,
  privateKey,
  setPrivateKey,
  password,
  setPassword,
  targetVersion,
  setTargetVersion,
  busy,
  result,
  error,
  onAction,
}: {
  authMethod: 'private_key' | 'password'
  setAuthMethod: (value: 'private_key' | 'password') => void
  privateKey: string
  setPrivateKey: (value: string) => void
  password: string
  setPassword: (value: string) => void
  targetVersion: string
  setTargetVersion: (value: string) => void
  busy: boolean
  result: string | undefined
  error: boolean
  onAction: (action: MaintenanceAction) => void
}): React.JSX.Element {
  return <div className="mt-5 grid gap-3 sm:grid-cols-2"><label className="grid gap-2 text-xs text-muted">Authentication<select value={authMethod} onChange={(event) => setAuthMethod(event.target.value as 'private_key' | 'password')} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy"><option value="private_key">Private key</option><option value="password">Temporary password</option></select></label><label className="grid gap-2 text-xs text-muted">Target version (update only)<input value={targetVersion} onChange={(event) => setTargetVersion(event.target.value)} placeholder="1.8.2" className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy" /></label>{authMethod === 'private_key' ? <label className="grid gap-2 text-xs text-muted sm:col-span-2">Private key<textarea value={privateKey} onChange={(event) => setPrivateKey(event.target.value)} rows={4} className="rounded-xl border border-line bg-panel-raised p-3 font-mono text-xs text-copy" autoComplete="off" /></label> : <label className="grid gap-2 text-xs text-muted">Temporary password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="rounded-xl border border-line bg-panel-raised px-3 py-2.5 text-copy" autoComplete="new-password" /></label>}<div className="flex flex-wrap gap-2 sm:col-span-2">{(['diagnose', 'repair', 'update', 'reinstall'] as MaintenanceAction[]).map((action) => <button key={action} type="button" disabled={busy} onClick={() => onAction(action)} className="rounded-xl border border-line px-3 py-2 text-xs font-semibold text-copy disabled:opacity-50">{action}</button>)}</div>{result && <p className="rounded-xl border border-line bg-panel-raised p-3 text-xs text-muted sm:col-span-2">{result}</p>}{error && <p className="rounded-xl border border-danger/30 bg-danger/10 p-3 text-xs text-danger sm:col-span-2">The managed action failed without exposing remote details.</p>}</div>
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
