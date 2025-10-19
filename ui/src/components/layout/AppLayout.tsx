import React from 'react'
import { cn } from '@/utils'

interface AppLayoutProps {
  navigation?: React.ReactNode
  header?: React.ReactNode
  children: React.ReactNode
  showNavigation?: boolean
  className?: string
}

/**
 * AppLayout: Root layout container for the entire application
 *
 * Architecture:
 * - CSS Grid with explicit areas for navigation, header, and content
 * - Navigation can be toggled on/off
 * - Header spans across the top (excluding navigation when visible)
 * - Content area fills remaining space
 * - Responsive behavior handled at this level
 */
export function AppLayout({
  navigation,
  header,
  children,
  showNavigation = false,
  className = ''
}: AppLayoutProps) {
  return (
    <div
      className={cn(
        'h-screen overflow-hidden bg-gray-50',
        'grid transition-all duration-300 ease-in-out',
        showNavigation
          ? 'grid-cols-[320px_1fr] grid-rows-[auto_1fr]'
          : 'grid-cols-1 grid-rows-[auto_1fr]',
        className
      )}
      style={{
        gridTemplateAreas: showNavigation
          ? '"nav header" "nav content"'
          : '"header" "content"'
      }}
    >
      {/* Navigation Sidebar */}
      {showNavigation && navigation && (
        <aside
          className="bg-white border-r border-gray-200 overflow-hidden"
          style={{ gridArea: 'nav' }}
        >
          {navigation}
        </aside>
      )}

      {/* Header */}
      {header && (
        <header
          className="bg-white border-b border-gray-200 flex-shrink-0 z-10"
          style={{ gridArea: 'header' }}
        >
          {header}
        </header>
      )}

      {/* Main Content */}
      <main
        className="overflow-hidden"
        style={{ gridArea: 'content' }}
      >
        {children}
      </main>
    </div>
  )
}