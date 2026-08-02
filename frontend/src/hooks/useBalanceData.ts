import { useQuery } from '@tanstack/react-query'
import { apiService } from '../services/apiService'

export function useBalanceData() {
  const query = useQuery({
    queryKey: ['balance'],
    queryFn: apiService.getBalance,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  })

  return {
    balance: query.data ?? null,
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
