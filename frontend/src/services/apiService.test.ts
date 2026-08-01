import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiService } from './apiService'
import { httpClient } from './httpClient'

describe('apiService', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('uses the read-only overview endpoint without sending credentials from the browser', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({
      data: { enabled_servers: 2 },
    } as never)

    await apiService.getOverview()

    expect(get).toHaveBeenCalledWith('/api/v1/overview', undefined)
    expect(get.mock.calls[0]?.[1]).not.toEqual(
      expect.objectContaining({ headers: expect.anything() }),
    )
  })

  it('requests only the latest server metric', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: [] } as never)

    await apiService.getServerMetrics(7)

    expect(get).toHaveBeenCalledWith('/api/v1/servers/7/metrics', { params: { limit: 1 } })
  })

  it('keeps resource services under the same-origin API prefix', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} } as never)

    await apiService.getServer(7)
    await apiService.getChannelMetrics(4, 24)
    await apiService.getBalance()
    await apiService.getRecommendations()

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/servers/7', undefined)
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/channels/4/metrics', { params: { limit: 24 } })
    expect(get).toHaveBeenNthCalledWith(3, '/api/v1/balance', undefined)
    expect(get).toHaveBeenNthCalledWith(4, '/api/v1/recommendations', undefined)
  })

  it('keeps health on the public endpoint outside /api/v1', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({
      data: { status: 'ok', database: 'ok', version: 'test' },
    } as never)

    await apiService.getHealth()

    expect(get).toHaveBeenCalledWith('/health', undefined)
  })
})
