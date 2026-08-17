import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { UseMutationResult } from '@tanstack/react-query'
import { apiService } from '../services/apiService'
import type {
  MaintenanceAction,
  MaintenanceResponse,
  OnboardingActiveResponse,
  OnboardingDiagnosisResponse,
  OnboardingDiscoveryRequest,
  OnboardingDiscoveryResponse,
  OnboardingHealthResponse,
  OnboardingResponse,
  OnboardingStartRequest,
  OnboardingTestSSHRequest,
  OnboardingTestSSHResponse,
} from '../types/api'

export function useActiveOnboardings(): {
  jobs: OnboardingActiveResponse[]
  isLoading: boolean
  isError: boolean
} {
  const query = useQuery({
    queryKey: ['onboarding-active'],
    queryFn: apiService.getActiveOnboardings,
    staleTime: 15_000,
    refetchOnWindowFocus: false,
    retry: 1,
  })
  return {
    jobs: query.data ?? [],
    isLoading: query.isPending,
    isError: query.isError,
  }
}

const terminalStatuses = new Set(['completed', 'failed', 'cancelled', 'rollback_required'])
type CredentialPayload = Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>
type RetryVariables = { id: number; payload: CredentialPayload }
type DiagnosisVariables = { id: number; payload: CredentialPayload }
type RequestVariables<T> = { payload: T; signal?: AbortSignal }
type MaintenanceVariables = {
  serverId: number
  action: MaintenanceAction
  payload: CredentialPayload & { target_version?: string }
}

export function useServerOnboarding(onboardingId: number | null): {
  onboarding: OnboardingResponse | undefined
  isLoading: boolean
  isError: boolean
  error: Error | null
  isFetching: boolean
  lastUpdatedAt: number
  health: OnboardingHealthResponse | undefined
  discover: ReturnType<typeof useMutation<OnboardingDiscoveryResponse, Error, RequestVariables<OnboardingDiscoveryRequest>>>
  testSSH: ReturnType<typeof useMutation<OnboardingTestSSHResponse, Error, RequestVariables<OnboardingTestSSHRequest>>>
  refetch: () => Promise<void>
  start: ReturnType<typeof useMutation<OnboardingResponse, Error, RequestVariables<OnboardingStartRequest>>>
  retry: UseMutationResult<OnboardingResponse, Error, RetryVariables, unknown>
  cancel: UseMutationResult<OnboardingResponse, Error, void, unknown>
  rollback: UseMutationResult<OnboardingResponse, Error, RetryVariables, unknown>
  diagnose: UseMutationResult<OnboardingDiagnosisResponse, Error, DiagnosisVariables, unknown>
  maintenance: UseMutationResult<MaintenanceResponse, Error, MaintenanceVariables, unknown>
} {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['server-onboarding', onboardingId],
    queryFn: () => apiService.getOnboarding(onboardingId as number),
    enabled: onboardingId !== null,
    staleTime: 1_000,
    refetchInterval: (current) => {
      const status = current.state.data?.status
      return status && terminalStatuses.has(status) ? false : 1_500
    },
    refetchIntervalInBackground: true,
    retry: 2,
  })
  const invalidateServers = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ['servers'] })
  }
  const syncOnboarding = async (data: OnboardingResponse): Promise<void> => {
    await queryClient.cancelQueries({ queryKey: ['server-onboarding', data.id] })
    queryClient.setQueryData(['server-onboarding', data.id], data)
    await invalidateServers()
  }
  const start = useMutation({ mutationFn: ({ payload, signal }: RequestVariables<OnboardingStartRequest>) => apiService.startOnboarding(payload, signal), onSuccess: syncOnboarding })
  const discover = useMutation({ mutationFn: ({ payload, signal }: RequestVariables<OnboardingDiscoveryRequest>) => apiService.discoverOnboarding(payload, signal) })
  const testSSH = useMutation({ mutationFn: ({ payload, signal }: RequestVariables<OnboardingTestSSHRequest>) => apiService.testSSHConnection(payload, signal) })
  const retry = useMutation({ mutationFn: ({ id, payload }: RetryVariables) => apiService.retryOnboarding(id, payload), onSuccess: syncOnboarding })
  const cancel = useMutation({ mutationFn: () => apiService.cancelOnboarding(onboardingId as number), onSuccess: syncOnboarding })
  const rollback = useMutation({ mutationFn: ({ id, payload }: RetryVariables) => apiService.rollbackOnboarding(id, payload), onSuccess: syncOnboarding })
  const diagnose = useMutation({ mutationFn: ({ id, payload }: DiagnosisVariables) => apiService.diagnoseOnboarding(id, payload) })
  const maintenance = useMutation({ mutationFn: ({ serverId, action, payload }: MaintenanceVariables) => apiService.maintenance(serverId, action, payload), onSuccess: invalidateServers })
  const healthQuery = useQuery({
    queryKey: ['server-onboarding-health', onboardingId],
    queryFn: () => apiService.getOnboardingHealth(onboardingId as number),
    enabled: onboardingId !== null && activeIsCompleted(query.data?.status),
    staleTime: 10_000,
  })

  return {
    onboarding: query.data,
    isLoading: query.isPending,
    isError: query.isError,
    error: query.error,
    isFetching: query.isFetching,
    lastUpdatedAt: query.dataUpdatedAt,
    health: healthQuery.data,
    discover,
    testSSH,
    refetch: async () => { await query.refetch() },
    start,
    retry,
    cancel,
    rollback,
    diagnose,
    maintenance,
  }
}

function activeIsCompleted(status: string | undefined): boolean {
  return status === 'completed'
}
