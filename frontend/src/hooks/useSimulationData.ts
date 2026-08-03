import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type { SimulationRequestInput } from '../types/api'

export function useSimulationData() {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['optimizer', 'simulations'],
    queryFn: () => apiService.getSimulations(1, 20),
    staleTime: 30_000,
    retry: 1,
  })
  const mutation = useMutation({
    mutationFn: (payload: SimulationRequestInput) => apiService.createSimulation(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['optimizer', 'simulations'] })
    },
  })

  return {
    simulations: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    isLoading: query.isPending,
    isError: query.isError,
    isFetching: query.isFetching,
    isStale: query.isStale,
    lastUpdatedAt: query.dataUpdatedAt,
    isSubmitting: mutation.isPending,
    mutationError: mutation.error,
    latestSimulation: mutation.data ?? null,
    run: mutation.mutateAsync,
    refetch: async () => {
      await query.refetch()
    },
  }
}
