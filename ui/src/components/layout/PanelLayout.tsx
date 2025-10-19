import React, { useState, useCallback, useRef, useEffect } from 'react'
import { cn } from '@/utils'

interface PanelLayoutProps {
  leftPanel?: React.ReactNode
  rightPanel?: React.ReactNode
  defaultLeftWidth?: number // Percentage (0-100)
  minLeftWidth?: number
  maxLeftWidth?: number
  leftCollapsed?: boolean
  rightCollapsed?: boolean
  allowResize?: boolean
  stackOnMobile?: boolean
  className?: string
  onResize?: (leftWidth: number) => void
  onLeftCollapse?: (collapsed: boolean) => void
  onRightCollapse?: (collapsed: boolean) => void
}

/**
 * PanelLayout: Flexible two-panel layout with resizing capabilities
 *
 * Features:
 * - Resizable panels with drag handle
 * - Collapsible panels
 * - Mobile stacking support
 * - Keyboard shortcuts
 * - Persistent sizing
 * - Touch-friendly resizing
 */
export function PanelLayout({
  leftPanel,
  rightPanel,
  defaultLeftWidth = 50,
  minLeftWidth = 20,
  maxLeftWidth = 80,
  leftCollapsed = false,
  rightCollapsed = false,
  allowResize = true,
  stackOnMobile = true,
  className = '',
  onResize,
  onLeftCollapse,
  onRightCollapse
}: PanelLayoutProps) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth)
  const [isResizing, setIsResizing] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const resizerRef = useRef<HTMLDivElement>(null)

  // Responsive breakpoint detection
  useEffect(() => {
    const updateBreakpoint = () => {
      setIsMobile(window.innerWidth < 768)
    }

    updateBreakpoint()
    window.addEventListener('resize', updateBreakpoint)
    return () => window.removeEventListener('resize', updateBreakpoint)
  }, [])

  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!allowResize || leftCollapsed || rightCollapsed) return

    e.preventDefault()
    setIsResizing(true)

    const startX = e.clientX
    const startWidth = leftWidth
    const containerRect = containerRef.current?.getBoundingClientRect()

    if (!containerRect) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - startX
      const deltaPercent = (deltaX / containerRect.width) * 100
      const newWidth = Math.max(
        minLeftWidth,
        Math.min(maxLeftWidth, startWidth + deltaPercent)
      )

      setLeftWidth(newWidth)
      onResize?.(newWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [allowResize, leftCollapsed, rightCollapsed, leftWidth, minLeftWidth, maxLeftWidth, onResize])

  // Touch handling for mobile
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (!allowResize || leftCollapsed || rightCollapsed || !isMobile) return

    const touch = e.touches[0]
    const startX = touch.clientX
    const startWidth = leftWidth
    const containerRect = containerRef.current?.getBoundingClientRect()

    if (!containerRect) return

    const handleTouchMove = (e: TouchEvent) => {
      e.preventDefault()
      const touch = e.touches[0]
      const deltaX = touch.clientX - startX
      const deltaPercent = (deltaX / containerRect.width) * 100
      const newWidth = Math.max(
        minLeftWidth,
        Math.min(maxLeftWidth, startWidth + deltaPercent)
      )

      setLeftWidth(newWidth)
      onResize?.(newWidth)
    }

    const handleTouchEnd = () => {
      setIsResizing(false)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleTouchEnd)
    }

    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd)
  }, [allowResize, leftCollapsed, rightCollapsed, isMobile, leftWidth, minLeftWidth, maxLeftWidth, onResize])

  // Calculate actual widths
  const actualLeftWidth = leftCollapsed ? 0 : rightCollapsed ? 100 : leftWidth
  const actualRightWidth = rightCollapsed ? 0 : leftCollapsed ? 100 : (100 - leftWidth)

  // Determine layout mode
  const useStackingLayout = stackOnMobile && isMobile && !leftCollapsed && !rightCollapsed

  return (
    <div
      ref={containerRef}
      className={cn(
        'h-full w-full relative',
        useStackingLayout ? 'flex flex-col' : 'flex flex-row',
        className
      )}
    >
      {/* Left Panel */}
      {!leftCollapsed && leftPanel && (
        <div
          className={cn(
            'bg-white border-gray-200 overflow-hidden',
            useStackingLayout
              ? 'w-full h-1/2 border-b'
              : 'h-full border-r',
            'flex-shrink-0'
          )}
          style={{
            width: useStackingLayout ? '100%' : `${actualLeftWidth}%`
          }}
        >
          {leftPanel}
        </div>
      )}

      {/* Resizer */}
      {allowResize && !leftCollapsed && !rightCollapsed && !useStackingLayout && (
        <div
          ref={resizerRef}
          className={cn(
            'w-1 bg-gray-300 hover:bg-blue-400 cursor-col-resize transition-colors flex-shrink-0 z-10',
            isResizing && 'bg-blue-500'
          )}
          onMouseDown={handleMouseDown}
          onTouchStart={handleTouchStart}
          title="Drag to resize panels"
        />
      )}

      {/* Right Panel */}
      {!rightCollapsed && rightPanel && (
        <div
          className={cn(
            'bg-white overflow-hidden',
            useStackingLayout
              ? 'w-full h-1/2'
              : 'h-full',
            'flex-1'
          )}
        >
          {rightPanel}
        </div>
      )}
    </div>
  )
}