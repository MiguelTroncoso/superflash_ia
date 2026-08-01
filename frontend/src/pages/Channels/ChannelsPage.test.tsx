import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChannelsPage } from './ChannelsPage'
import { useChannelsData } from '../../hooks/useChannelsData'

vi.mock('../../hooks/useChannelsData', () => ({ useChannelsData: vi.fn() }))
vi.mock('../../hooks/usePageTitle', () => ({ usePageTitle: vi.fn() }))

const channelsMock = vi.mocked(useChannelsData)

describe('ChannelsPage', () => {
  beforeEach(() => channelsMock.mockReset())

  it('renders live channel rows and does not invent missing samples', () => {
    channelsMock.mockReturnValue({
      rows: [{
        channel: { id: 1, external_id: 'ch-1', name: 'News', category: 'News', current_server_id: 2, enabled: true, created_at: '2026-08-01T10:00:00Z', updated_at: '2026-08-01T10:00:00Z' },
        metric: { id: 2, channel_id: 1, server_id: 2, collected_at: '2026-08-01T10:00:00Z', viewers: 1200, bitrate_mbps: 4.5, estimated_output_mbps: 5, status: 'online' },
        state: 'healthy',
      }, {
        channel: { id: 2, external_id: 'ch-2', name: 'Sports', category: null, current_server_id: null, enabled: true, created_at: '2026-08-01T10:00:00Z', updated_at: '2026-08-01T10:00:00Z' },
        metric: null,
        state: 'warning',
      }],
      page: 1, pageSize: 50, total: 2, totalPages: 1,
      isLoading: false, isError: false, isFetching: false, isStale: false, lastUpdatedAt: 0, refetch: vi.fn().mockResolvedValue(undefined),
    })

    render(<ChannelsPage />)

    expect(screen.getAllByText('News')).toHaveLength(2)
    expect(screen.getAllByText('1.2K')).toHaveLength(2)
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('renders the explicit empty API state', () => {
    channelsMock.mockReturnValue({ rows: [], page: 1, pageSize: 50, total: 0, totalPages: 0, isLoading: false, isError: false, isFetching: false, isStale: false, lastUpdatedAt: 0, refetch: vi.fn().mockResolvedValue(undefined) })
    render(<ChannelsPage />)
    expect(screen.getByText('No monitoring data available')).toBeInTheDocument()
  })
})
