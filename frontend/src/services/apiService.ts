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
  startOnboarding: (payload: OnboardingStartRequest): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding`, payload).then(({ data }) => data),
  getOnboarding: (onboardingId: number): Promise<OnboardingResponse> =>
    getData(`${API_V1_PREFIX}/onboarding/${onboardingId}`),
  getOnboardingAudit: (onboardingId: number): Promise<OnboardingAuditResponse[]> =>
    getData(`${API_V1_PREFIX}/onboarding/${onboardingId}/audit`),
  diagnoseOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingDiagnosisResponse> =>
    httpClient.post<OnboardingDiagnosisResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/diagnose`, payload).then(({ data }) => data),
  retryOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/retry`, payload).then(({ data }) => data),
  cancelOnboarding: (onboardingId: number): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/cancel`).then(({ data }) => data),
  rollbackOnboarding: (onboardingId: number, payload: Pick<OnboardingStartRequest, 'auth_method' | 'password' | 'private_key'>): Promise<OnboardingResponse> =>
    httpClient.post<OnboardingResponse>(`${API_V1_PREFIX}/onboarding/${onboardingId}/rollback`, payload).then(({ data }) => data),
  updateAlert: (alertId: number, status: 'active' | 'acknowledged' | 'resolved') =>
    httpClient.patch(`${API_V1_PREFIX}/alerts/${alertId}`, { status }),
}
