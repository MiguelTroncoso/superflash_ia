import type {
  AlertResponse,
  AlertsResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerMetricResponse,
  ServerResponse,
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

function average(values: Array<number | null>): number | null {
  const validValues = values.filter((value): value is number => value !== null)
  if (validValues.length === 0) return null
  return validValues.reduce((total, value) => total + value, 0) / validValues.length
}

function serverState(
  metric: ServerMetricResponse | undefined,
  serverAlerts: AlertResponse[],
): Pick<DashboardServerRow, 'state' | 'stateLabel'> {
  if (!metric) return { state: 'warning', stateLabel: 'No sample' }
  if (serverAlerts.length > 0) return { state: 'warning', stateLabel: 'Attention' }
  return { state: 'healthy', stateLabel: 'Healthy' }
}

export function mapServerRows(
  servers: ServerResponse[],
  latestMetrics: ReadonlyMap<number, ServerMetricResponse | undefined>,
  alerts: AlertsResponse,
): DashboardServerRow[] {
  return servers
    .filter((server) => server.enabled)
    .map((server) => {
      const metric = latestMetrics.get(server.id)
      const serverAlerts = alerts.alerts.filter((alert) => alert.server_id === server.id)
      const state = serverState(metric, serverAlerts)

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
        ...state,
      }
    })
}

export function buildDashboardSummary(
  overview: OverviewResponse,
  channels: { length: number },
  rows: DashboardServerRow[],
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
    channelCount: channels.length,
    avgCpuPercent: overview.avg_cpu_percent,
    avgMemoryPercent: overview.avg_memory_percent,
    avgDiskPercent: average(rows.map((row) => row.diskPercent)),
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
  histories: ReadonlyMap<number, ServerMetricResponse[]>,
): DashboardHistoryPoint[] {
  const buckets = new Map<string, ServerMetricResponse[]>()
  histories.forEach((metrics) => {
    metrics.forEach((metric) => {
      const bucket = buckets.get(metric.collected_at) ?? []
      bucket.push(metric)
      buckets.set(metric.collected_at, bucket)
    })
  })

  return [...buckets.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([timestamp, metrics]) => ({
      time: new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      cpu: average(metrics.map((metric) => metric.cpu_percent)) ?? 0,
      memory: average(metrics.map((metric) => metric.memory_percent)) ?? 0,
      inbound: round(metrics.reduce((total, metric) => total + metric.input_mbps, 0)),
      outbound: round(metrics.reduce((total, metric) => total + metric.output_mbps, 0)),
    }))
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}
