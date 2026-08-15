import { httpClient } from './httpClient'
import type {
  AlertsResponse,
  CapacityOverviewResponse,
  CostsSummaryResponse,
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
  ServerDiagnosticResponse,
  ServerInventorySnapshotResponse,
  ServerWriteInput,
  RecommendationsResponse,
  SimulationListResponse,
  SimulationRequestInput,
  SimulationResponse,
  IntelligenceRecommendationsResponse,
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
  diagnoseServer: (serverId: number): Promise<ServerDiagnosticResponse> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}/diagnose`),
  getServerInventory: (serverId: number): Promise<ServerInventorySnapshotResponse | null> =>
    getData(`${API_V1_PREFIX}/servers/${serverId}/inventory`),
  createServer: (payload: ServerWriteInput): Promise<ServerResponse> =>
    httpClient.post<ServerResponse>(`${API_V1_PREFIX}/servers`, payload).then((response) => response.data),
  updateServer: (serverId: number, payload: Partial<ServerWriteInput>): Promise<ServerResponse> =>
    httpClient.patch<ServerResponse>(`${API_V1_PREFIX}/servers/${serverId}`, payload).then((response) => response.data),
  deleteServer: (serverId: number): Promise<void> =>
    httpClient.delete(`${API_V1_PREFIX}/servers/${serverId}`).then(() => undefined),
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
  getCapacityOverview: (): Promise<CapacityOverviewResponse> =>
    getData(`${API_V1_PREFIX}/capacity/overview`),
  getCapacityServers: (): Promise<CapacityOverviewResponse['servers']> =>
    getData(`${API_V1_PREFIX}/capacity/servers`),
  getCostsSummary: (): Promise<CostsSummaryResponse> =>
    getData(`${API_V1_PREFIX}/costs/summary`),
  getUpcomingCosts: (days = 30) =>
    getData<CostsSummaryResponse['upcoming']>(`${API_V1_PREFIX}/costs/upcoming`, { days }),
  getSimulations: (page = 1, pageSize = 50): Promise<SimulationListResponse> =>
    getData(`${API_V1_PREFIX}/simulations`, { page, page_size: pageSize }),
  createSimulation: (payload: SimulationRequestInput): Promise<SimulationResponse> =>
    httpClient.post<SimulationResponse>(`${API_V1_PREFIX}/simulations`, payload).then((response) => response.data),
  getIntelligenceRecommendations: (): Promise<IntelligenceRecommendationsResponse> =>
    getData(`${API_V1_PREFIX}/intelligence/recommendations`),
  updateAlert: (alertId: number, status: 'active' | 'acknowledged' | 'resolved') =>
    httpClient.patch(`${API_V1_PREFIX}/alerts/${alertId}`, { status }),
}
