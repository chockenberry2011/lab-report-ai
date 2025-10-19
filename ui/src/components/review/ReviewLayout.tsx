import React, { useState, useCallback } from 'react'
import { FileText, PanelLeft } from 'lucide-react'
import { PanelLayout } from '@/components/layout/PanelLayout'
import { Panel } from '@/components/layout/Panel'
import PdfViewer from './PdfViewer'
import { usePdfFieldHighlights } from '@/hooks/usePdfFieldHighlights'
import { PdfJumpProvider } from './PdfJumpContext'
import type { LabResult } from '@/types'

interface ReviewLayoutProps {
  jobId: string
  resultData?: LabResult | null
  formContent: React.ReactNode
  onFieldFocus?: (fieldPath: string | null) => void
  defaultPdfWidth?: number
  showPdf?: boolean
  className?: string
}

/**
 * ReviewLayout: Clean layout for PDF + Form review interface
 *
 * Features:
 * - PDF viewer in left panel
 * - Form content in right panel
 * - Resizable panels with persistence
 * - Mobile stacking support
 * - Keyboard shortcuts
 * - PDF jump functionality
 */
export function ReviewLayout({
  jobId,
  resultData,
  formContent,
  onFieldFocus,
  defaultPdfWidth = 60,
  showPdf = true,
  className = ''
}: ReviewLayoutProps) {
  const [pdfWidth, setPdfWidth] = useState(() => {
    const saved = localStorage.getItem('lab-ai-pdf-width')
    return saved ? parseInt(saved, 10) : defaultPdfWidth
  })
  const [pdfCollapsed, setPdfCollapsed] = useState(!showPdf)
  const [currentPage, setCurrentPage] = useState(1)
  const [activeFieldPath, setActiveFieldPath] = useState<string | null>(null)
  const [showConfidenceHighlights, setShowConfidenceHighlights] = useState(() => {
    const saved = localStorage.getItem('lab-ai-show-confidence-highlights')
    return saved !== null ? saved === 'true' : true
  })

  // PDF highlights and field mapping (use new hook signature)
  const { highlights } = usePdfFieldHighlights({ resultData })

  // Handle panel resize
  const handlePdfResize = useCallback((width: number) => {
    setPdfWidth(width)
    localStorage.setItem('lab-ai-pdf-width', width.toString())
  }, [])

  // Handle PDF collapse
  const handlePdfCollapse = useCallback((collapsed: boolean) => {
    setPdfCollapsed(collapsed)
    localStorage.setItem('lab-ai-pdf-collapsed', collapsed.toString())
  }, [])

  // Handle field focus
  const handleFieldFocus = useCallback((fieldPath: string | null) => {
    setActiveFieldPath(fieldPath)
    onFieldFocus?.(fieldPath)
  }, [onFieldFocus])

  // Handle confidence highlights toggle
  const handleToggleConfidenceHighlights = useCallback((show: boolean) => {
    setShowConfidenceHighlights(show)
    localStorage.setItem('lab-ai-show-confidence-highlights', show.toString())
  }, [])

  // Handle jump to PDF location
  const handleJumpToPdf = useCallback((fieldPath: string) => {
    const highlight = highlights.find(h => h.fieldPath === fieldPath)
    if (highlight) {
      setCurrentPage(highlight.page)
      setActiveFieldPath(fieldPath)

      // Show PDF if collapsed
      if (pdfCollapsed) {
        setPdfCollapsed(false)
      }
    }
  }, [highlights, pdfCollapsed])

  // PDF panel content
  const pdfPanel = (
    <Panel
      title="Original PDF"
      subtitle={`Page ${currentPage}`}
      icon={<FileText className="h-4 w-4" />}
      badge={
        highlights.length > 0 ? (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">
            {highlights.length} fields
          </span>
        ) : undefined
      }
      collapsible
      collapsed={false}
      className="h-full"
      contentClassName="p-0"
    >
      <PdfViewer
        jobId={jobId}
        highlightedFields={highlights}
        onFieldClick={handleFieldFocus}
        navigateToPage={currentPage}
        onPageChange={setCurrentPage}
        showConfidenceHighlights={showConfidenceHighlights}
        onToggleConfidenceHighlights={handleToggleConfidenceHighlights}
        className="h-full"
      />
    </Panel>
  )

  // Form panel content
  const formPanel = (
    <Panel
      title="Review Form"
      icon={<PanelLeft className="h-4 w-4" />}
      badge={
        activeFieldPath ? (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">
            Active: {activeFieldPath.split('.').pop()}
          </span>
        ) : undefined
      }
      className="h-full"
      contentClassName="overflow-y-auto"
    >
      <PdfJumpProvider onJumpToPdf={handleJumpToPdf} currentPage={currentPage}>
        <div className="p-6">
          {formContent}
        </div>
      </PdfJumpProvider>
    </Panel>
  )

  return (
    <div className={className}>
      <PanelLayout
        leftPanel={pdfPanel}
        rightPanel={formPanel}
        defaultLeftWidth={pdfWidth}
        leftCollapsed={pdfCollapsed}
        allowResize={true}
        stackOnMobile={true}
        minLeftWidth={30}
        maxLeftWidth={70}
        onResize={handlePdfResize}
        onLeftCollapse={handlePdfCollapse}
        className="h-full"
      />
    </div>
  )
}
