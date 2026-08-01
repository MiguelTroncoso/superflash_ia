import { useQuery } from '@tanstack/react-query'
import { apiService, type ServerListParams } from '../services/apiService'
import type { ServerListItem, ServerMetricResponse } from '../types/api'
import type { HealthState } from '../types/monitoring'

export interface ServerTableRow {
  server: ServerListItem
  metric: ServerMetricResponse | null
  state: HealthState
}

export interface ServersData {
  rows: ServerTableRow[]
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

export function useServersData(params: ServerListParams = {}): ServersData {
  const query = useQuery({
    queryKey: ['servers', params],
    queryFn: () => apiService.getServers(params),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const page = query.data
  const rows = (page?.items ?? []).map((server) => ({
    server,
    metric: server.latest_metric,
    state: serverState(server),
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

function serverState(server: ServerListItem): HealthState {
  if (server.status === 'offline') return 'critical'
  if (server.active_alert_count > 0 || server.status === 'degraded' || server.status === 'maintenance') {
    return 'warning'
  }
  if (server.latest_metric === null || server.status === 'unknown') return 'warning'
  return 'healthy'
}
