export type ApiHealthStatus = 'ok' | 'degraded'

export type ApiServerRole = 'main' | 'live' | 'vod' | 'other'
export type ApiServerLifecycleState = 'active' | 'archived' | 'deleted'

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
  server_profile?: 'critical' | 'replaceable' | 'shared'
  country: string | null
  network_capacity_mbps: number | null
  network_speed_mbps: number | null
  prometheus_configured: boolean
  ssh_host_key_fingerprint?: string | null
  ssh_management_configured?: boolean
  ssh_management_key_fingerprint?: string | null
  ssh_management_key_created_at?: string | null
  ssh_management_key_rotated_at?: string | null
  node_exporter_status?: string
  node_exporter_version?: string | null
  heartbeat_interval_seconds: number
  last_heartbeat_at: string | null
  status: 'online' | 'degraded' | 'offline' | 'unknown' | 'maintenance'
  lifecycle_state?: ApiServerLifecycleState
  archived_at?: string | null
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

export type OnboardingAuthMethod = 'password' | 'private_key'
export type OnboardingStatus =
  | 'pending'
  | 'connecting'
  | 'authenticating'
  | 'discovering'
  | 'installing_exporter'
  | 'configuring_firewall'
  | 'verifying_exporter'
  | 'registering_inventory'
  | 'configuring_monitoring'
  | 'validating'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rollback_required'

export interface OnboardingResponse {
  id: number
  server_id: number
  status: OnboardingStatus
  current_step: string
  progress_percent: number
  started_at: string | null
  completed_at: string | null
  failed_at: string | null
  last_error_code: string | null
  last_error_message_sanitized: string | null
  retry_count: number
  last_successful_step: string | null
  created_by: string
  auth_method: OnboardingAuthMethod
  ssh_port: number
  ssh_username: string
  cancel_requested: boolean
  created_at: string
  updated_at: string
}

export interface OnboardingActiveResponse extends OnboardingResponse {
  server_name: string
  server_hostname: string | null
}

export interface ServerRelationSummary {
  metrics: number
  alerts: number
  inventory_snapshots: number
  onboarding_jobs: number
  non_cancelled_onboarding_jobs: number
  onboarding_audit_events: number
  assigned_channels: number
  channel_metrics: number
  category_history: number
  cost_records: number
  simulation_records: number
}

export interface ServerDeletionImpact {
  server_id: number
  name: string
  hostname: string | null
  relations: ServerRelationSummary
  can_hard_delete: boolean
}

export interface ServerDeletionResponse extends ServerDeletionImpact {
  action: 'deleted' | 'archived'
  cancelled_onboarding_jobs: number
}

export interface OnboardingAuditResponse {
  id: number
  actor: string
  event: string
  step: string
  success: boolean
  detail_sanitized: string
  created_at: string
}

export interface OnboardingDiagnosisResponse {
  status: 'PASS' | 'PARTIAL' | 'FAIL'
  node_exporter: 'PASS' | 'PARTIAL' | 'FAIL'
  prometheus: 'PASS' | 'PARTIAL' | 'FAIL'
  firewall: 'PASS' | 'PARTIAL' | 'FAIL'
  network: 'PASS' | 'PARTIAL' | 'FAIL'
  prometheus_target_status?: 'UP' | 'PENDING_SCRAPE' | 'CONNECTION_FAILED' | string | null
  latency_ms: number | null
  last_sample: string | null
  errors: string[]
}

export interface OnboardingDiscoveryRequest {
  host: string
  port: number
  username: string
  auth_method: OnboardingAuthMethod
  password?: string
  private_key?: string
  host_key_fingerprint?: string
  confirm_host_key?: boolean
}

export interface OnboardingDiscoveryResponse {
  reachable: boolean
  authentication_ok: boolean
  privilege_ok: boolean
  discovered_inventory: Record<string, unknown> | null
  host_key_fingerprint: string | null
  host_key_status: string
  detected_firewall: string
  detected_interface: string | null
  link_speed_mbps: number | null
  exporter_status: string
  exporter_version: string | null
  port_9100_status: string
  systemd_available: boolean
  warnings: string[]
  blocking_errors: string[]
  error_code?: string | null
  error_message?: string | null
  probable_cause?: string | null
}

export interface OnboardingTestSSHRequest extends OnboardingDiscoveryRequest {}

export interface OnboardingTestSSHResponse {
  reachable: boolean
  authentication_ok: boolean
  privilege_ok: boolean
  temp_write_ok: boolean
  host_key_fingerprint: string | null
  host_key_status: string
  hostname: string | null
  os: string | null
  os_version: string | null
  architecture: string | null
  interfaces: Array<Record<string, unknown>>
  discovered_inventory: Record<string, unknown> | null
  error_code?: string | null
  error_message?: string | null
  probable_cause?: string | null
}

export interface OnboardingHealthResponse {
  onboarding_status: string
  ssh: string
  privilege: string
  node_exporter: string
  exporter_version: string | null
  firewall: string
  prometheus: string
  prometheus_target_status?: 'UP' | 'PENDING_SCRAPE' | 'CONNECTION_FAILED' | string | null
  inventory: string
  network_interface: string | null
  metrics_available: boolean
  last_scrape: string | null
  scrape_age_seconds: number | null
  freshness: string
  latency_ms: number | null
  overall_status: string
}

export type MaintenanceAction = 'diagnose' | 'repair' | 'update' | 'reinstall'

export interface MaintenanceResponse {
  action: MaintenanceAction
  status: string
  message: string
  exporter_status: string
  exporter_version: string | null
}

export interface OnboardingStartRequest {
  name: string
  ip: string
  ssh_port: number
  ssh_username: string
  host_key_fingerprint: string
  network_interface?: string
  auth_method: OnboardingAuthMethod
  password?: string
  private_key?: string
  provider?: string
  datacenter?: string
  country?: string
  server_type?: string
  server_profile?: 'critical' | 'replaceable' | 'shared'
  prometheus_url?: string
  physical_capacity_mbps?: number
  operational_target_mbps?: number
  recommended_max_mbps?: number
  minimum_reserve_mbps?: number
  monthly_cost?: number
  currency?: string
  next_payment_date?: string
  auto_renew?: boolean
  notes?: string
}
