export type HealthState = 'healthy' | 'warning' | 'critical'

export type MetricTone = 'cyan' | 'violet' | 'amber' | 'emerald' | 'rose' | 'slate'

export interface MetricDefinition {
  label: string
  value: string
  detail: string
  trend?: string
  trendPositive?: boolean
  tone: MetricTone
}

export interface TimeSeriesPoint {
  time: string
  cpu: number
  memory: number
}

export interface TrafficPoint {
  time: string
  inbound: number
  outbound: number
}

export interface ActivityItem {
  id: string
  title: string
  description: string
  time: string
  state: HealthState
}

export interface ServerSummary {
  name: string
  host: string
  role: string
  cpu: number
  memory: number
  network: string
  state: HealthState
}

export interface ChannelSummary {
  name: string
  category: string
  viewers: string
  bitrate: string
  state: HealthState
}
