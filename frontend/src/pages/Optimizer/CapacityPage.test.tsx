import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CapacityPage } from './CapacityPage'
import { useCapacityData } from '../../hooks/useCapacityData'

vi.mock('../../hooks/useCapacityData', () => ({ useCapacityData: vi.fn() }))

const capacityMock = vi.mocked(useCapacityData)

const baseData = {
  capacity: {
    generated_at: '2026-08-03T12:00:00Z',
    server_count: 1,
    configured_server_count: 1,
    sampled_server_count: 1,
    total_physical_capacity_mbps: 1000,
    total_operational_limit_mbps: 700,
    total_observed_load_mbps: 650,
    total_physical_free_mbps: 350,
    total_operational_free_mbps: 50,
    data_quality: 'observed' as const,
    missing_data: [],
    servers: [{
      server_id: 1,
      name: 'MainServer',
      provider: 'Example',
      group: 'core',
      physical_capacity_mbps: 1000,
      operational_limit_mbps: 700,
      recommended_limit_mbps: 800,
      minimum_reserve_mbps: 100,
      observed_load_mbps: 650,
      physical_utilization_percent: 65,
      operational_utilization_percent: 92.86,
      physical_free_mbps: 350,
      operational_free_mbps: 50,
      safety_margin_mbps: 0,
      state: 'warning' as const,
      data_quality: 'observed' as const,
      last_collected_at: '2026-08-03T12:00:00Z',
    }],
  },
  isLoading: false,
  isError: false,
  isFetching: false,
  isStale: false,
  lastUpdatedAt: Date.parse('2026-08-03T12:00:00Z'),
  refetch: vi.fn().mockResolvedValue(undefined),
}

describe('CapacityPage', () => {
  beforeEach(() => capacityMock.mockReset())

  it('shows loading without invented capacity values', () => {
    capacityMock.mockReturnValue({ ...baseData, capacity: null, isLoading: true })
    render(<CapacityPage />)

    expect(screen.getByText('Loading configured capacity and latest samples.')).toBeInTheDocument()
    expect(screen.queryByText('1000.0 Mbps')).not.toBeInTheDocument()
  })

  it('shows explicit API data and stale freshness', () => {
    capacityMock.mockReturnValue({ ...baseData, isStale: true })
    render(<CapacityPage />)

    expect(screen.getByText('MainServer')).toBeInTheDocument()
    expect(screen.getByText('warning')).toBeInTheDocument()
    expect(screen.getByText('Operational target')).toBeInTheDocument()
  })

  it('shows empty state when no servers are configured', () => {
    capacityMock.mockReturnValue({ ...baseData, capacity: { ...baseData.capacity, server_count: 0, servers: [] } })
    render(<CapacityPage />)

    expect(screen.getByText('No enabled servers are available for capacity planning.')).toBeInTheDocument()
  })
})
