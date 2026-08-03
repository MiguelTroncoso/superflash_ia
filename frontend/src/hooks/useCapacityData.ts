import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useCapacityData() {
  const query = useQuery({
    queryKey: ['optimizer', 'capacity'],
    queryFn: apiService.getCapacityOverview,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })

  return {
    capacity: query.data ?? null,
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
