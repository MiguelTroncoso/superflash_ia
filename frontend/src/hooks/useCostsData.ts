import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useCostsData() {
  const query = useQuery({
    queryKey: ['optimizer', 'costs'],
    queryFn: apiService.getCostsSummary,
    staleTime: 60_000,
    refetchInterval: 300_000,
    retry: 1,
  })

  return {
    costs: query.data ?? null,
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
