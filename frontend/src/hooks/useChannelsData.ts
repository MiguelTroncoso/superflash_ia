import { useQuery } from '@tanstack/react-query'
import { apiService, type ChannelListParams } from '../services/apiService'
import type { ChannelListItem, ChannelMetricResponse } from '../types/api'
import type { HealthState } from '../types/monitoring'

export interface ChannelTableRow {
  channel: ChannelListItem
  metric: ChannelMetricResponse | null
  state: HealthState
}

export interface ChannelsData {
  rows: ChannelTableRow[]
  page: number
  pageSize: number
  total: number
  totalPages: number
  isLoading: boolean
  isError: boolean
  isFetching: boolean
  isStale: boolean
  lastUpdatedAt: number
  refetch: () => Promise<void>
}

export function useChannelsData(params: ChannelListParams = {}): ChannelsData {
  const query = useQuery({
    queryKey: ['channels', params],
    queryFn: () => apiService.getChannels(params),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const page = query.data
  const rows = (page?.items ?? []).map((channel) => ({
    channel,
    metric: channel.latest_metric,
    state: channelState(channel.enabled, channel.latest_metric),
  }))

  return {
    rows,
    page: page?.page ?? params.page ?? 1,
    pageSize: page?.page_size ?? params.page_size ?? 50,
    total: page?.total ?? 0,
    totalPages: page?.total_pages ?? 0,
    isLoading: query.isPending,
    isError: query.isError,
    isFetching: query.isFetching,
    isStale: query.isStale,
    lastUpdatedAt: query.dataUpdatedAt,
    refetch: async () => {
      await query.refetch()
    },
  }
}

function channelState(enabled: boolean, metric: ChannelMetricResponse | null): HealthState {
  if (!enabled || metric?.status === 'offline') return 'critical'
  if (metric?.status === 'degraded' || metric === null) return 'warning'
  return 'healthy'
}
