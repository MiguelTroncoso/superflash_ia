import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AlertsPage } from './AlertsPage'
import { useAlertsData } from '../../hooks/useAlertsData'

vi.mock('../../hooks/useAlertsData', () => ({ useAlertsData: vi.fn() }))
vi.mock('../../hooks/usePageTitle', () => ({ usePageTitle: vi.fn() }))

const alertsMock = vi.mocked(useAlertsData)

describe('AlertsPage', () => {
  beforeEach(() => alertsMock.mockReset())

  it('renders persisted alert data from the API shape', () => {
    alertsMock.mockReturnValue({
      alerts: [{ id: 8, type: 'high_cpu', severity: 'critical', status: 'active', server_id: 1, server_name: 'core-1', message: 'CPU high', value: 95, threshold: 90, collected_at: '2026-08-01T10:00:00Z', first_seen_at: '2026-08-01T10:00:00Z', last_seen_at: '2026-08-01T10:00:00Z', acknowledged_at: null, resolved_at: null }],
      generatedAt: '2026-08-01T10:00:00Z', isLoading: false, isError: false, isFetching: false, isStale: false, lastUpdatedAt: Date.parse('2026-08-01T10:00:00Z'), refetch: vi.fn().mockResolvedValue(undefined),
    })

    render(<AlertsPage />)

    expect(screen.getByText('CPU high')).toBeInTheDocument()
    expect(screen.getByText(/core-1 · high_cpu ·/)).toBeInTheDocument()
  })

  it('renders empty when no rules are currently active', () => {
    alertsMock.mockReturnValue({ alerts: [], generatedAt: null, isLoading: false, isError: false, isFetching: false, isStale: false, lastUpdatedAt: 0, refetch: vi.fn().mockResolvedValue(undefined) })
    render(<AlertsPage />)
    expect(screen.getByText('No monitoring data available')).toBeInTheDocument()
  })
})
