import { httpClient } from './httpClient'
import type {
  AlertsResponse,
  ChannelResponse,
  CollectionStatusResponse,
  HealthResponse,
  OverviewResponse,
  ServerMetricResponse,
  ServerResponse,
} from '../types/api'

const API_V1_PREFIX = '/api/v1'

async function getData<T>(path: string, params?: Record<string, number>): Promise<T> {
  const response = await httpClient.get<T>(path, params ? { params } : undefined)
  return response.data
}

export const apiService = {
  getOverview: (): Promise<OverviewResponse> => getData(`${API_V1_PREFIX}/overview`),
  getServers: (): Promise<ServerResponse[]> => getData(`${API_V1_PREFIX}/servers`),
  getServerMetrics: (serverId: number): Promise<ServerMetricResponse[]> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}/metrics`, { limit: 1 }),
  getChannels: (): Promise<ChannelResponse[]> => getData(`${API_V1_PREFIX}/channels`),
  getAlerts: (): Promise<AlertsResponse> => getData(`${API_V1_PREFIX}/alerts`),
  getCollectionStatus: (): Promise<CollectionStatusResponse> =>
    getData(`${API_V1_PREFIX}/collection/status`),
  getHealth: (): Promise<HealthResponse> => getData('/health'),
}
