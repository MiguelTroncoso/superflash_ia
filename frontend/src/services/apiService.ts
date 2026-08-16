import { httpClient } from './httpClient'
import type {
  AlertsResponse,
  BalanceResponse,
  ChannelMetricResponse,
  ChannelPageResponse,
  ApiChannelType,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerMetricResponse,
  ServerPageResponse,
  ServerResponse,
  RecommendationsResponse,
  OnboardingAuditResponse,
  OnboardingDiagnosisResponse,
  OnboardingDiscoveryRequest,
  OnboardingDiscoveryResponse,
  OnboardingTestSSHRequest,
  OnboardingTestSSHResponse,
  OnboardingHealthResponse,
  MaintenanceAction,
  MaintenanceResponse,
  OnboardingResponse,
  OnboardingStartRequest,
} from '../types/api'

const API_V1_PREFIX = '/api/v1'

type QueryParams = Record<string, boolean | number | string | undefined>

export interface ServerListParams extends QueryParams {
  page?: number
  page_size?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  status?: string
  provider?: string
  group?: string
  enabled?: boolean
}

export interface ChannelListParams extends QueryParams {
  page?: number
  page_size?: number
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  server_id?: number
  category?: string
  category_id?: string
  source_id?: string
  channel_type?: ApiChannelType
  active?: boolean
  event_start_from?: string
  event_start_to?: string
  enabled?: boolean
}

async function getData<T>(path: string, params?: QueryParams): Promise<T> {
  const response = await httpClient.get<T>(path, params ? { params } : undefined)
  return response.data
}

async function postData<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  const response = signal === undefined
    ? await httpClient.post<T>(path, payload)
    : await httpClient.post<T>(path, payload, { signal })
  return response.data
}

export const apiService = {
  getOverview: (): Promise<OverviewResponse> => getData(`${API_V1_PREFIX}/overview`),
  getServers: (params?: ServerListParams): Promise<ServerPageResponse> =>
    getData(`${API_V1_PREFIX}/servers`, params),
  getServer: (serverId: number): Promise<ServerResponse> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}`),
  getServerMetrics: (serverId: number, limit = 1): Promise<ServerMetricResponse[]> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}/metrics`, { limit }),
  getChannels: (params?: ChannelListParams): Promise<ChannelPageResponse> =>
    getData(`${API_V1_PREFIX}/channels`, params),
  getChannelMetrics: (channelId: number, limit = 1): Promise<ChannelMetricResponse[]> =>
    getData(`${API_V1_PREFIX}/channels/${channelId}/metrics`, { limit }),
  getAlerts: (): Promise<AlertsResponse> => getData(`${API_V1_PREFIX}/alerts`),
  getCollectionStatus: (): Promise<CollectionStatusResponse> =>
    getData(`${API_V1_PREFIX}/collection/status`),
  getHealth: (): Promise<HealthResponse> => getData('/health'),
  getBalance: (): Promise<BalanceResponse> => getData(`${API_V1_PREFIX}/balance`),
  getRecommendations: (): Promise<RecommendationsResponse> =>
    getData(`${API_V1_PREFIX}/recommendations`),
  startOnboarding: (payload: OnboardingStartRequest, signal?: AbortSignal): Promise<OnboardingResponse> =>
    postData<OnboardingResponse>(`${API_V1_PREFIX}/onboarding`, payload, signal),
  discoverOnboarding: (payload: OnboardingDiscoveryRequest, signal?: AbortSignal): Promise<OnboardingDiscoveryResponse> =>
    postData<OnboardingDiscoveryResponse>(`${API_V1_PREFIX}/onboarding/discover`, payload, signal),
  testSSHConnection: (payload: OnboardingTestSSHRequest, signal?: AbortSignal): Promise<OnboardingTestSSHResponse> =>
    postData<OnboardingTestSSHResponse>(`${API_V1_PREFIX}/onboarding/test-ssh`, payload, signal),
  getOnboarding: (onboardingId: number): Promise<OnboardingResponse> =>
    getData(`${API_V1_PREFIX}/onboarding/${onboardingId}`),
  getOnboardingAudit: (onboardingId: number): Promise<OnboardingAuditResponse[]> =>
    getData(`${API_V1_PREFIX}/onboarding/${onboardingId}/audit`),
  getOnboardingHealth: (onboardingId: number): Promise<OnboardingHealthResponse> =>
    getData(`${API_V1_PREFIX}/onboarding/${onboardingId}/health`),
  diagnoseOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingDiagnosisResponse> =>
    httpClient.post<OnboardingDiagnosisResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/diagnose`, payload).then(({ data }) => data),
  retryOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/retry`, payload).then(({ data }) => data),
  cancelOnboarding: (onboardingId: number): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/cancel`).then(({ data }) => data),
  rollbackOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/rollback`, payload).then(({ data }) => data),
  maintenance: (
    serverId: number,
    action: MaintenanceAction,
    payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'> & { target_version?: string },
  ): Promise<MaintenanceResponse> =>
    httpClient.post<MaintenanceResponse>(`${API_V1_PREFIX}/onboarding/server/${serverId}/maintenance/${action}`, payload).then(({ data }) => data),
  updateAlert: (alertId: number, status: 'active' | 'acknowledged' | 'resolved') =>
    httpClient.patch(`${API_V1_PREFIX}/alerts/${alertId}`, { status }),
}
