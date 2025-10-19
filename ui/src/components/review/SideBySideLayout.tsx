import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { PanelLeft, PanelRight, Maximize2, Minimize2 } from 'lucide-react'
import PdfViewer from './PdfViewer'
import { usePdfFieldHighlights } from '@/hooks/usePdfFieldHighlights'
import { PdfJumpProvider } from './PdfJumpContext'
import { cn } from '@/utils'
import type { LabResult } from '@/types'

interface SideBySideLayoutProps {
  jobId: string
  resultData?: LabResult | null
  leftContent: React.ReactNode
  className?: string
  defaultPdfWidth?: number // Percentage (0-100)
  onFieldFocus?: (fieldPath: string | null) => void
}

export default function SideBySideLayout({
  jobId,
  resultData,
  leftContent,
  className = '',
  defaultPdfWidth = 60,
  onFieldFocus
}: SideBySideLayoutProps) {
  // Load saved panel width from localStorage
  const [pdfWidth, setPdfWidth] = useState(() => {
    const saved = localStorage.getItem('lab-ai-pdf-panel-width')
    return saved ? parseInt(saved, 10) : defaultPdfWidth
  })
  const [isResizing, setIsResizing] = useState(false)
  const [activeFieldPath, setActiveFieldPath] = useState<string | null>(null)
  const [isPdfCollapsed, setIsPdfCollapsed] = useState(() => {
    const saved = localStorage.getItem('lab-ai-pdf-collapsed')
    return saved === 'true'
  })
  const [isFormCollapsed, setIsFormCollapsed] = useState(false)
  const [navigateToPage, setNavigateToPage] = useState<number | undefined>(undefined)
  const [currentPdfPage, setCurrentPdfPage] = useState<number>(1)
  const [isTabletMode, setIsTabletMode] = useState(false)
  const [isMobileMode, setIsMobileMode] = useState(false)
  const [touchStartX, setTouchStartX] = useState<number | null>(null)

  const containerRef = useRef<HTMLDivElement>(null)
  const resizerRef = useRef<HTMLDivElement>(null)

  // Get PDF field highlights
  const {
    highlights,
    lowConfidenceHighlights,
    pagesWithHighlights,
    lowConfidenceCount
  } = usePdfFieldHighlights({
    resultData,
    activeFieldPath,
    confidenceThreshold: 0.0
  })

  // Handle field click from PDF
  const handlePdfFieldClick = useCallback((fieldPath: string) => {
    setActiveFieldPath(fieldPath)
    onFieldFocus?.(fieldPath)

    // Scroll to field in form if possible
    const fieldElement = document.querySelector(`[data-field-path="${fieldPath}"]`)
    if (fieldElement) {
      fieldElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [onFieldFocus])

  // Handle field focus from form
  const handleFormFieldFocus = useCallback((fieldPath: string | null) => {
    setActiveFieldPath(fieldPath)
    onFieldFocus?.(fieldPath)
  }, [onFieldFocus])

  // Handle jump to PDF location
  const handleJumpToPdf = useCallback((fieldPath: string) => {
    // Find the highlight for this field
    const fieldHighlight = highlights.find(h => h.fieldPath === fieldPath)
    if (fieldHighlight) {
      setNavigateToPage(fieldHighlight.page)
      setActiveFieldPath(fieldPath)

      // Show PDF panel if collapsed
      if (isPdfCollapsed) {
        setIsPdfCollapsed(false)
      }

      // Brief flash effect to indicate navigation
      setTimeout(() => setNavigateToPage(undefined), 100)
    }
  }, [highlights, isPdfCollapsed])

  // Handle PDF page changes
  const handlePdfPageChange = useCallback((page: number) => {
    setCurrentPdfPage(page)
  }, [])

  // Listen for PDF jump requests from floating widget
  useEffect(() => {
    const handlePdfJumpRequest = (event: CustomEvent) => {
      const { fieldPath } = event.detail
      if (fieldPath) {
        handleJumpToPdf(fieldPath)
      }
    }

    window.addEventListener('pdf-jump-request', handlePdfJumpRequest as EventListener)
    return () => window.removeEventListener('pdf-jump-request', handlePdfJumpRequest as EventListener)
  }, [handleJumpToPdf])

  // Responsive breakpoint detection
  useEffect(() => {
    const updateBreakpoints = () => {
      const width = window.innerWidth
      const isMobile = width < 768
      const isTablet = width >= 768 && width < 1024

      setIsMobileMode(isMobile)
      setIsTabletMode(isTablet)

      // Auto-collapse panels on mobile
      if (isMobile && !isPdfCollapsed && !isFormCollapsed) {
        setIsPdfCollapsed(true)
      }
    }

    updateBreakpoints()
    window.addEventListener('resize', updateBreakpoints)
    return () => window.removeEventListener('resize', updateBreakpoints)
  }, [isPdfCollapsed, isFormCollapsed])

  // Touch gesture handling for panel navigation
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    setTouchStartX(e.touches[0].clientX)
  }, [])

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (touchStartX === null) return

    const touchEndX = e.changedTouches[0].clientX
    const deltaX = touchStartX - touchEndX
    const threshold = 100

    // Swipe gestures for mobile/tablet
    if (Math.abs(deltaX) > threshold) {
      if (deltaX > 0) {
        // Swipe left - show form, hide PDF
        if (!isPdfCollapsed) setIsPdfCollapsed(true)
        if (isFormCollapsed) setIsFormCollapsed(false)
      } else {
        // Swipe right - show PDF, hide form
        if (isPdfCollapsed) setIsPdfCollapsed(false)
        if (!isFormCollapsed) setIsFormCollapsed(true)
      }
    }

    setTouchStartX(null)
  }, [touchStartX, isPdfCollapsed, isFormCollapsed])

  // Save panel state to localStorage
  useEffect(() => {
    localStorage.setItem('lab-ai-pdf-panel-width', pdfWidth.toString())
  }, [pdfWidth])

  useEffect(() => {
    localStorage.setItem('lab-ai-pdf-collapsed', isPdfCollapsed.toString())
  }, [isPdfCollapsed])

  // Mouse drag resizing
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)

    const startX = e.clientX
    const startWidth = pdfWidth

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return

      const containerWidth = containerRef.current.offsetWidth
      const deltaX = e.clientX - startX
      const deltaPercent = (deltaX / containerWidth) * 100
      const newWidth = Math.max(20, Math.min(80, startWidth + deltaPercent))
      setPdfWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [pdfWidth])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        switch (e.key) {
          case '[':
            e.preventDefault()
            setIsPdfCollapsed(prev => !prev)
            break
          case ']':
            e.preventDefault()
            setIsFormCollapsed(prev => !prev)
            break
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Calculate actual widths based on collapse state and device type
  const actualPdfWidth = useMemo(() => {
    if (isPdfCollapsed) return 0
    if (isFormCollapsed) return 100
    if (isTabletMode) return 100 // Full width in tablet stacking mode
    return pdfWidth
  }, [isPdfCollapsed, isFormCollapsed, isTabletMode, pdfWidth])

  const actualFormWidth = useMemo(() => {
    if (isFormCollapsed) return 0
    if (isPdfCollapsed) return 100
    if (isTabletMode) return 100 // Full width in tablet stacking mode
    return 100 - pdfWidth
  }, [isFormCollapsed, isPdfCollapsed, isTabletMode, pdfWidth])

  // Determine layout mode
  const useStackingLayout = isTabletMode && !isPdfCollapsed && !isFormCollapsed

  return (
    <div
      ref={containerRef}
      className={cn(
        'h-full bg-gray-50 grid transition-all duration-300',
        useStackingLayout ? 'grid-rows-2' : 'grid-cols-1',
        className
      )}
      style={{
        minHeight: '600px',
        gridTemplateColumns: useStackingLayout
          ? '1fr'
          : isPdfCollapsed
            ? '1fr'
            : isFormCollapsed
              ? `${actualPdfWidth}%`
              : `${actualPdfWidth}% 1fr`
      }}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* PDF Viewer Panel - Grid Layout */}
      {!isPdfCollapsed && (
        <div
          className={cn(
            'flex flex-col bg-white',
            useStackingLayout
              ? 'border-b border-gray-200'
              : 'border-r border-gray-200',
            'overflow-hidden'
          )}
        >
          {/* PDF Panel Header - Touch-Friendly */}
          <div className={`flex items-center justify-between px-4 ${isMobileMode ? 'py-3' : 'py-2'} bg-gray-50 border-b border-gray-200`}>
            <div className="flex items-center space-x-2">
              <PanelLeft className={`${isMobileMode ? 'h-5 w-5' : 'h-4 w-4'} text-gray-500`} />
              <h3 className={`${isMobileMode ? 'text-base' : 'text-sm'} font-medium text-gray-700`}>
                Original PDF
                {useStackingLayout && <span className="text-xs text-gray-500 ml-2">(Top Panel)</span>}
              </h3>
              {pagesWithHighlights.length > 0 && !isMobileMode && (
                <span className="text-xs text-gray-500">
                  ({pagesWithHighlights.length} pages with data)
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              {lowConfidenceCount > 0 && (
                <span className={`text-xs bg-amber-100 text-amber-700 ${isMobileMode ? 'px-3 py-1.5' : 'px-2 py-1'} rounded`}>
                  {lowConfidenceCount} need review
                </span>
              )}
              {(isMobileMode || isTabletMode) && (
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                  {isTabletMode ? 'Swipe ← →' : 'Swipe to switch'}
                </span>
              )}
              <button
                onClick={() => setIsPdfCollapsed(true)}
                className={`${isMobileMode ? 'p-2' : 'p-1'} hover:bg-gray-200 rounded transition-colors`}
                title={useStackingLayout ? 'Hide PDF panel' : 'Hide PDF (Cmd+[)'}
              >
                <Minimize2 className={`${isMobileMode ? 'h-5 w-5' : 'h-4 w-4'}`} />
              </button>
            </div>
          </div>

          {/* PDF Viewer */}
          <div className="flex-1">
            <PdfViewer
              jobId={jobId}
              highlightedFields={highlights}
              onFieldClick={handlePdfFieldClick}
              navigateToPage={navigateToPage}
              onPageChange={handlePdfPageChange}
              className="h-full"
            />
          </div>
        </div>
      )}

      {/* Resizer - Grid-aware */}
      {!isPdfCollapsed && !isFormCollapsed && !useStackingLayout && (
        <div
          ref={resizerRef}
          className={cn(
            'absolute top-0 bottom-0 w-1 bg-gray-300 cursor-col-resize hover:bg-blue-400 transition-colors z-40',
            isResizing && 'bg-blue-500'
          )}
          style={{
            left: `${actualPdfWidth}%`,
            transform: 'translateX(-50%)'
          }}
          onMouseDown={handleMouseDown}
          title="Drag to resize panels"
        />
      )}

      {/* Form Panel - Grid Layout */}
      {!isFormCollapsed && (
        <div
          className={cn(
            'flex flex-col bg-white overflow-hidden',
            useStackingLayout && 'border-t border-gray-200'
          )}
        >
          {/* Form Panel Header - Touch-Friendly */}
          <div className={`flex items-center justify-between px-4 ${isMobileMode ? 'py-3' : 'py-2'} bg-gray-50 border-b border-gray-200`}>
            <div className="flex items-center space-x-2">
              <PanelRight className={`${isMobileMode ? 'h-5 w-5' : 'h-4 w-4'} text-gray-500`} />
              <h3 className={`${isMobileMode ? 'text-base' : 'text-sm'} font-medium text-gray-700`}>
                Review Form
                {useStackingLayout && <span className="text-xs text-gray-500 ml-2">(Bottom Panel)</span>}
              </h3>
              {activeFieldPath && !isMobileMode && (
                <span className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                  Focusing: {activeFieldPath.split('.').pop()}
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              {isPdfCollapsed && (
                <button
                  onClick={() => setIsPdfCollapsed(false)}
                  className={`text-xs text-blue-600 hover:text-blue-700 ${isMobileMode ? 'px-3 py-1.5' : 'px-2 py-1'} rounded hover:bg-blue-50 transition-colors`}
                  title={useStackingLayout ? 'Show PDF panel' : 'Show PDF (Cmd+[)'}
                >
                  Show PDF
                </button>
              )}
              <button
                onClick={() => setIsFormCollapsed(true)}
                className={`${isMobileMode ? 'p-2' : 'p-1'} hover:bg-gray-200 rounded transition-colors`}
                title={useStackingLayout ? 'Hide form panel' : 'Hide form (Cmd+])'}
              >
                <Minimize2 className={`${isMobileMode ? 'h-5 w-5' : 'h-4 w-4'}`} />
              </button>
            </div>
          </div>

          {/* Form Content - Independent Scrolling */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden">
            {/* Enhanced form content that supports field focus */}
            <PdfJumpProvider onJumpToPdf={handleJumpToPdf} currentPage={currentPdfPage}>
              <div
                onFocus={(e) => {
                  const target = e.target as HTMLElement
                  const fieldPath = target.getAttribute('data-field-path')
                  if (fieldPath) {
                    handleFormFieldFocus(fieldPath)
                  }
                }}
              >
                {leftContent}
              </div>
            </PdfJumpProvider>
          </div>
        </div>
      )}

      {/* Collapsed Panel Restore Buttons */}
      {isPdfCollapsed && (
        <div className="fixed left-4 top-1/2 transform -translate-y-1/2 z-50">
          <button
            onClick={() => setIsPdfCollapsed(false)}
            className="bg-blue-600 text-white p-2 rounded-r shadow-lg hover:bg-blue-700 transition-colors"
            title="Show PDF panel (Cmd+[)"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {isFormCollapsed && (
        <div className="fixed right-4 top-1/2 transform -translate-y-1/2 z-50">
          <button
            onClick={() => setIsFormCollapsed(false)}
            className="bg-blue-600 text-white p-2 rounded-l shadow-lg hover:bg-blue-700 transition-colors"
            title="Show form panel (Cmd+])"
          >
            <Maximize2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Enhanced Keyboard shortcut hints */}
      <div className="fixed bottom-4 right-4 text-xs text-gray-500 bg-white px-3 py-2 rounded-lg shadow-lg border z-50">
        <div className="font-medium text-gray-700 mb-1">Keyboard Shortcuts:</div>
        <div className="space-y-1">
          <div><kbd className="bg-gray-100 px-1 rounded">Cmd+[</kbd> Toggle PDF</div>
          <div><kbd className="bg-gray-100 px-1 rounded">Cmd+]</kbd> Toggle Form</div>
          <div><kbd className="bg-gray-100 px-1 rounded">N</kbd> Next Issue</div>
          <div><kbd className="bg-gray-100 px-1 rounded">P</kbd> Prev Issue</div>
        </div>
      </div>
    </div>
  )
}