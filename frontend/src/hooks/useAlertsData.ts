import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useAlertsData() {
  const query = useQuery({
    queryKey: ['alerts'],
    queryFn: apiService.getAlerts,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })

  return {
    alerts: query.data?.alerts ?? [],
    generatedAt: query.data?.generated_at ?? null,
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
