import { useQueries, useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type { ChannelMetricResponse, ChannelResponse } from '../types/api'
import type { HealthState } from '../types/monitoring'

export interface ChannelTableRow {
  channel: ChannelResponse
  metric: ChannelMetricResponse | null
  state: HealthState
}

export function useChannelsData(): {
  rows: ChannelTableRow[]
  isLoading: boolean
  isError: boolean
  isFetching: boolean
  isStale: boolean
  lastUpdatedAt: number
  refetch: () => Promise<void>
} {
  const channelsQuery = useQuery({
    queryKey: ['channels'],
    queryFn: apiService.getChannels,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const channels = channelsQuery.data ?? []
  const metricQueries = useQueries({
    queries: channels.map((channel) => ({
      queryKey: ['channels', channel.id, 'latest-metric'],
      queryFn: () => apiService.getChannelMetrics(channel.id),
      staleTime: 30_000,
      refetchInterval: 60_000,
      retry: 1,
    })),
  })
  const rows = channels.map((channel, index) => {
    const metric = metricQueries[index]?.data?.[0] ?? null
    return { channel, metric, state: channelState(channel.enabled, metric) }
  })
  const queries = [channelsQuery, ...metricQueries]

  return {
    rows,
    isLoading: queries.some((query) => query.isPending),
    isError: queries.some((query) => query.isError),
    isFetching: queries.some((query) => query.isFetching),
    isStale: queries.some((query) => query.isStale),
    lastUpdatedAt: Math.max(...queries.map((query) => query.dataUpdatedAt), 0),
    refetch: async () => {
      await Promise.all(queries.map((query) => query.refetch()))
    },
  }
}

function channelState(enabled: boolean, metric: ChannelMetricResponse | null): HealthState {
  if (!enabled || metric?.status === 'offline') return 'critical'
  if (metric?.status === 'degraded' || metric === null) return 'warning'
  return 'healthy'
}
