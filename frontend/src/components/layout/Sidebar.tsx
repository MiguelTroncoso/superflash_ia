import { Bell, LayoutDashboard, Radio, Server, Settings2, X } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import brandMark from '../../assets/brand-mark.svg'
import { useUiStore } from '../../store/uiStore'
import { cn } from '../../utils/formatters'

const navItems = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Servers', path: '/servers', icon: Server },
  { label: 'Channels', path: '/channels', icon: Radio },
  { label: 'Alerts', path: '/alerts', icon: Bell, count: 2 },
  { label: 'Settings', path: '/settings', icon: Settings2 },
]

interface SidebarProps {
  isCollapsed: boolean
}

export function Sidebar({ isCollapsed }: SidebarProps): React.JSX.Element {
  const isMobileOpen = useUiStore((state) => state.isMobileSidebarOpen)
  const closeMobileSidebar = useUiStore((state) => state.closeMobileSidebar)

  return (
    <>
      {isMobileOpen && (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
          onClick={closeMobileSidebar}
        />
      )}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-panel/95 backdrop-blur-xl transition-all duration-300 lg:static lg:translate-x-0',
          isCollapsed ? 'lg:w-[88px]' : 'lg:w-64',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-20 items-center justify-between border-b border-line px-5">
          <div className="flex items-center gap-3 overflow-hidden">
            <img src={brandMark} alt="SuperFlash Monitor" className="h-9 w-9 shrink-0" />
            <div
              className={cn(
                'whitespace-nowrap transition-opacity',
                isCollapsed && 'lg:pointer-events-none lg:w-0 lg:opacity-0',
              )}
            >
              <p className="text-sm font-semibold tracking-wide text-copy">SuperFlash</p>
              <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-muted">
                Monitor
              </p>
            </div>
          </div>
          <button
            aria-label="Close navigation"
            className="rounded-lg p-2 text-muted hover:bg-panel-raised hover:text-copy lg:hidden"
            onClick={closeMobileSidebar}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3 py-6" aria-label="Primary navigation">
          <p
            className={cn(
              'mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted',
              isCollapsed && 'lg:sr-only',
            )}
          >
            Operations
          </p>
          {navItems.map(({ label, path, icon: Icon, count }) => (
            <NavLink
              key={path}
              to={path}
              onClick={closeMobileSidebar}
              title={isCollapsed ? label : undefined}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition',
                  isActive
                    ? 'bg-brand/10 text-brand'
                    : 'text-muted hover:bg-panel-raised hover:text-copy',
                  isCollapsed && 'lg:justify-center lg:px-0',
                )
              }
            >
              <Icon size={19} strokeWidth={1.8} />
              <span
                className={cn(
                  'flex-1 whitespace-nowrap transition-opacity',
                  isCollapsed && 'lg:pointer-events-none lg:w-0 lg:flex-none lg:opacity-0',
                )}
              >
                {label}
              </span>
              {count && !isCollapsed && (
                <span className="rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-bold text-warning">
                  {count}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={cn('border-t border-line p-4', isCollapsed && 'lg:px-3')}>
          <div
            className={cn(
              'rounded-xl bg-panel-raised p-3',
              isCollapsed && 'lg:flex lg:justify-center lg:bg-transparent lg:p-0',
            )}
          >
            <div className={cn('flex items-center gap-3', isCollapsed && 'lg:hidden')}>
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/15 text-xs font-bold text-brand">
                SF
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs font-semibold text-copy">Read-only mode</p>
                <p className="mt-0.5 text-[11px] text-muted">Mock environment</p>
              </div>
            </div>
            {isCollapsed && (
              <span className="hidden h-8 w-8 items-center justify-center rounded-lg bg-brand/15 text-xs font-bold text-brand lg:flex">
                SF
              </span>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
