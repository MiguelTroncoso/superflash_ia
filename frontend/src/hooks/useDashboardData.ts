import { useQueries, useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type {
  AlertsResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerMetricResponse,
  ServerResponse,
} from '../types/api'
import {
  buildDashboardSummary,
  buildDashboardHistory,
  hasMetricSamples,
  mapServerRows,
  type DashboardServerRow,
  type DashboardSummary,
  type DashboardHistoryPoint,
} from '../utils/dashboardMetrics'

const queryOptions = {
  staleTime: 30_000,
  refetchInterval: 60_000,
  retry: 1,
}

export interface DashboardData {
  isLoading: boolean
  isError: boolean
  isEmpty: boolean
  isFetching: boolean
  isStale: boolean
  error: unknown
  lastUpdatedAt: number
  summary: DashboardSummary | null
  rows: DashboardServerRow[]
  alerts: AlertsResponse['alerts']
  health: HealthResponse | null
  collectionStatus: CollectionStatusResponse | null
  history: DashboardHistoryPoint[]
  refetch: () => Promise<void>
}

export function useDashboardData(): DashboardData {
  const overviewQuery = useQuery<OverviewResponse>({
    queryKey: ['dashboard', 'overview'],
    queryFn: apiService.getOverview,
    ...queryOptions,
  })
  const serversQuery = useQuery<ServerResponse[]>({
    queryKey: ['dashboard', 'servers'],
    queryFn: apiService.getServers,
    ...queryOptions,
  })
  const channelsQuery = useQuery({
    queryKey: ['dashboard', 'channels'],
    queryFn: apiService.getChannels,
    ...queryOptions,
  })
  const alertsQuery = useQuery<AlertsResponse>({
    queryKey: ['dashboard', 'alerts'],
    queryFn: apiService.getAlerts,
    ...queryOptions,
  })
  const collectionQuery = useQuery<CollectionStatusResponse>({
    queryKey: ['dashboard', 'collection-status'],
    queryFn: apiService.getCollectionStatus,
    ...queryOptions,
  })
  const healthQuery = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: apiService.getHealth,
    ...queryOptions,
  })

  const enabledServers = (serversQuery.data ?? []).filter((server) => server.enabled)
  const metricQueries = useQueries({
    queries: enabledServers.map((server) => ({
      queryKey: ['dashboard', 'server-metrics', server.id, 'history'],
      queryFn: () => apiService.getServerMetrics(server.id, 24),
      ...queryOptions,
    })),
  })
  const queries = [
    overviewQuery,
    serversQuery,
    channelsQuery,
    alertsQuery,
    collectionQuery,
    healthQuery,
    ...metricQueries,
  ]
  const isLoading = queries.some((query) => query.isPending)
  const isError = queries.some((query) => query.isError)
  const isFetching = queries.some((query) => query.isFetching)
  const isStale = queries.some((query) => query.isStale)
  const error = queries.find((query) => query.isError)?.error ?? null
  const lastUpdatedAt = Math.max(...queries.map((query) => query.dataUpdatedAt), 0)
  const latestMetrics = new Map<number, ServerMetricResponse | undefined>()
  const histories = new Map<number, ServerMetricResponse[]>()

  enabledServers.forEach((server, index) => {
    latestMetrics.set(server.id, metricQueries[index]?.data?.[0])
    histories.set(server.id, metricQueries[index]?.data ?? [])
  })

  const rows =
    serversQuery.data && alertsQuery.data
      ? mapServerRows(serversQuery.data, latestMetrics, alertsQuery.data)
      : []
  const dataReady =
    !isLoading &&
    !isError &&
    overviewQuery.data !== undefined &&
    channelsQuery.data !== undefined &&
    alertsQuery.data !== undefined &&
    collectionQuery.data !== undefined &&
    healthQuery.data !== undefined
  const summary = dataReady
    ? buildDashboardSummary(
        overviewQuery.data,
        channelsQuery.data,
        rows,
        alertsQuery.data,
        healthQuery.data,
        collectionQuery.data,
      )
    : null
  const isEmpty = Boolean(dataReady && (!rows.length || !hasMetricSamples(rows)))

  const refetch = async (): Promise<void> => {
    await Promise.all(queries.map((query) => query.refetch()))
  }

  return {
    isLoading,
    isError,
    isEmpty,
    isFetching,
    isStale,
    error,
    lastUpdatedAt,
    summary,
    rows,
    alerts: alertsQuery.data?.alerts ?? [],
    health: healthQuery.data ?? null,
    collectionStatus: collectionQuery.data ?? null,
    history: buildDashboardHistory(histories),
    refetch,
  }
}
