import { Bell, ChevronDown, Menu, PanelLeftClose, PanelLeftOpen, Search } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { useUiStore } from '../../store/uiStore'
import { cn } from '../../utils/formatters'

const pageNames: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/servers': 'Servers',
  '/channels': 'Channels',
  '/alerts': 'Alerts',
  '/balance': 'Balance',
  '/recommendations': 'Recommendations',
  '/settings': 'Settings',
}

export function Topbar(): React.JSX.Element {
  const location = useLocation()
  const isCollapsed = useUiStore((state) => state.isSidebarCollapsed)
  const toggleSidebar = useUiStore((state) => state.toggleSidebar)
  const openMobileSidebar = useUiStore((state) => state.openMobileSidebar)
  const pageName = pageNames[location.pathname] ?? 'Dashboard'

  return (
    <header className="sticky top-0 z-20 flex h-20 items-center justify-between border-b border-line bg-canvas/80 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <button
          aria-label="Open navigation"
          className="rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy lg:hidden"
          onClick={openMobileSidebar}
        >
          <Menu size={20} />
        </button>
        <button
          aria-label="Toggle sidebar"
          className="hidden rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy lg:block"
          onClick={toggleSidebar}
        >
          {isCollapsed ? <PanelLeftOpen size={19} /> : <PanelLeftClose size={19} />}
        </button>
        <div className="hidden h-6 w-px bg-line sm:block" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-copy">{pageName}</p>
          <p className="hidden text-xs text-muted sm:block">SuperFlash Monitor / Operations</p>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        <div className="hidden items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2 text-xs text-muted md:flex">
          <Search size={15} />
          <span>Search workspace</span>
          <kbd className="ml-6 rounded border border-line px-1.5 py-0.5 text-[10px] text-muted">
            ⌘ K
          </kbd>
        </div>
        <button
          aria-label="Notifications"
          className="relative rounded-lg p-2.5 text-muted hover:bg-panel-raised hover:text-copy"
        >
          <Bell size={18} />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-warning ring-2 ring-canvas" />
        </button>
        <div className="hidden h-7 w-px bg-line sm:block" />
        <button className="flex items-center gap-2 rounded-xl p-1.5 pr-2 hover:bg-panel-raised">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-400 to-teal-500 text-xs font-bold text-slate-950">
            MT
          </span>
          <span className="hidden text-left sm:block">
            <span className="block text-xs font-semibold text-copy">Monitor team</span>
            <span className="block text-[10px] text-muted">Operator</span>
          </span>
          <ChevronDown size={15} className={cn('hidden text-muted sm:block')} />
        </button>
      </div>
    </header>
  )
}
