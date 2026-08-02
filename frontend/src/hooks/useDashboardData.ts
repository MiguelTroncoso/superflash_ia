import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type {
  AlertsResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerPageResponse,
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
  const serversQuery = useQuery<ServerPageResponse>({
    queryKey: ['dashboard', 'servers'],
    queryFn: () => apiService.getServers({ page: 1, page_size: 200, enabled: true }),
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

  const queries = [overviewQuery, serversQuery, alertsQuery, collectionQuery, healthQuery]
  const isLoading = queries.some((query) => query.isPending)
  const isError = queries.some((query) => query.isError)
  const isFetching = queries.some((query) => query.isFetching)
  const isStale = queries.some((query) => query.isStale)
  const error = queries.find((query) => query.isError)?.error ?? null
  const lastUpdatedAt = Math.max(...queries.map((query) => query.dataUpdatedAt), 0)
  const alerts = alertsQuery.data ?? { generated_at: '', alerts: [] }
  const rows = serversQuery.data ? mapServerRows(serversQuery.data.items, alerts) : []
  const dataReady =
    !isLoading &&
    !isError &&
    overviewQuery.data !== undefined &&
    serversQuery.data !== undefined &&
    alertsQuery.data !== undefined &&
    collectionQuery.data !== undefined &&
    healthQuery.data !== undefined
  const summary = dataReady
    ? buildDashboardSummary(
        overviewQuery.data!,
        alertsQuery.data!,
        healthQuery.data!,
        collectionQuery.data!,
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
    history: buildDashboardHistory(overviewQuery.data?.history ?? []),
    refetch,
  }
}
