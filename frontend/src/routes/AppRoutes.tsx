import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { MonitorLayout } from '../layouts/MonitorLayout'

const ChannelsPage = lazy(() =>
  import('../pages/Channels/ChannelsPage').then((module) => ({ default: module.ChannelsPage })),
)
const DashboardPage = lazy(() =>
  import('../pages/Dashboard/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const AlertsPage = lazy(() =>
  import('../pages/Alerts/AlertsPage').then((module) => ({ default: module.AlertsPage })),
)
const BalancePage = lazy(() =>
  import('../pages/Balance/BalancePage').then((module) => ({ default: module.BalancePage })),
)
const RecommendationsPage = lazy(() =>
  import('../pages/Recommendations/RecommendationsPage').then((module) => ({ default: module.RecommendationsPage })),
)
const ServersPage = lazy(() =>
  import('../pages/Servers/ServersPage').then((module) => ({ default: module.ServersPage })),
)
const ServerDetailPage = lazy(() =>
  import('../pages/Servers/ServerDetailPage').then((module) => ({ default: module.ServerDetailPage })),
)
const SettingsPage = lazy(() =>
  import('../pages/Settings/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)

function PageFallback(): React.JSX.Element {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted">
      Loading workspace…
    </div>
  )
}

export function AppRoutes(): React.JSX.Element {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route element={<MonitorLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="servers" element={<ServersPage />} />
          <Route path="server/:serverId" element={<ServerDetailPage />} />
          <Route path="channels" element={<ChannelsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="balance" element={<BalancePage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
