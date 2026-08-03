import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type { AlertResponse, CollectionStatusResponse, ServerDiagnosticResponse, ServerMetricResponse } from '../types/api'
import type { ServerResponse } from '../types/api'

export interface ServerDetailData {
  server: ServerResponse | undefined
  metrics: ServerMetricResponse[]
  alerts: AlertResponse[]
  collectionStatus: CollectionStatusResponse | null
  diagnostic: ServerDiagnosticResponse | null
  isLoading: boolean
  isError: boolean
  isFetching: boolean
  isStale: boolean
  isEmpty: boolean
  lastUpdatedAt: number
  refetch: () => Promise<void>
}

const queryOptions = {
  staleTime: 30_000,
  refetchInterval: 60_000,
  retry: 1,
}

export function useServerDetailData(serverId: number): ServerDetailData {
  const serverQuery = useQuery({
    queryKey: ['server', serverId],
    queryFn: () => apiService.getServer(serverId),
    ...queryOptions,
  })
  const metricsQuery = useQuery({
    queryKey: ['server', serverId, 'metrics'],
    queryFn: () => apiService.getServerMetrics(serverId, 100),
    ...queryOptions,
    enabled: serverId > 0,
  })
  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: apiService.getAlerts,
    ...queryOptions,
  })
  const collectionQuery = useQuery({
    queryKey: ['collection-status'],
    queryFn: apiService.getCollectionStatus,
    ...queryOptions,
  })
  const diagnosticQuery = useQuery({
    queryKey: ['server', serverId, 'diagnostic'],
    queryFn: () => apiService.diagnoseServer(serverId),
    ...queryOptions,
    enabled: serverId > 0,
  })
  const queries = [serverQuery, metricsQuery, alertsQuery, collectionQuery, diagnosticQuery]

  return {
    server: serverQuery.data,
    metrics: metricsQuery.data ?? [],
    alerts: (alertsQuery.data?.alerts ?? []).filter((alert) => alert.server_id === serverId),
    collectionStatus: collectionQuery.data ?? null,
    diagnostic: diagnosticQuery.data ?? null,
    isLoading: queries.some((query) => query.isPending),
    isError: queries.some((query) => query.isError),
    isFetching: queries.some((query) => query.isFetching),
    isStale: queries.some((query) => query.isStale),
    isEmpty: Boolean(!serverQuery.isPending && !serverQuery.isError && !metricsQuery.data?.length),
    lastUpdatedAt: Math.max(...queries.map((query) => query.dataUpdatedAt), 0),
    refetch: async () => {
      await Promise.all(queries.map((query) => query.refetch()))
    },
  }
}
