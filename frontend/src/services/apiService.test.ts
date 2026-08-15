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

  it('sends backend pagination, filters and ordering for inventory pages', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} } as never)

    await apiService.getServers({
      page: 2,
      page_size: 50,
      search: 'edge',
      sort_by: 'cpu',
      sort_order: 'desc',
      status: 'online',
    })
    await apiService.getChannels({
      page: 3,
      page_size: 50,
      search: 'news',
      sort_by: 'viewers',
      sort_order: 'desc',
      enabled: true,
    })

    expect(get).toHaveBeenNthCalledWith(1, '/api/v1/servers', {
      params: {
        page: 2,
        page_size: 50,
        search: 'edge',
        sort_by: 'cpu',
        sort_order: 'desc',
        status: 'online',
      },
    })
    expect(get).toHaveBeenNthCalledWith(2, '/api/v1/channels', {
      params: {
        page: 3,
        page_size: 50,
        search: 'news',
        sort_by: 'viewers',
        sort_order: 'desc',
        enabled: true,
      },
    })
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

  it('keeps discovery and maintenance under protected same-origin paths', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: {} } as never)
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} } as never)

    await apiService.discoverOnboarding({
      host: 'server.example',
      port: 22,
      username: 'root',
      auth_method: 'private_key',
      private_key: 'ephemeral-key',
      confirm_host_key: false,
    })
    await apiService.testSSHConnection({
      host: 'server.example',
      port: 22,
      username: 'root',
      auth_method: 'password',
      password: 'ephemeral-password',
      host_key_fingerprint: 'SHA256:test-fingerprint',
      confirm_host_key: true,
    })
    await apiService.getOnboardingHealth(12)
    await apiService.maintenance(12, 'repair', {
      auth_method: 'private_key',
      private_key: 'ephemeral-key',
    })

    expect(post).toHaveBeenNthCalledWith(1, '/api/v1/onboarding/discover', expect.anything())
    expect(get).toHaveBeenCalledWith('/api/v1/onboarding/12/health', undefined)
    expect(post).toHaveBeenNthCalledWith(2, '/api/v1/onboarding/test-ssh', expect.anything())
    expect(post).toHaveBeenNthCalledWith(3, '/api/v1/onboarding/server/12/maintenance/repair', expect.anything())
    expect(post.mock.calls[0]?.[1]).not.toHaveProperty('api_key')
  })

  it('posts onboarding credentials only to the protected same-origin endpoint', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({
      data: { id: 12, status: 'pending' },
    } as never)

    await apiService.startOnboarding({
      name: 'Live 1',
      ip: '203.0.113.10',
      ssh_port: 22,
      ssh_username: 'root',
      auth_method: 'private_key',
      private_key: 'ephemeral-test-key',
      host_key_fingerprint: 'SHA256:test-fingerprint',
    })

    expect(post).toHaveBeenCalledWith('/api/v1/onboarding', expect.objectContaining({
      auth_method: 'private_key',
      private_key: 'ephemeral-test-key',
    }))
    expect(post.mock.calls[0]?.[1]).not.toHaveProperty('api_key')
    expect(post.mock.calls[0]?.[1]).not.toHaveProperty('x-api-key')
  })
})
