import type {
  AlertsResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerListItem,
} from '../types/api'
import type { HealthState } from '../types/monitoring'

export interface DashboardServerRow {
  id: number
  name: string
  hostname: string | null
  role: string
  cpuPercent: number | null
  memoryPercent: number | null
  diskPercent: number | null
  inputMbps: number | null
  outputMbps: number | null
  collectedAt: string | null
  source: string | null
  state: HealthState
  stateLabel: string
}

export interface DashboardSummary {
  serverCount: number
  channelCount: number
  avgCpuPercent: number | null
  avgMemoryPercent: number | null
  avgDiskPercent: number | null
  totalInputMbps: number
  totalOutputMbps: number
  alertCount: number
  generalState: HealthState
  generalLabel: string
  collectionLabel: string
}

export interface DashboardHistoryPoint {
  time: string
  cpu: number
  memory: number
  inbound: number
  outbound: number
}

function serverState(server: ServerListItem, hasAlert: boolean): Pick<DashboardServerRow, 'state' | 'stateLabel'> {
  if (server.status === 'offline') return { state: 'critical', stateLabel: 'Offline' }
  if (hasAlert) return { state: 'warning', stateLabel: 'Attention' }
  if (!server.latest_metric) return { state: 'warning', stateLabel: 'No sample' }
  return { state: 'healthy', stateLabel: 'Healthy' }
}

export function mapServerRows(
  servers: ServerListItem[],
  alerts: AlertsResponse,
): DashboardServerRow[] {
  return servers
    .filter((server) => server.enabled)
    .map((server) => {
      const metric = server.latest_metric
      const hasAlert = server.active_alert_count > 0 || alerts.alerts.some((alert) => alert.server_id === server.id)
      const state = serverState(server, hasAlert)

      return {
        id: server.id,
        name: server.name,
        hostname: server.hostname,
        role: server.role,
        cpuPercent: metric?.cpu_percent ?? null,
        memoryPercent: metric?.memory_percent ?? null,
        diskPercent: metric?.disk_percent ?? null,
        inputMbps: metric?.input_mbps ?? null,
        outputMbps: metric?.output_mbps ?? null,
        collectedAt: metric?.collected_at ?? null,
        source: metric?.source ?? null,
        ...state,
      }
    })
}

export function buildDashboardSummary(
  overview: OverviewResponse,
  alerts: AlertsResponse,
  health: HealthResponse,
  collectionStatus: CollectionStatusResponse,
): DashboardSummary {
  const collectionTimestamp = collectionStatus.finished_at ?? collectionStatus.heartbeat_at
  const collectionLabel = collectionTimestamp
    ? `Last collection ${new Date(collectionTimestamp).toLocaleString()}`
    : 'No collection recorded'
  const generalState: HealthState =
    health.status === 'ok' && collectionStatus.status !== 'error' && alerts.alerts.length === 0
      ? 'healthy'
      : 'warning'

  return {
    serverCount: overview.enabled_servers,
    channelCount: overview.channel_count,
    avgCpuPercent: overview.avg_cpu_percent,
    avgMemoryPercent: overview.avg_memory_percent,
    avgDiskPercent: overview.avg_disk_percent,
    totalInputMbps: overview.total_input_mbps,
    totalOutputMbps: overview.total_output_mbps,
    alertCount: alerts.alerts.length,
    generalState,
    generalLabel: generalState === 'healthy' ? 'Healthy' : 'Degraded',
    collectionLabel,
  }
}

export function hasMetricSamples(rows: DashboardServerRow[]): boolean {
  return rows.some((row) => row.collectedAt !== null)
}

export function buildDashboardHistory(
  history: OverviewResponse['history'],
): DashboardHistoryPoint[] {
  return history.map((point) => ({
    time: new Date(point.collected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    cpu: point.avg_cpu_percent ?? 0,
    memory: point.avg_memory_percent ?? 0,
    inbound: round(point.total_input_mbps),
    outbound: round(point.total_output_mbps),
  }))
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}
