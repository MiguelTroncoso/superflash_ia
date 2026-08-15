import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useIntelligenceRecommendationsData() {
  const query = useQuery({
    queryKey: ['optimizer', 'intelligence-recommendations'],
    queryFn: apiService.getIntelligenceRecommendations,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })

  return {
    recommendations: query.data?.recommendations ?? [],
    dataQuality: query.data?.data_quality ?? 'insufficient_data',
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
