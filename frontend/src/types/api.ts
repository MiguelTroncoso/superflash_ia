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

export type ApiChannelType = 'permanent' | 'event' | 'temporary' | 'scheduled' | 'archived'

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
  avg_disk_percent: number | null
  channel_count: number
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
  history: Array<{
    collected_at: string
    avg_cpu_percent: number | null
    avg_memory_percent: number | null
    avg_disk_percent: number | null
    total_input_mbps: number
    total_output_mbps: number
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

export interface ServerListItem extends ServerResponse {
  latest_metric: ServerMetricResponse | null
  network_utilization_percent: number | null
  active_alert_count: number
  last_updated_at: string | null
}

export interface ServerPageResponse {
  items: ServerListItem[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ChannelResponse {
  id: number
  source_id: string
  external_id: string
  name: string
  category: string | null
  category_id: string | null
  category_name: string | null
  channel_type: ApiChannelType
  event_start_at: string | null
  event_end_at: string | null
  first_seen_at: string
  last_seen_at: string
  active: boolean
  inactive_since_at: string | null
  archived_at: string | null
  source_updated_at: string | null
  current_server_id: number | null
  event_id: number | null
  technical_stream_id: number | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ChannelMetricResponse {
  id: number
  channel_id: number
  event_id: number | null
  technical_stream_id: number | null
  server_id: number | null
  collected_at: string
  viewers: number
  bitrate_mbps: number | null
  estimated_output_mbps: number | null
  status: 'online' | 'degraded' | 'offline' | 'unknown'
}

export interface ChannelListItem extends ChannelResponse {
  current_server_name: string | null
  event_external_id: string | null
  event_name: string | null
  technical_stream_external_id: string | null
  technical_stream_name: string | null
  latest_metric: ChannelMetricResponse | null
  viewers: number | null
  bitrate_mbps: number | null
  estimated_output_mbps: number | null
  status: 'online' | 'degraded' | 'offline' | 'unknown' | null
  last_updated_at: string | null
}

export interface ChannelPageResponse {
  items: ChannelListItem[]
  page: number
  page_size: number
  total: number
  total_pages: number
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
  channels_created?: number
  channels_updated?: number
  channels_reactivated?: number
  channels_deactivated?: number
  channels_archived?: number
  channels_unchanged?: number
  channels_failed?: number
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
