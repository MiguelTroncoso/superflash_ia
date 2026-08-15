import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type { OnboardingDiagnosisResponse, OnboardingResponse, OnboardingStartRequest } from '../types/api'

const terminalStatuses = new Set(['completed', 'failed', 'cancelled', 'rollback_required'])
type CredentialPayload = Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>
type RetryVariables = { id: number; payload: CredentialPayload }
type DiagnosisVariables = { id: number; payload: CredentialPayload }

export function useServerOnboarding(onboardingId: number | null): {
  onboarding: OnboardingResponse | undefined
  isLoading: boolean
  isError: boolean
  isFetching: boolean
  refetch: () => Promise<void>
  start: ReturnType<typeof useMutation<OnboardingResponse, Error, OnboardingStartRequest>>
  retry: UseMutationResult<OnboardingResponse, Error, RetryVariables, unknown>
  cancel: UseMutationResult<OnboardingResponse, Error, void, unknown>
  rollback: UseMutationResult<OnboardingResponse, Error, RetryVariables, unknown>
  diagnose: UseMutationResult<OnboardingDiagnosisResponse, Error, DiagnosisVariables, unknown>
} {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['server-onboarding', onboardingId],
    queryFn: () => apiService.getOnboarding(onboardingId as number),
    enabled: onboardingId !== null,
    staleTime: 1_000,
    refetchInterval: (current) => {
      const status = current.state.data?.status
      return status && !terminalStatuses.has(status) ? 1_500 : false
    },
  })
  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['servers'] })
  }
  const start = useMutation({ mutationFn: apiService.startOnboarding, onSuccess: invalidate })
  const retry = useMutation({ mutationFn: ({ id, payload }: RetryVariables) => apiService.retryOnboarding(id, payload), onSuccess: invalidate })
  const cancel = useMutation({ mutationFn: () => apiService.cancelOnboarding(onboardingId as number) })
  const rollback = useMutation({ mutationFn: ({ id, payload }: RetryVariables) => apiService.rollbackOnboarding(id, payload), onSuccess: invalidate })
  const diagnose = useMutation({ mutationFn: ({ id, payload }: DiagnosisVariables) => apiService.diagnoseOnboarding(id, payload) })

  return {
    onboarding: query.data,
    isLoading: query.isPending,
    isError: query.isError,
    isFetching: query.isFetching,
    refetch: async () => { await query.refetch() },
    start,
    retry,
    cancel,
    rollback,
    diagnose,
  }
}
