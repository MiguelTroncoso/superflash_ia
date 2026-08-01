import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { useDashboardData, type DashboardData } from '../../hooks/useDashboardData'

vi.mock('../../hooks/useDashboardData', () => ({
  useDashboardData: vi.fn(),
}))

const dashboardMock = vi.mocked(useDashboardData)

function renderPage(): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <DashboardPage />
    </QueryClientProvider>,
  )
}

function dashboardState(overrides: Partial<DashboardData> = {}): DashboardData {
  return {
    isLoading: false,
    isError: false,
    isEmpty: false,
    isFetching: false,
    isStale: false,
    error: null,
    lastUpdatedAt: Date.parse('2026-08-01T10:00:00Z'),
    summary: {
      serverCount: 1,
      channelCount: 3,
      avgCpuPercent: 62,
      avgMemoryPercent: 71,
      avgDiskPercent: 44,
      totalInputMbps: 22,
      totalOutputMbps: 140,
      alertCount: 1,
      generalState: 'healthy',
      generalLabel: 'Healthy',
      collectionLabel: 'Last collection 1 Aug 2026, 10:00',
    },
    rows: [
      {
        id: 1,
        name: 'sf-core-01',
        hostname: 'core-a',
        role: 'main',
        cpuPercent: 92,
        memoryPercent: 71,
        diskPercent: 44,
        inputMbps: 22,
        outputMbps: 140,
        collectedAt: '2026-08-01T10:00:00Z',
        state: 'warning',
        stateLabel: 'Attention',
      },
    ],
    alerts: [],
    health: { status: 'ok', database: 'ok', version: '0.1.0' },
    collectionStatus: {
      running: false,
      run_id: 2,
      source: 'mock',
      triggered_by: 'scheduler',
      started_at: '2026-08-01T09:59:00Z',
      heartbeat_at: '2026-08-01T09:59:05Z',
      finished_at: '2026-08-01T10:00:00Z',
      duration_ms: 1000,
      status: 'success',
      inserted: 1,
      skipped: 0,
      errors: [],
      next_run_at: null,
    },
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

describe('DashboardPage', () => {
  beforeEach(() => {
    dashboardMock.mockReset()
  })

  it('renders a loading state without metric placeholders', () => {
    dashboardMock.mockReturnValue(dashboardState({ isLoading: true, summary: null }))
    renderPage()

    expect(screen.getByText('Loading live dashboard data')).toBeInTheDocument()
    expect(screen.queryByText('62.0%')).not.toBeInTheDocument()
  })

  it('renders an error state and retries', async () => {
    const retry = vi.fn().mockResolvedValue(undefined)
    dashboardMock.mockReturnValue(
      dashboardState({ isError: true, summary: null, refetch: retry }),
    )
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(retry).toHaveBeenCalledOnce())
    expect(screen.getByText('Live dashboard unavailable')).toBeInTheDocument()
  })

  it('renders an explicit empty state when the API has no samples', () => {
    dashboardMock.mockReturnValue(dashboardState({ isEmpty: true, summary: null }))
    renderPage()

    expect(screen.getByText('No monitoring data available')).toBeInTheDocument()
    expect(screen.getByText(/no server samples/i)).toBeInTheDocument()
  })

  it('renders API-shaped data and clearly labels simulated sections', () => {
    dashboardMock.mockReturnValue(dashboardState())
    renderPage()

    expect(screen.getByText('62.0%')).toBeInTheDocument()
    expect(screen.getByText('44.0%')).toBeInTheDocument()
    expect(screen.getAllByText('140.0 Mbps')).toHaveLength(2)
    expect(screen.getByText('sf-core-01')).toBeInTheDocument()
    expect(screen.getByText('Latest server metrics from the read-only API')).toBeInTheDocument()
    expect(screen.getAllByText('Simulated data')).toHaveLength(3)
  })
})
