import { ReactNode, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Inbox,
  Clock,
  CheckCircle2,
  Eye,
  Edit3,
  Activity,
  Settings,
  HelpCircle,
  GitCompare,
} from 'lucide-react'
import { systemApi } from '@/services/api'
import { normalizeRawId, buildResultPath } from '@/lib/routeParsing'
import { cn } from '@/utils'
import type { StatusCounts, Stats } from '@/types'

interface LayoutProps {
  children: ReactNode
}

interface NavItem {
  name: string
  path: string
  icon: ReactNode
  description: string
}

const navItems: NavItem[] = [
  {
    name: 'Inbox',
    path: '/inbox',
    icon: <Inbox size={20} />,
    description: 'Upload new lab reports',
  },
  {
    name: 'Queue',
    path: '/queue',
    icon: <Clock size={20} />,
    description: 'View processing status',
  },
  {
    name: 'Processed',
    path: '/processed',
    icon: <CheckCircle2 size={20} />,
    description: 'Browse completed results',
  },
]

export function Layout({ children }: LayoutProps) {
  const location = useLocation()

  const DEFAULT_STATS: Stats = { status_counts: { queued: 0, processing: 0, failed: 0, completed: 0 } }
  const [error, setError] = useState<string | null>(null)

  // Get system stats for the header
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: systemApi.getStats,
    refetchInterval: 30000, // Refresh every 30 seconds
    onError: (err: any) => {
      setError(err?.message || 'Failed to fetch stats')
    },
    onSuccess: () => {
      setError(null)
    }
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: systemApi.health,
    refetchInterval: 60000, // Refresh every minute
  })

  // Collapsible site menu state (persisted)
  const [menuCollapsed, setMenuCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem('labai.menu.collapsed') === 'true' } catch { return false }
  })
  const toggleMenu = () => setMenuCollapsed(v => { try { localStorage.setItem('labai.menu.collapsed', String(!v)) } catch {} ; return !v })

  // Keyboard shortcut: Cmd/Ctrl + Shift + M toggles menu
  if (typeof window !== 'undefined') {
    // attach once per mount
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).__labai_menu_shortcut || (window.addEventListener('keydown', (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'M' || e.key === 'm')) {
        e.preventDefault()
        toggleMenu()
      }
    }), (window as any).__labai_menu_shortcut = true)
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar */}
      <div className={cn(menuCollapsed ? 'w-12' : 'w-64', 'bg-white shadow-sm border-r border-gray-200 flex flex-col transition-all duration-200')}>
        {/* Logo and title */}
        <div className="p-3 border-b border-gray-200">
          <div className={cn('flex items-center', menuCollapsed ? 'justify-center' : 'justify-between')}>
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-600 rounded-lg flex items-center justify-center">
                <Activity size={18} className="text-white" />
              </div>
              {!menuCollapsed && (
                <div>
                  <h1 className="text-lg font-semibold text-gray-900">Lab AI</h1>
                  <p className="text-xs text-gray-500">Report Processing</p>
                </div>
              )}
            </div>
            {!menuCollapsed && (
              <button onClick={toggleMenu} className="text-xs text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100" aria-label="Collapse Menu" title="Collapse Menu (Cmd+Shift+M)">
                Collapse
              </button>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className={cn('flex-1', menuCollapsed ? 'p-2' : 'p-4', 'space-y-1')}>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700 border border-primary-200'
                    : 'text-gray-700 hover:bg-gray-100'
                )}
                title={menuCollapsed ? item.name : undefined}
              >
                <span className={cn(isActive ? 'text-primary-600' : 'text-gray-400')}>
                  {item.icon}
                </span>
                {!menuCollapsed && (
                  <div>
                    <div>{item.name}</div>
                    <div className="text-xs text-gray-500">{item.description}</div>
                  </div>
                )}
              </Link>
            )
          })}
        </nav>

        {/* System status */}
        <div className={cn('border-t border-gray-200', menuCollapsed ? 'p-2' : 'p-4')}>
          {!menuCollapsed && <div className="text-xs text-gray-500 mb-2">System Status</div>}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className={cn(menuCollapsed && 'sr-only')}>API</span>
              <span className={cn(
                'w-2 h-2 rounded-full',
                health?.status === 'healthy' ? 'bg-success-500' : 'bg-error-500'
              )} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className={cn(menuCollapsed && 'sr-only')}>Redis</span>
              <span className={cn(
                'w-2 h-2 rounded-full',
                health?.redis === 'connected' ? 'bg-success-500' : 'bg-error-500'
              )} />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className={cn(menuCollapsed && 'sr-only')}>Workers</span>
              <span className={cn(
                'w-2 h-2 rounded-full',
                health?.celery === 'connected' ? 'bg-success-500' : 'bg-warning-500'
              )} />
            </div>
            {!menuCollapsed && error && <div className="text-amber-600 text-sm">API unavailable or returned invalid data.</div>}
            {!menuCollapsed && (stats || DEFAULT_STATS) && (
              <div className="text-xs text-gray-600 mt-2 pt-2 border-t border-gray-100">
                <div>Total Jobs: {stats?.total_jobs ?? 0}</div>
                <div className="flex justify-between">
                  <span>Processing: {stats?.status_counts?.processing ?? 0}</span>
                  <span>Queued: {stats?.status_counts?.queued ?? 0}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Help link */}
        <div className="border-t border-gray-200">
          <div className={cn(menuCollapsed ? 'p-2' : 'p-4')}>
            <button className="flex items-center space-x-2 text-xs text-gray-500 hover:text-gray-700 transition-colors" title={menuCollapsed ? 'Help & Documentation' : undefined}>
              <HelpCircle size={14} />
              {!menuCollapsed && <span>Help & Documentation</span>}
            </button>
          </div>
          {menuCollapsed && (
            <div className="p-2 flex items-center justify-center">
              <button
                onClick={toggleMenu}
                className="text-[11px] text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-100"
                aria-label="Expand Menu"
                title="Expand Menu (Cmd+Shift+M)"
              >
                Expand
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {(() => {
                  const navItem = navItems.find(item => item.path === location.pathname)
                  if (navItem) return navItem.name
                  if (location.pathname.startsWith('/viewer/')) return 'Result Viewer'
                  if (location.pathname.startsWith('/review/')) return 'Manual Review'
                  if (location.pathname.startsWith('/compare/')) return 'Compare Results'
                  return 'Lab AI'
                })()}
              </h2>
              <p className="text-sm text-gray-600">
                {(() => {
                  const navItem = navItems.find(item => item.path === location.pathname)
                  if (navItem) return navItem.description
                  if (location.pathname.startsWith('/viewer/')) return 'View processed results in detail'
                  if (location.pathname.startsWith('/review/')) return 'Review and correct results'
                  if (location.pathname.startsWith('/compare/')) return 'Compare original vs corrected results'
                  return 'AI-powered lab report processing'
                })()}
              </p>
            </div>
            
            {/* Quick actions */}
            <div className="flex items-center space-x-3">
              {location.pathname.startsWith('/viewer/') && (() => {
                const raw = location.pathname.slice('/viewer/'.length)
                const parsed = normalizeRawId(raw)
                const compareTo = `/compare/${parsed.baseId || raw}`
                const reviewTo = buildResultPath('review', parsed.baseId, {
                  stage: parsed.stage,
                  flags: parsed.flags.length ? parsed.flags : undefined
                })
                return (
                  <>
                    <Link to={compareTo} className="btn-ghost flex items-center space-x-2">
                      <GitCompare size={16} />
                      <span>Compare</span>
                    </Link>
                    <Link to={reviewTo} className="btn-primary flex items-center space-x-2">
                      <Edit3 size={16} />
                      <span>Review & Edit</span>
                    </Link>
                  </>
                )
              })()}

              {location.pathname.startsWith('/review/') && (() => {
                const raw = location.pathname.slice('/review/'.length)
                const parsed = normalizeRawId(raw)
                const compareTo = `/compare/${parsed.baseId || raw}`
                const viewerTo = buildResultPath('viewer', parsed.baseId, {
                  stage: parsed.stage,
                  flags: parsed.flags.length ? parsed.flags : undefined
                })
                return (
                  <>
                    <Link to={compareTo} className="btn-ghost flex items-center space-x-2">
                      <GitCompare size={16} />
                      <span>Compare</span>
                    </Link>
                    <Link to={viewerTo} className="btn-ghost flex items-center space-x-2">
                      <Eye size={16} />
                      <span>View Only</span>
                    </Link>
                  </>
                )
              })()}

              {location.pathname.startsWith('/compare/') && (() => {
                const raw = location.pathname.slice('/compare/'.length)
                const parsed = normalizeRawId(raw)
                const viewerTo = buildResultPath('viewer', parsed.baseId, {
                  stage: parsed.stage,
                  flags: parsed.flags.length ? parsed.flags : undefined
                })
                const reviewTo = buildResultPath('review', parsed.baseId, {
                  stage: parsed.stage,
                  flags: parsed.flags.length ? parsed.flags : undefined
                })
                return (
                  <>
                    <Link to={viewerTo} className="btn-ghost flex items-center space-x-2">
                      <Eye size={16} />
                      <span>View</span>
                    </Link>
                    <Link to={reviewTo} className="btn-primary flex items-center space-x-2">
                      <Edit3 size={16} />
                      <span>Review</span>
                    </Link>
                  </>
                )
              })()}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
