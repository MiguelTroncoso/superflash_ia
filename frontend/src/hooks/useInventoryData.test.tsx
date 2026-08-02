import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '../services/httpClient'
import { useChannelsData } from './useChannelsData'
import { useServersData } from './useServersData'

function wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('aggregated inventory hooks', () => {
  afterEach(() => vi.restoreAllMocks())

  it('loads server rows and latest metrics with one HTTP request', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({
      data: {
        items: [{
          id: 1,
          external_id: 'srv-1',
          name: 'Server 1',
          hostname: null,
          role: 'live',
          provider: null,
          datacenter: null,
          group: null,
          tags: [],
          type: null,
          country: null,
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
          latest_metric: null,
          network_utilization_percent: null,
          active_alert_count: 0,
          last_updated_at: null,
        }],
        page: 1,
        page_size: 50,
        total: 1,
        total_pages: 1,
      },
    } as never)

    const { result } = renderHook(() => useServersData({ page: 1, page_size: 50 }), { wrapper })

    await waitFor(() => expect(result.current.rows).toHaveLength(1))
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0]?.[0]).toBe('/api/v1/servers')
    expect(get.mock.calls.some(([path]) => String(path).includes('/metrics'))).toBe(false)
  })

  it('loads channel rows and latest samples with one HTTP request', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({
      data: {
        items: [{
          id: 1,
          external_id: 'ch-1',
          name: 'News',
          category: 'news',
          current_server_id: 1,
          enabled: true,
          created_at: '2026-08-01T10:00:00Z',
          updated_at: '2026-08-01T10:00:00Z',
          current_server_name: 'Server 1',
          latest_metric: null,
          viewers: null,
          bitrate_mbps: null,
          estimated_output_mbps: null,
          status: null,
          last_updated_at: null,
        }],
        page: 1,
        page_size: 50,
        total: 1,
        total_pages: 1,
      },
    } as never)

    const { result } = renderHook(() => useChannelsData({ page: 1, page_size: 50 }), { wrapper })

    await waitFor(() => expect(result.current.rows).toHaveLength(1))
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0]?.[0]).toBe('/api/v1/channels')
    expect(get.mock.calls.some(([path]) => String(path).includes('/metrics'))).toBe(false)
  })
})
