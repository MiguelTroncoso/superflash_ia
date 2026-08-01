import { useQueries, useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type { AlertResponse, ServerMetricResponse, ServerResponse } from '../types/api'
import type { HealthState } from '../types/monitoring'

export interface ServerTableRow {
  server: ServerResponse
  metric: ServerMetricResponse | null
  state: HealthState
}

export interface ServersData {
  rows: ServerTableRow[]
  isLoading: boolean
  isError: boolean
  isFetching: boolean
  isStale: boolean
  lastUpdatedAt: number
  refetch: () => Promise<void>
}

export function useServersData(): ServersData {
  const serversQuery = useQuery({
    queryKey: ['servers'],
    queryFn: apiService.getServers,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: apiService.getAlerts,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })
  const servers = serversQuery.data ?? []
  const metricServers = servers.filter((server) => server.enabled)
  const metricQueries = useQueries({
    queries: metricServers.map((server) => ({
      queryKey: ['servers', server.id, 'latest-metric'],
      queryFn: () => apiService.getServerMetrics(server.id),
      staleTime: 30_000,
      refetchInterval: 60_000,
      retry: 1,
    })),
  })
  const queries = [serversQuery, alertsQuery, ...metricQueries]
  const alerts = alertsQuery.data?.alerts ?? []
  const metricsByServer = new Map(
    metricServers.map((server, index) => [server.id, metricQueries[index]?.data?.[0] ?? null]),
  )
  const rows = servers.map((server) => {
    const metric = metricsByServer.get(server.id) ?? null
    const serverAlerts = alerts.filter((alert) => alert.server_id === server.id)
    return { server, metric, state: serverState(server, metric, serverAlerts) }
  })

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

function serverState(
  server: ServerResponse,
  metric: ServerMetricResponse | null,
  alerts: AlertResponse[],
): HealthState {
  if (alerts.some((alert) => alert.severity === 'critical')) return 'critical'
  if (alerts.length > 0 || server.status === 'degraded' || server.status === 'maintenance') {
    return 'warning'
  }
  if (server.status === 'offline') return 'critical'
  if (metric === null || server.status === 'unknown') return 'warning'
  return 'healthy'
}
