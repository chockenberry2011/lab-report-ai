import React, { useState, useEffect } from 'react'
import { ChevronUp, ChevronDown, Target, Search, Filter, CheckCircle2, AlertTriangle } from 'lucide-react'
import { cn } from '@/utils'

interface NavigationItem {
  path: string
  label: string
  type: 'issue' | 'warning' | 'completed'
  page?: number
  line?: number
}

interface FloatingNavigationWidgetProps {
  issues: NavigationItem[]
  currentIndex: number
  onNavigate: (index: number) => void
  onJumpToPdf?: (fieldPath: string) => void
  className?: string
}

export function FloatingNavigationWidget({
  issues,
  currentIndex,
  onNavigate,
  onJumpToPdf,
  className = ''
}: FloatingNavigationWidgetProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [searchFilter, setSearchFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'issue' | 'warning' | 'completed'>('all')
  const [isMobile, setIsMobile] = useState(false)
  const [isTablet, setIsTablet] = useState(false)

  // Responsive breakpoint detection
  useEffect(() => {
    const updateBreakpoints = () => {
      const width = window.innerWidth
      setIsMobile(width < 768)
      setIsTablet(width >= 768 && width < 1024)
    }

    updateBreakpoints()
    window.addEventListener('resize', updateBreakpoints)
    return () => window.removeEventListener('resize', updateBreakpoints)
  }, [])

  const filteredIssues = issues.filter(item => {
    const matchesSearch = !searchFilter ||
      item.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
      item.path.toLowerCase().includes(searchFilter.toLowerCase())

    const matchesType = typeFilter === 'all' || item.type === typeFilter

    return matchesSearch && matchesType
  })

  const currentIssue = issues[currentIndex]

  if (issues.length === 0) {
    return null
  }

  return (
    <div className={cn(
      'fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg',
      isMobile
        ? 'bottom-4 left-4 right-4'
        : isTablet
        ? 'right-4 top-1/2 transform -translate-y-1/2'
        : 'right-6 top-1/2 transform -translate-y-1/2',
      className
    )}>
      {/* Compact View */}
      {!isExpanded && (
        <div className={isMobile ? 'p-2' : 'p-3'}>
          <div className={cn(
            'flex items-center justify-between gap-3',
            isMobile ? 'min-w-0' : 'min-w-[200px]'
          )}>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                {currentIssue?.type === 'issue' && <AlertTriangle size={14} className="text-amber-500" />}
                {currentIssue?.type === 'warning' && <AlertTriangle size={14} className="text-orange-500" />}
                {currentIssue?.type === 'completed' && <CheckCircle2 size={14} className="text-green-500" />}
                <span className="text-sm font-medium">
                  {currentIndex + 1} / {issues.length}
                </span>
              </div>
              {currentIssue && (
                <span className="text-xs text-gray-600 truncate max-w-[100px]">
                  {currentIssue.label}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => onNavigate(Math.max(0, currentIndex - 1))}
                disabled={currentIndex <= 0}
                className="p-1 hover:bg-gray-100 rounded disabled:opacity-50"
                title="Previous (P)"
              >
                <ChevronUp size={14} />
              </button>
              <button
                onClick={() => onNavigate(Math.min(issues.length - 1, currentIndex + 1))}
                disabled={currentIndex >= issues.length - 1}
                className="p-1 hover:bg-gray-100 rounded disabled:opacity-50"
                title="Next (N)"
              >
                <ChevronDown size={14} />
              </button>
              <button
                onClick={() => setIsExpanded(true)}
                className="p-1 hover:bg-gray-100 rounded"
                title="Expand navigation"
              >
                <Target size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Expanded View */}
      {isExpanded && (
        <div className="w-80">
          {/* Header */}
          <div className="p-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900">Field Navigation</h3>
              <button
                onClick={() => setIsExpanded(false)}
                className="text-gray-400 hover:text-gray-600"
                title="Collapse"
              >
                ×
              </button>
            </div>

            {/* Search and Filters */}
            <div className="mt-2 space-y-2">
              <div className="relative">
                <Search size={14} className="absolute left-2 top-2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search fields..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-7 pr-3 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex gap-1">
                {(['all', 'issue', 'warning', 'completed'] as const).map(type => (
                  <button
                    key={type}
                    onClick={() => setTypeFilter(type)}
                    className={cn(
                      'px-2 py-1 text-xs rounded transition-colors',
                      typeFilter === type
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    )}
                  >
                    {type === 'all' ? 'All' : type === 'issue' ? 'Issues' : type === 'warning' ? 'Warnings' : 'Done'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Issue List */}
          <div className="max-h-80 overflow-y-auto">
            {filteredIssues.map((item, index) => {
              const originalIndex = issues.findIndex(issue => issue.path === item.path)
              const isActive = originalIndex === currentIndex

              return (
                <div
                  key={item.path}
                  className={cn(
                    'p-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors',
                    isActive && 'bg-blue-50 border-blue-200'
                  )}
                  onClick={() => onNavigate(originalIndex)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {item.type === 'issue' && <AlertTriangle size={12} className="text-amber-500 flex-shrink-0" />}
                        {item.type === 'warning' && <AlertTriangle size={12} className="text-orange-500 flex-shrink-0" />}
                        {item.type === 'completed' && <CheckCircle2 size={12} className="text-green-500 flex-shrink-0" />}
                        <span className="text-sm font-medium text-gray-900 truncate">
                          {item.label}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {item.path}
                      </div>
                      {(item.page || item.line) && (
                        <div className="text-xs text-gray-400 mt-1">
                          {item.page && `Page ${item.page}`}
                          {item.page && item.line && ', '}
                          {item.line && `Line ${item.line}`}
                        </div>
                      )}
                    </div>

                    {onJumpToPdf && (item.page || item.line) && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onJumpToPdf(item.path)
                        }}
                        className="text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-100 px-1 py-0.5 rounded"
                        title="Jump to PDF"
                      >
                        PDF
                      </button>
                    )}
                  </div>
                </div>
              )
            })}

            {filteredIssues.length === 0 && (
              <div className="p-4 text-center text-gray-500 text-sm">
                No items match your filters
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-600">
            <div className="flex justify-between items-center">
              <span>Showing {filteredIssues.length} of {issues.length}</span>
              <span>Use N/P keys to navigate</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}