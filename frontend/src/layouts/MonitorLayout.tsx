import { Outlet } from 'react-router'
import { Sidebar } from '../components/layout/Sidebar'
import { Topbar } from '../components/layout/Topbar'
import { useUiStore } from '../store/uiStore'

export function MonitorLayout(): React.JSX.Element {
  const isCollapsed = useUiStore((state) => state.isSidebarCollapsed)

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar isCollapsed={isCollapsed} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-[1600px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
