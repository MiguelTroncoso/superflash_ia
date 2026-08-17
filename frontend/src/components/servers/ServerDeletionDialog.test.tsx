import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiService } from '../../services/apiService'
import type { ServerResponse } from '../../types/api'
import { ServerDeletionDialog } from './ServerDeletionDialog'

const server = {
  id: 7,
  name: 'Test server',
  hostname: '203.0.113.7',
} as ServerResponse

const impact = {
  server_id: 7,
  name: 'Test server',
  hostname: '203.0.113.7',
  can_hard_delete: true,
  relations: {
    metrics: 0,
    alerts: 0,
    inventory_snapshots: 0,
    onboarding_jobs: 0,
    non_cancelled_onboarding_jobs: 0,
    onboarding_audit_events: 0,
    assigned_channels: 0,
    channel_metrics: 0,
    category_history: 0,
    cost_records: 0,
    simulation_records: 0,
  },
}

describe('ServerDeletionDialog', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('requires the explicit checkbox and exact server name before deleting', async () => {
    vi.spyOn(apiService, 'getServerDeletionImpact').mockResolvedValue(impact)
    const deleteServer = vi.spyOn(apiService, 'deleteServer').mockResolvedValue({
      ...impact,
      action: 'deleted',
      cancelled_onboarding_jobs: 0,
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(
      <QueryClientProvider client={queryClient}>
        <ServerDeletionDialog server={server} onClose={vi.fn()} onDeleted={vi.fn()} />
      </QueryClientProvider>,
    )

    await waitFor(() => expect(screen.getByText(/No productive relations/)).toBeInTheDocument())
    const deleteButton = screen.getByRole('button', { name: /Delete server/ })
    expect(deleteButton).toBeDisabled()
    expect(deleteServer).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('checkbox'))
    expect(deleteButton).toBeDisabled()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Test server' } })
    expect(deleteButton).toBeEnabled()
    fireEvent.click(deleteButton)

    await waitFor(() => expect(deleteServer).toHaveBeenCalledWith(7, {
      confirmation: 'Test server',
      hostname: '203.0.113.7',
    }))
  })
})
