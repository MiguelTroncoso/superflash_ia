import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiService } from '../../services/apiService'
import { ServerOnboardingDialog } from './ServerOnboardingDialog'

function renderDialog(): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ServerOnboardingDialog onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('ServerOnboardingDialog recovery controls', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('unlocks discovery after the preflight timeout and allows a reset', async () => {
    vi.useFakeTimers()
    vi.spyOn(apiService, 'discoverOnboarding').mockImplementation(() => new Promise(() => undefined))
    renderDialog()

    fireEvent.change(screen.getByLabelText('Server name'), { target: { value: 'Live 1' } })
    fireEvent.change(screen.getByLabelText('IP or hostname'), { target: { value: '203.0.113.10' } })
    fireEvent.change(screen.getByLabelText('Temporary password'), { target: { value: 'temporary' } })
    fireEvent.click(screen.getByRole('button', { name: 'Detect server' }))

    await vi.advanceTimersByTimeAsync(30_000)
    expect(screen.getByText(/superó los 30 segundos/)).toBeInTheDocument()

    const reset = screen.getByRole('button', { name: 'Start a new discovery' })
    expect(reset).toBeEnabled()
    fireEvent.click(reset)
    expect(screen.getByRole('button', { name: 'Detect server' })).toBeEnabled()
  })
})
