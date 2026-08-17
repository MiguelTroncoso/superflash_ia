import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiService } from '../../services/apiService'
import type { OnboardingActiveResponse } from '../../types/api'
import { ServerOnboardingDialog } from './ServerOnboardingDialog'

function renderDialog(activeJobs: OnboardingActiveResponse[] = []): void {
  vi.spyOn(apiService, 'getActiveOnboardings').mockResolvedValue(activeJobs)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ServerOnboardingDialog onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('ServerOnboardingDialog recovery controls', () => {
  afterEach(() => {
    cleanup()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('opens at zero with every onboarding step not started and no polling job', () => {
    const getOnboarding = vi.spyOn(apiService, 'getOnboarding')
    renderDialog()

    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.queryByText(/estimated time/)).not.toBeInTheDocument()
    expect(screen.queryByText('In progress')).not.toBeInTheDocument()
    expect(screen.getAllByText('Not started')).toHaveLength(10)
    expect(getOnboarding).not.toHaveBeenCalled()
  })

  it('unlocks discovery after the preflight timeout and allows a reset', async () => {
    vi.useFakeTimers()
    vi.spyOn(apiService, 'discoverOnboarding').mockImplementation(() => new Promise(() => undefined))
    renderDialog()

    fireEvent.change(screen.getByLabelText('Server name'), { target: { value: 'Live 1' } })
    fireEvent.change(screen.getByLabelText('IP or hostname'), { target: { value: '203.0.113.10' } })
    fireEvent.change(screen.getByLabelText('Temporary password'), { target: { value: 'temporary' } })
    fireEvent.click(screen.getByRole('button', { name: 'Detect server' }))
    expect(screen.getByText(/5%/)).toBeInTheDocument()
    expect(screen.getByText('In progress')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(30_000)
    expect(screen.getByText(/superó los 30 segundos/)).toBeInTheDocument()

    const reset = screen.getByRole('button', { name: 'Start a new discovery' })
    expect(reset).toBeEnabled()
    fireEvent.click(reset)
    expect(screen.getByRole('button', { name: 'Detect server' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Temporary password'), { target: { value: 'temporary-again' } })
    expect(screen.getByRole('button', { name: 'Detect server' })).toBeEnabled()
    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.queryByText('In progress')).not.toBeInTheDocument()
    expect(screen.getAllByText('Not started')).toHaveLength(10)
  })

  it('offers resume for a real active backend job without starting discovery', async () => {
    const job: OnboardingActiveResponse = {
      id: 42,
      server_id: 7,
      server_name: 'Live 1',
      server_hostname: '203.0.113.10',
      status: 'discovering',
      current_step: 'discovering',
      progress_percent: 25,
      started_at: '2026-08-16T00:00:00Z',
      completed_at: null,
      failed_at: null,
      last_error_code: null,
      last_error_message_sanitized: null,
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
    vi.spyOn(apiService, 'getOnboarding').mockResolvedValue(job)
    renderDialog([job])

    await waitFor(() => expect(screen.getByText('Resume existing onboarding')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Resume$/ }))
    await waitFor(() => expect(screen.getByText('Current step:')).toBeInTheDocument())
    expect(screen.getAllByText('discovering')).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Detect server' })).not.toBeInTheDocument()
  })
})
