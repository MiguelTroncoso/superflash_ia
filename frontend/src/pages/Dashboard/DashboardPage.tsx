import { PageHeader } from '../../components/common/PageHeader'
import { DashboardContent } from '../../components/dashboard/DashboardContent'
import { DashboardState } from '../../components/dashboard/DashboardState'
import { useDashboardData } from '../../hooks/useDashboardData'
import { usePageTitle } from '../../hooks/usePageTitle'

export function DashboardPage(): React.JSX.Element {
  usePageTitle('Dashboard')
  const dashboard = useDashboardData()

  if (dashboard.isLoading) {
    return (
      <>
        <PageHeader
          eyebrow="Operations center"
          title="SuperFlash Monitor"
          description="Loading live read-only infrastructure data."
        />
        <DashboardState state="loading" />
      </>
    )
  }

  if (dashboard.isError) {
    return (
      <>
        <PageHeader
          eyebrow="Operations center"
          title="SuperFlash Monitor"
          description="Live data is unavailable; no placeholder values are shown."
        />
        <DashboardState
          state="error"
          message="The monitoring API could not provide a complete dashboard response."
          onRetry={() => void dashboard.refetch()}
        />
      </>
    )
  }

  if (dashboard.isEmpty || !dashboard.summary || !dashboard.health || !dashboard.collectionStatus) {
    return (
      <>
        <PageHeader
          eyebrow="Operations center"
          title="SuperFlash Monitor"
          description="The API is reachable, but no current server samples are available."
        />
        <DashboardState state="empty" />
      </>
    )
  }

  return (
    <>
      <PageHeader
        eyebrow="Operations center"
        title="SuperFlash Monitor"
        description="Live read-only infrastructure data from the FastAPI monitoring service."
      />
      <DashboardContent
        summary={dashboard.summary}
        rows={dashboard.rows}
        health={dashboard.health}
        collectionStatus={dashboard.collectionStatus}
        isFetching={dashboard.isFetching}
        isStale={dashboard.isStale}
        lastUpdatedAt={dashboard.lastUpdatedAt}
        onRefresh={() => void dashboard.refetch()}
      />
    </>
  )
}
