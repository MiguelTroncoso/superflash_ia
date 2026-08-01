export type ApiHealthStatus = 'ok' | 'degraded'

export type ApiServerRole = 'main' | 'live' | 'vod' | 'other'

export type ApiAlertType =
  | 'high_cpu'
  | 'high_memory'
  | 'high_disk'
  | 'high_network_utilization'
  | 'stale_server'

export type ApiAlertSeverity = 'info' | 'warning' | 'critical'
export type ApiAlertStatus = 'active' | 'acknowledged' | 'resolved'

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
  provider: string | null
  datacenter: string | null
  group: string | null
  tags: string[]
  type: string | null
  country: string | null
  network_capacity_mbps: number | null
  network_speed_mbps: number | null
  prometheus_url: string | null
  prometheus_configured: boolean
  heartbeat_interval_seconds: number
  last_heartbeat_at: string | null
  status: 'online' | 'degraded' | 'offline' | 'unknown' | 'maintenance'
  notes: string | null
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
  filesystem_percent: number | null
  swap_percent: number | null
  input_mbps: number
  output_mbps: number
  io_read_mbps: number | null
  io_write_mbps: number | null
  load_average_1m: number | null
  load_average_5m: number | null
  load_average_15m: number | null
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
  id: number
  type: ApiAlertType
  severity: ApiAlertSeverity
  status: ApiAlertStatus
  server_id: number
  server_name: string
  message: string
  value: number | null
  threshold: number | null
  collected_at: string | null
  first_seen_at: string | null
  last_seen_at: string | null
  acknowledged_at: string | null
  resolved_at: string | null
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

export interface BalanceServerResponse {
  server_id: number
  name: string
  output_mbps: number
  capacity_mbps: number | null
  utilization_percent: number | null
}

export interface BalanceResponse {
  generated_at: string
  server_count: number
  sampled_server_count: number
  average_cpu_percent: number | null
  average_memory_percent: number | null
  average_network_mbps: number | null
  average_network_utilization_percent: number | null
  average_disk_percent: number | null
  capacity_total_mbps: number
  capacity_used_mbps: number
  capacity_free_mbps: number
  most_loaded: BalanceServerResponse | null
  least_utilized: BalanceServerResponse | null
  servers: BalanceServerResponse[]
}

export type RecommendationType =
  | 'high_cpu'
  | 'high_memory'
  | 'high_disk'
  | 'high_network'
  | 'heartbeat_lost'
  | 'no_data'
  | 'underutilized'

export interface RecommendationResponse {
  type: RecommendationType
  severity: ApiAlertSeverity
  server_id: number
  server_name: string
  title: string
  message: string
  value: number | null
  threshold: number | null
  generated_at: string
}

export interface RecommendationsResponse {
  generated_at: string
  recommendations: RecommendationResponse[]
}
