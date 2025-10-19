import React, { useState, useCallback, useEffect } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Layers,
  Search,
  AlertTriangle,
  Eye,
  Focus,
  Navigation,
  FileText,
  Settings,
  Maximize2,
  Minimize2
} from 'lucide-react'
import { cn } from '@/utils'

interface UnifiedNavigationProps {
  // Section navigation
  sections: Array<{ key: string; title: string; dirty: boolean }>
  activeSection: string
  onSectionSelect: (key: string) => void

  // Issues management
  issues: Array<{ path: string; label: string; type: 'issue' | 'warning' | 'completed' }>
  currentIssueIndex: number
  onNavigateIssue: (index: number) => void
  onFocusField: (path: string) => void

  // Layout modes
  layoutMode: 'focus' | 'reference' | 'navigation'
  onLayoutModeChange: (mode: 'focus' | 'reference' | 'navigation') => void

  // Tabs
  activeTab: 'headers' | 'panels'
  onTabChange: (tab: 'headers' | 'panels') => void

  // Stats
  totalFields: number
  completedFields: number

  // Panels/test stats (for tab labels)
  panelsCount?: number
  testsCount?: number

  className?: string
  // Collapse control (driven by parent)
  collapsed?: boolean
  onCollapseChange?: (collapsed: boolean) => void
}

interface NavSection {
  id: string
  label: string
  icon: React.ReactNode
  badge?: number
  content: React.ReactNode
}

export function UnifiedNavigation({
  sections,
  activeSection,
  onSectionSelect,
  issues,
  currentIssueIndex,
  onNavigateIssue,
  onFocusField,
  layoutMode,
  onLayoutModeChange,
  activeTab,
  onTabChange,
  totalFields,
  completedFields,
  collapsed = false,
  onCollapseChange,
  panelsCount,
  testsCount,
  className = ''
}: UnifiedNavigationProps) {
  const [activeNavSection, setActiveNavSection] = useState<string>('sections')

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey) {
        switch (e.key) {
          case 'N':
            e.preventDefault()
            onCollapseChange?.(!collapsed)
            break
          case 'F':
            e.preventDefault()
            onLayoutModeChange('focus')
            break
          case 'R':
            e.preventDefault()
            onLayoutModeChange('reference')
            break
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onLayoutModeChange])

  const navSections: NavSection[] = [
    {
      id: 'sections',
      label: 'Sections',
      icon: <Layers size={16} />,
      content: (
        <div className="space-y-1">
          {sections.map(section => (
            <button
              key={section.key}
              onClick={() => onSectionSelect(section.key)}
              className={cn(
                'w-full text-left px-3 py-2 rounded text-sm transition-colors',
                activeSection === section.key
                  ? 'bg-blue-100 text-blue-700'
                  : 'hover:bg-gray-100 text-gray-700',
                section.dirty && 'font-medium'
              )}
            >
              <div className="flex items-center justify-between">
                <span>{section.title}</span>
                {section.dirty && (
                  <div className="w-2 h-2 bg-orange-400 rounded-full" />
                )}
              </div>
            </button>
          ))}
        </div>
      )
    },
    {
      id: 'issues',
      label: 'Issues',
      icon: <AlertTriangle size={16} />,
      badge: issues.filter(issue => issue.type === 'issue').length,
      content: (
        <div className="space-y-1">
          {issues.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-sm">
              No issues found
            </div>
          ) : (
            issues.map((issue, index) => (
              <button
                key={issue.path}
                onClick={() => {
                  onNavigateIssue(index)
                  onFocusField(issue.path)
                }}
                className={cn(
                  'w-full text-left px-3 py-2 rounded text-sm transition-colors',
                  currentIssueIndex === index
                    ? 'bg-amber-100 text-amber-700'
                    : 'hover:bg-gray-100 text-gray-700'
                )}
              >
                <div className="flex items-center gap-2">
                  {issue.type === 'issue' && <AlertTriangle size={12} className="text-amber-500" />}
                  {issue.type === 'warning' && <AlertTriangle size={12} className="text-orange-500" />}
                  <span className="truncate">{issue.label}</span>
                </div>
              </button>
            ))
          )}
        </div>
      )
    },
    {
      id: 'tabs',
      label: 'Content',
      icon: <FileText size={16} />,
      content: (
        <div className="space-y-3">
          <div className="flex border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => onTabChange('headers')}
              className={cn(
                'flex-1 px-3 py-2 text-sm transition-colors',
                activeTab === 'headers'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              )}
            >
              Headers
            </button>
            <button
              onClick={() => onTabChange('panels')}
              className={cn(
                'flex-1 px-3 py-2 text-sm transition-colors',
                activeTab === 'panels'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              )}
            >
              <span>Panels</span>
              {typeof testsCount === 'number' && testsCount > 0 && (
                <span className={cn(
                  'ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium',
                  activeTab === 'panels' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
                )}>
                  {testsCount} {testsCount === 1 ? 'test' : 'tests'}
                </span>
              )}
            </button>
          </div>

          {/* Progress indicator */}
          <div className="bg-gray-100 rounded-lg p-3">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-gray-600">Progress</span>
              <span className="font-medium">{completedFields}/{totalFields}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${(completedFields / totalFields) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )
    }
  ]

  if (collapsed) {
    return null // Navigation button is now handled in the header
  }

  return (
    <div className={cn(
      'bg-white border-r border-gray-200 shadow-lg z-30 flex flex-col h-full',
      'w-80 transition-all duration-300',
      className
    )}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h2 className="font-semibold text-gray-900">Navigation</h2>
        <div className="flex items-center gap-2">
          {/* Layout mode selector */}
          <div className="flex border border-gray-200 rounded overflow-hidden">
            <button
              onClick={() => onLayoutModeChange('focus')}
              className={cn(
                'p-1.5 transition-colors',
                layoutMode === 'focus' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
              )}
              title="Focus Mode (Cmd+Shift+F)"
            >
              <Focus size={14} />
            </button>
            <button
              onClick={() => onLayoutModeChange('reference')}
              className={cn(
                'p-1.5 transition-colors',
                layoutMode === 'reference' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
              )}
              title="Reference Mode (Cmd+Shift+R)"
            >
              <Eye size={14} />
            </button>
            <button
              onClick={() => onLayoutModeChange('navigation')}
              className={cn(
                'p-1.5 transition-colors',
                layoutMode === 'navigation' ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
              )}
              title="Navigation Mode"
            >
              <Navigation size={14} />
            </button>
          </div>

          <button
            onClick={() => onCollapseChange?.(true)}
            className="p-1.5 text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title="Collapse Navigation (Cmd+Shift+N)"
            aria-label="Collapse Navigation"
          >
            <ChevronLeft size={16} />
          </button>
        </div>
      </div>

      {/* Navigation tabs */}
      <div className="flex border-b border-gray-200">
        {navSections.map(section => (
          <button
            key={section.id}
            onClick={() => setActiveNavSection(section.id)}
            className={cn(
              'flex-1 flex items-center justify-center gap-2 p-3 text-sm transition-colors relative',
              activeNavSection === section.id
                ? 'text-blue-600 bg-blue-50 border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            )}
          >
            {section.icon}
            <span>{section.label}</span>
            {section.badge && section.badge > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {section.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-4">
        {navSections.find(section => section.id === activeNavSection)?.content}
      </div>

      {/* Footer with shortcuts */}
      <div className="border-t border-gray-200 p-3 bg-gray-50">
        <div className="text-xs text-gray-500 space-y-1">
          <div><kbd className="bg-gray-200 px-1 rounded">Cmd+Shift+N</kbd> Toggle nav</div>
          <div><kbd className="bg-gray-200 px-1 rounded">Cmd+Shift+F</kbd> Focus mode</div>
          <div><kbd className="bg-gray-200 px-1 rounded">N/P</kbd> Navigate issues</div>
        </div>
      </div>
    </div>
  )
}
