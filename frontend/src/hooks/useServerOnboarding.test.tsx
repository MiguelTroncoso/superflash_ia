import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiService } from '../services/apiService'
import type { OnboardingResponse } from '../types/api'
import { useServerOnboarding } from './useServerOnboarding'

function wrapper({ children }: { children: React.ReactNode }): React.JSX.Element {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

function onboarding(status: OnboardingResponse['status']): OnboardingResponse {
  return {
    id: 7,
    server_id: 11,
    status,
    current_step: status === 'pending' ? 'pending' : status,
    progress_percent: status === 'completed' ? 100 : 0,
    started_at: null,
    completed_at: null,
    failed_at: null,
    last_error_code: status === 'failed' ? 'command_timeout' : null,
    last_error_message_sanitized: status === 'failed' ? 'La comprobación remota superó el tiempo máximo.' : null,
    retry_count: 0,
    last_successful_step: null,
    created_by: 'operator',
    auth_method: 'password',
    ssh_port: 22,
    ssh_username: 'root',
    cancel_requested: false,
    created_at: '2026-08-16T00:00:00Z',
    updated_at: '2026-08-16T00:00:00Z',
  }
}

describe('useServerOnboarding', () => {
  afterEach(() => vi.restoreAllMocks())

  it('keeps polling after an initial transient status request failure', async () => {
    const getOnboarding = vi.spyOn(apiService, 'getOnboarding')
      .mockRejectedValueOnce(new Error('temporary network failure'))
      .mockResolvedValue(onboarding('pending'))

    const { result } = renderHook(() => useServerOnboarding(7), { wrapper })

    await waitFor(() => expect(result.current.onboarding?.status).toBe('pending'), { timeout: 4_000 })
    expect(getOnboarding.mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('synchronizes retry and cancel responses immediately into the status query', async () => {
    vi.spyOn(apiService, 'getOnboarding').mockResolvedValue(onboarding('failed'))
    const retryOnboarding = vi.spyOn(apiService, 'retryOnboarding').mockResolvedValue(onboarding('pending'))
    const cancelOnboarding = vi.spyOn(apiService, 'cancelOnboarding').mockResolvedValue(onboarding('cancelled'))
    const { result } = renderHook(() => useServerOnboarding(7), { wrapper })

    await waitFor(() => expect(result.current.onboarding?.status).toBe('failed'))
    await act(async () => {
      await result.current.retry.mutateAsync({ id: 7, payload: { auth_method: 'password', password: 'temporary' } })
    })
    await waitFor(() => expect(result.current.onboarding?.status).toBe('pending'))
    expect(retryOnboarding).toHaveBeenCalledOnce()

    await act(async () => {
      await result.current.cancel.mutateAsync()
    })
    await waitFor(() => expect(result.current.onboarding?.status).toBe('cancelled'))
    expect(cancelOnboarding).toHaveBeenCalledOnce()
  })
})
