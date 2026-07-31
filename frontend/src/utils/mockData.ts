import type {
  ActivityItem,
  ChannelSummary,
  HealthState,
  ServerSummary,
  TimeSeriesPoint,
  TrafficPoint,
} from '../types/monitoring'

export const loadSeries: TimeSeriesPoint[] = [
  { time: '00:00', cpu: 38, memory: 52 },
  { time: '04:00', cpu: 31, memory: 49 },
  { time: '08:00', cpu: 47, memory: 56 },
  { time: '12:00', cpu: 62, memory: 63 },
  { time: '16:00', cpu: 54, memory: 59 },
  { time: '20:00', cpu: 69, memory: 67 },
  { time: '24:00', cpu: 45, memory: 54 },
]

export const trafficSeries: TrafficPoint[] = [
  { time: '00:00', inbound: 14, outbound: 92 },
  { time: '04:00', inbound: 11, outbound: 76 },
  { time: '08:00', inbound: 19, outbound: 118 },
  { time: '12:00', inbound: 25, outbound: 146 },
  { time: '16:00', inbound: 22, outbound: 131 },
  { time: '20:00', inbound: 29, outbound: 168 },
  { time: '24:00', inbound: 16, outbound: 104 },
]

export const activityItems: ActivityItem[] = [
  {
    id: 'collection',
    title: 'Collection cycle completed',
    description: 'Mock source · 5 servers · 24 channels',
    time: '2 min ago',
    state: 'healthy',
  },
  {
    id: 'capacity',
    title: 'Capacity threshold approaching',
    description: 'sf-edge-03 · network utilization at 82%',
    time: '18 min ago',
    state: 'warning',
  },
  {
    id: 'heartbeat',
    title: 'Heartbeat received',
    description: 'sf-core-01 · scheduler is responding',
    time: '23 min ago',
    state: 'healthy',
  },
  {
    id: 'latency',
    title: 'Latency observation created',
    description: 'sf-edge-05 · no action taken',
    time: '41 min ago',
    state: 'warning',
  },
]

export const serverSummaries: ServerSummary[] = [
  {
    name: 'sf-core-01',
    host: 'core-a',
    role: 'Control plane',
    cpu: 42,
    memory: 58,
    network: '84 Mbps',
    state: 'healthy',
  },
  {
    name: 'sf-edge-02',
    host: 'edge-b',
    role: 'Streaming edge',
    cpu: 68,
    memory: 71,
    network: '126 Mbps',
    state: 'healthy',
  },
  {
    name: 'sf-edge-03',
    host: 'edge-c',
    role: 'Streaming edge',
    cpu: 79,
    memory: 76,
    network: '164 Mbps',
    state: 'warning',
  },
  {
    name: 'sf-vod-04',
    host: 'vod-a',
    role: 'VOD storage',
    cpu: 35,
    memory: 63,
    network: '92 Mbps',
    state: 'healthy',
  },
]

export const channelSummaries: ChannelSummary[] = [
  { name: 'News 24', category: 'News', viewers: '18.4K', bitrate: '4.8 Mbps', state: 'healthy' },
  {
    name: 'Cinema One',
    category: 'Movies',
    viewers: '12.7K',
    bitrate: '6.2 Mbps',
    state: 'healthy',
  },
  {
    name: 'Arena Live',
    category: 'Sports',
    viewers: '9.8K',
    bitrate: '5.4 Mbps',
    state: 'warning',
  },
  {
    name: 'Kids World',
    category: 'Family',
    viewers: '7.3K',
    bitrate: '3.6 Mbps',
    state: 'healthy',
  },
]

export const alertSummary: Array<{ label: string; count: number; state: HealthState }> = [
  { label: 'Critical', count: 0, state: 'critical' },
  { label: 'Warning', count: 2, state: 'warning' },
  { label: 'Informational', count: 7, state: 'healthy' },
]
