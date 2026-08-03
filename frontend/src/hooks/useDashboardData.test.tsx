import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '../services/httpClient'
import { useDashboardData } from './useDashboardData'
import type { ServerListItem, ServerMetricResponse } from '../types/api'

const server: ServerListItem = {
  id: 1,
  external_id: 'sf-core-01',
  name: 'sf-core-01',
  hostname: 'core-a',
  role: 'main' as const,
  provider: null,
  datacenter: null,
  group: null,
  tags: [],
  type: null,
  country: null,
  network_capacity_mbps: 1000,
  network_speed_mbps: 1000,
  operational_network_limit_mbps: null,
  recommended_network_limit_mbps: null,
  minimum_network_reserve_mbps: null,
  candidate_for_replacement: false,
  prometheus_configured: false,
  heartbeat_interval_seconds: 300,
  last_heartbeat_at: null,
  status: 'online',
  notes: null,
  enabled: true,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
  latest_metric: null,
  network_utilization_percent: null,
  active_alert_count: 0,
  last_updated_at: null,
}

const metric: ServerMetricResponse = {
  id: 11,
  server_id: 1,
  collected_at: '2026-08-01T10:00:00Z',
  cpu_percent: 62,
  memory_percent: 71,
  disk_percent: 44,
  filesystem_percent: 44,
  swap_percent: 10,
  input_mbps: 22,
  output_mbps: 140,
  io_read_mbps: 1,
  io_write_mbps: 1,
  load_average_1m: 1,
  load_average_5m: 1,
  load_average_15m: 1,
  active_connections: 12,
  active_streams: 3,
  uptime_seconds: 100,
  source: 'mock',
}

function wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useDashboardData', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('maps API-shaped HTTP responses into live dashboard data', async () => {
    const responses: Record<string, unknown> = {
      '/api/v1/overview': {
        generated_at: '2026-08-01T10:00:00Z',
        enabled_servers: 1,
        total_active_connections: 12,
        total_output_mbps: 140,
        total_input_mbps: 22,
        avg_cpu_percent: 62,
        avg_memory_percent: 71,
        avg_disk_percent: 44,
        channel_count: 0,
        top_output_server: { server_id: 1, name: server.name, output_mbps: 140 },
        server_network_utilization: [],
        top_channels: [],
        history: [],
      },
      '/api/v1/servers': {
        items: [{ ...server, latest_metric: metric, network_utilization_percent: 14, active_alert_count: 0, last_updated_at: metric.collected_at }],
        page: 1,
        page_size: 200,
        total: 1,
        total_pages: 1,
      },
      '/api/v1/alerts': { generated_at: '2026-08-01T10:00:00Z', alerts: [] },
      '/api/v1/collection/status': {
        running: false,
        run_id: 2,
        source: 'mock',
        triggered_by: 'scheduler',
        finished_at: '2026-08-01T10:00:00Z',
        status: 'success',
        inserted: 1,
        skipped: 0,
        errors: [],
        next_run_at: null,
      },
      '/health': { status: 'ok', database: 'ok', version: '0.1.0' },
    }
    const get = vi.spyOn(httpClient, 'get').mockImplementation(async (path) => ({
      data: responses[String(path)],
    }) as never)

    const { result } = renderHook(() => useDashboardData(), { wrapper })

    await waitFor(() => expect(result.current.summary?.serverCount).toBe(1))

    expect(result.current.summary).toMatchObject({
      avgCpuPercent: 62,
      avgMemoryPercent: 71,
      avgDiskPercent: 44,
      totalInputMbps: 22,
      totalOutputMbps: 140,
    })
    expect(result.current.rows[0]).toMatchObject({
      name: 'sf-core-01',
      cpuPercent: 62,
      outputMbps: 140,
      state: 'healthy',
    })
    expect(get).toHaveBeenCalledWith('/api/v1/overview', undefined)
    expect(get.mock.calls.some(([path]) => String(path).includes('/metrics'))).toBe(false)
  })
})
