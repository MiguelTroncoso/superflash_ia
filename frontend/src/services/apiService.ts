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
  updateAlert: (alertId: number, status: 'active' | 'acknowledged' | 'resolved') =>
    httpClient.patch(`${API_V1_PREFIX}/alerts/${alertId}`, { status }),
}
