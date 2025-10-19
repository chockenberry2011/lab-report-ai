import React from 'react'
import { cn } from '@/utils'
import { X, Maximize2, Minimize2 } from 'lucide-react'

interface PanelProps {
  title?: string
  subtitle?: string
  icon?: React.ReactNode
  badge?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  collapsible?: boolean
  closeable?: boolean
  collapsed?: boolean
  onCollapse?: (collapsed: boolean) => void
  onClose?: () => void
  className?: string
  headerClassName?: string
  contentClassName?: string
}

/**
 * Panel: Reusable panel component with header, content, and actions
 *
 * Features:
 * - Optional header with title, subtitle, icon, badge
 * - Custom actions in header
 * - Collapsible content
 * - Closeable panels
 * - Flexible styling
 */
export function Panel({
  title,
  subtitle,
  icon,
  badge,
  actions,
  children,
  collapsible = false,
  closeable = false,
  collapsed = false,
  onCollapse,
  onClose,
  className = '',
  headerClassName = '',
  contentClassName = ''
}: PanelProps) {
  const hasHeader = title || subtitle || icon || badge || actions || collapsible || closeable

  return (
    <div className={cn('flex flex-col h-full bg-white', className)}>
      {/* Panel Header */}
      {hasHeader && (
        <div className={cn(
          'flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gray-50 flex-shrink-0',
          headerClassName
        )}>
          <div className="flex items-center space-x-3 min-w-0">
            {icon && (
              <div className="flex-shrink-0 text-gray-500">
                {icon}
              </div>
            )}

            <div className="min-w-0 flex-1">
              {title && (
                <h3 className="text-sm font-medium text-gray-900 truncate">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="text-xs text-gray-500 truncate">
                  {subtitle}
                </p>
              )}
            </div>

            {badge && (
              <div className="flex-shrink-0">
                {badge}
              </div>
            )}
          </div>

          <div className="flex items-center space-x-2 flex-shrink-0">
            {actions}

            {collapsible && (
              <button
                onClick={() => onCollapse?.(!collapsed)}
                className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded transition-colors"
                title={collapsed ? 'Expand panel' : 'Collapse panel'}
              >
                {collapsed ? (
                  <Maximize2 className="h-4 w-4" />
                ) : (
                  <Minimize2 className="h-4 w-4" />
                )}
              </button>
            )}

            {closeable && (
              <button
                onClick={onClose}
                className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded transition-colors"
                title="Close panel"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Panel Content */}
      {!collapsed && (
        <div className={cn('flex-1 overflow-hidden', contentClassName)}>
          {children}
        </div>
      )}
    </div>
  )
}