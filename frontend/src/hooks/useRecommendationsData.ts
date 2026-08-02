import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useRecommendationsData() {
  const query = useQuery({
    queryKey: ['recommendations'],
    queryFn: apiService.getRecommendations,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })

  return {
    recommendations: query.data?.recommendations ?? [],
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
