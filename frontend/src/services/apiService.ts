import { httpClient } from './httpClient'
import type {
  AlertsResponse,
  BalanceResponse,
  ChannelMetricResponse,
  ChannelResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerMetricResponse,
  ServerResponse,
  RecommendationsResponse,
} from '../types/api'

const API_V1_PREFIX = '/api/v1'

async function getData<T>(path: string, params?: Record<string, number>): Promise<T> {
  const response = await httpClient.get<T>(path, params ? { params } : undefined)
  return response.data
}

export const apiService = {
  getOverview: (): Promise<OverviewResponse> => getData(`${API_V1_PREFIX}/overview`),
  getServers: (): Promise<ServerResponse[]> => getData(`${API_V1_PREFIX}/servers`),
  getServer: (serverId: number): Promise<ServerResponse> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}`),
  getServerMetrics: (serverId: number, limit = 1): Promise<ServerMetricResponse[]> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}/metrics`, { limit }),
  getChannels: (): Promise<ChannelResponse[]> => getData(`${API_V1_PREFIX}/channels`),
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
