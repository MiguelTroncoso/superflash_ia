import { describe, expect, it } from 'vitest'
import { buildDashboardSummary, mapServerRows } from './dashboardMetrics'
import type { AlertsResponse, HealthResponse, OverviewResponse, ServerResponse } from '../types/api'

const server: ServerResponse = {
  id: 1,
  external_id: 'sf-core-01',
  name: 'sf-core-01',
  hostname: 'core-a',
  role: 'main',
  provider: 'Acme',
  datacenter: 'SCL-1',
  group: 'live',
  tags: [],
  type: 'bare-metal',
  country: 'CL',
  network_capacity_mbps: 1000,
  network_speed_mbps: 1000,
  prometheus_configured: false,
  heartbeat_interval_seconds: 300,
  last_heartbeat_at: null,
  status: 'online',
  notes: null,
  enabled: true,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

const overview: OverviewResponse = {
  generated_at: '2026-08-01T10:00:00Z',
  enabled_servers: 1,
  total_active_connections: 12,
  total_output_mbps: 140,
  total_input_mbps: 22,
  avg_cpu_percent: 62,
  avg_memory_percent: 71,
  avg_disk_percent: null,
  channel_count: 3,
  top_output_server: { server_id: 1, name: server.name, output_mbps: 140 },
  server_network_utilization: [],
  top_channels: [],
  history: [],
}

const alerts: AlertsResponse = {
  generated_at: '2026-08-01T10:00:00Z',
  alerts: [
    {
      id: 1,
      type: 'high_cpu',
      severity: 'critical',
      status: 'active',
      server_id: 1,
      server_name: server.name,
      message: 'CPU high',
      value: 92,
      threshold: 85,
      collected_at: '2026-08-01T10:00:00Z',
      first_seen_at: '2026-08-01T10:00:00Z',
      last_seen_at: '2026-08-01T10:00:00Z',
      acknowledged_at: null,
      resolved_at: null,
    },
  ],
}

const health: HealthResponse = { status: 'ok', database: 'ok', version: '0.1.0' }

describe('dashboardMetrics', () => {
  it('maps latest API metrics and marks alerted servers', () => {
    const rows = mapServerRows([{ ...server, latest_metric: {
      id: 11,
      server_id: 1,
      collected_at: '2026-08-01T10:00:00Z',
      cpu_percent: 92,
      memory_percent: 71,
      disk_percent: 44,
      filesystem_percent: 44,
      swap_percent: 18,
      input_mbps: 22,
      output_mbps: 140,
      io_read_mbps: 42,
      io_write_mbps: 21,
      load_average_1m: 1.2,
      load_average_5m: 1,
      load_average_15m: 0.8,
      active_connections: 12,
      active_streams: 3,
      uptime_seconds: 100,
      source: 'mock',
    }, network_utilization_percent: 14, active_alert_count: 1, last_updated_at: '2026-08-01T10:00:00Z' }], alerts)

    expect(rows[0]).toMatchObject({
      name: 'sf-core-01',
      cpuPercent: 92,
      diskPercent: 44,
      state: 'warning',
      stateLabel: 'Attention',
    })
  })

  it('derives summary values without inventing disk data', () => {
    const rows = mapServerRows([{ ...server, latest_metric: null, network_utilization_percent: null, active_alert_count: 0, last_updated_at: server.updated_at }], { generated_at: '', alerts: [] })
    const collectionStatus = {
      running: false,
      run_id: 2,
      source: 'mock',
      triggered_by: 'scheduler' as const,
      started_at: '2026-08-01T09:59:00Z',
      heartbeat_at: '2026-08-01T09:59:05Z',
      finished_at: '2026-08-01T10:00:00Z',
      duration_ms: 1000,
      status: 'success' as const,
      inserted: 1,
      skipped: 0,
      errors: [],
      next_run_at: null,
    }

    const summary = buildDashboardSummary(
      overview,
      { generated_at: '', alerts: [] },
      health,
      collectionStatus,
    )

    expect(summary).toMatchObject({
      serverCount: 1,
      channelCount: 3,
      avgCpuPercent: 62,
      avgMemoryPercent: 71,
      avgDiskPercent: null,
      totalInputMbps: 22,
      totalOutputMbps: 140,
      alertCount: 0,
      generalState: 'healthy',
    })
  })

  it('degrades the general status when active alerts exist', () => {
    const summary = buildDashboardSummary(
      overview,
      alerts,
      health,
      {
        running: false,
        run_id: null,
        source: null,
        triggered_by: null,
        started_at: null,
        heartbeat_at: null,
        finished_at: null,
        duration_ms: null,
        status: 'success',
        errors: [],
        inserted: 1,
        skipped: 0,
        next_run_at: null,
      },
    )

    expect(summary.generalState).toBe('warning')
    expect(summary.generalLabel).toBe('Degraded')
  })
})
