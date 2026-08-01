export type ApiHealthStatus = 'ok' | 'degraded'

export type ApiServerRole = 'main' | 'live' | 'vod' | 'other'

export type ApiAlertType =
  | 'high_cpu'
  | 'high_memory'
  | 'high_disk'
  | 'high_network_utilization'
  | 'stale_server'

export type ApiCollectionStatus = 'running' | 'success' | 'error'

export type ApiCollectionTrigger = 'manual' | 'scheduler'

export interface HealthResponse {
  status: ApiHealthStatus
  database: 'ok' | 'error'
  version: string
}

export interface OverviewResponse {
  generated_at: string
  enabled_servers: number
  total_active_connections: number
  total_output_mbps: number
  total_input_mbps: number
  avg_cpu_percent: number | null
  avg_memory_percent: number | null
  top_output_server: {
    server_id: number
    name: string
    output_mbps: number
  } | null
  server_network_utilization: Array<{
    server_id: number
    name: string
    output_mbps: number
    network_capacity_mbps: number | null
    utilization_percent: number | null
  }>
  top_channels: Array<{
    channel_id: number
    name: string
    viewers: number
    collected_at: string
  }>
}

export interface ServerResponse {
  id: number
  external_id: string
  name: string
  hostname: string | null
  role: ApiServerRole
  network_capacity_mbps: number | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ServerMetricResponse {
  id: number
  server_id: number
  collected_at: string
  cpu_percent: number
  memory_percent: number
  disk_percent: number | null
  input_mbps: number
  output_mbps: number
  active_connections: number
  active_streams: number
  uptime_seconds: number | null
  source: string
}

export interface ChannelResponse {
  id: number
  external_id: string
  name: string
  category: string | null
  current_server_id: number | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AlertResponse {
  type: ApiAlertType
  server_id: number
  server_name: string
  message: string
  value: number | null
  threshold: number | null
  collected_at: string | null
}

export interface AlertsResponse {
  generated_at: string
  alerts: AlertResponse[]
}

export interface CollectionStatusResponse {
  running: boolean
  run_id: number | null
  source: string | null
  triggered_by: ApiCollectionTrigger | null
  started_at: string | null
  heartbeat_at: string | null
  finished_at: string | null
  duration_ms: number | null
  status: ApiCollectionStatus | null
  inserted: number
  skipped: number
  errors: string[]
  next_run_at: string | null
}
