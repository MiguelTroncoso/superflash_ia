import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '../services/httpClient'
import { useDashboardData } from './useDashboardData'

const server = {
  id: 1,
  external_id: 'sf-core-01',
  name: 'sf-core-01',
  hostname: 'core-a',
  role: 'main' as const,
  network_capacity_mbps: 1000,
  enabled: true,
  created_at: '2026-08-01T10:00:00Z',
  updated_at: '2026-08-01T10:00:00Z',
}

const metric = {
  id: 11,
  server_id: 1,
  collected_at: '2026-08-01T10:00:00Z',
  cpu_percent: 62,
  memory_percent: 71,
  disk_percent: 44,
  input_mbps: 22,
  output_mbps: 140,
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
        top_output_server: { server_id: 1, name: server.name, output_mbps: 140 },
        server_network_utilization: [],
        top_channels: [],
      },
      '/api/v1/servers': [server],
      '/api/v1/channels': [],
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
      '/api/v1/servers/1/metrics': [metric],
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
  })
})
