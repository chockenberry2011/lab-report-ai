import React, { useState, useCallback, useEffect } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
// Bundle worker from top-level pdfjs-dist (aligned to react-pdf)
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore - Vite ?url import for asset URL
import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { ZoomIn, ZoomOut, RotateCcw, ChevronLeft, ChevronRight, Download, Loader2, AlertTriangle, Eye, EyeOff } from 'lucide-react'
import { fileApi } from '@/services/api'
import { toast } from 'react-hot-toast'

// Configure pdf.js worker to the bundled asset to ensure version parity
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerSrc as unknown as string

interface PdfViewerProps {
  jobId: string
  className?: string
  highlightedFields?: Array<{
    page: number
    bbox: [number, number, number, number] // [x, y, width, height] normalized 0-1
    confidence: number
    fieldPath: string
  }>
  onFieldClick?: (fieldPath: string) => void
  navigateToPage?: number // External page navigation request
  onPageChange?: (page: number) => void // Callback when page changes
  showConfidenceHighlights?: boolean // Toggle for confidence highlighting
  onToggleConfidenceHighlights?: (show: boolean) => void // Callback for toggling highlights
}

interface PdfViewerState {
  numPages: number | null
  currentPage: number
  scale: number
  rotation: number
  loading: boolean
  error: string | null
  pdfUrl: string | null
  watchdogFired: boolean
}

const ZOOM_LEVELS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
const DEFAULT_SCALE = 1.0

export default function PdfViewer({
  jobId,
  className = '',
  highlightedFields = [],
  onFieldClick,
  navigateToPage,
  onPageChange,
  showConfidenceHighlights = true,
  onToggleConfidenceHighlights
}: PdfViewerProps) {
  const [docKey, setDocKey] = useState(0)
  const [state, setState] = useState<PdfViewerState>({
    numPages: null,
    currentPage: 1,
    scale: DEFAULT_SCALE,
    rotation: 0,
    loading: true,
    error: null,
    pdfUrl: null,
    watchdogFired: false,
  })
  const [useIframeFallback, setUseIframeFallback] = useState(false)
  const [attemptedRemount, setAttemptedRemount] = useState(false)
  const [usedCdnWorker, setUsedCdnWorker] = useState(false)

  // Initialize PDF URL
  useEffect(() => {
    const loadPdfUrl = async () => {
      try {
        const url = await fileApi.getOriginalPdf(jobId)
        setState(prev => ({ ...prev, pdfUrl: url, loading: false }))
      } catch (error) {
        console.error('Failed to load PDF URL:', error)
        setState(prev => ({
          ...prev,
          error: 'Failed to load PDF. Original document may not be available.',
          loading: false
        }))
      }
    }

    loadPdfUrl()
  }, [jobId])

  const onDocumentLoadSuccess = useCallback((pdf: any) => {
    setState(prev => ({
      ...prev,
      numPages: pdf.numPages,
      loading: false,
      error: null,
      watchdogFired: false,
    }))
  }, [])

  const onDocumentLoadError = useCallback((error: any) => {
    console.error('PDF load error:', error)
    const msg = String(error && (error.message || error.details || error))
    // If we hit a version mismatch, switch to CDN worker matching the API version
    if (!usedCdnWorker && /does not match the Worker version/i.test(msg)) {
      try {
        const cdn = `https://unpkg.com/pdfjs-dist@${(pdfjs as any).version}/build/pdf.worker.min.mjs`
        ;(pdfjs as any).GlobalWorkerOptions.workerSrc = cdn
        setUsedCdnWorker(true)
        setDocKey(k => k + 1)
        setState(prev => ({ ...prev, error: null, loading: true }))
        return
      } catch {/* noop */}
    }
    // If worker failed once, remount to retry. If it fails again, surface error.
    if (!attemptedRemount) {
      setAttemptedRemount(true)
      setDocKey(k => k + 1)
      setState(prev => ({ ...prev, error: null, loading: true }))
      return
    }
    setState(prev => ({ ...prev, error: 'Failed to load PDF document', loading: false }))
    toast.error('Failed to load PDF document')
  }, [])

  // Watchdog to surface worker failures where the internal loader spins indefinitely
  useEffect(() => {
    if (!state.pdfUrl || state.numPages || state.error) return
    const timeoutMs = 12000
    const timer = setTimeout(() => {
      setState(prev => ({
        ...prev,
        error: prev.error || 'Timed out loading the PDF. The PDF worker may be blocked by the browser or network.',
        watchdogFired: true,
      }))
    }, timeoutMs)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.pdfUrl, state.numPages, state.error])

  const handlePageChange = useCallback((pageNumber: number) => {
    if (pageNumber >= 1 && pageNumber <= (state.numPages || 1)) {
      setState(prev => ({ ...prev, currentPage: pageNumber }))
      onPageChange?.(pageNumber)
    }
  }, [state.numPages, onPageChange])

  // Handle external page navigation requests
  useEffect(() => {
    if (navigateToPage && navigateToPage !== state.currentPage && navigateToPage >= 1 && navigateToPage <= (state.numPages || 1)) {
      setState(prev => ({ ...prev, currentPage: navigateToPage }))
      onPageChange?.(navigateToPage)
    }
  }, [navigateToPage, state.currentPage, state.numPages, onPageChange])

  const handleZoom = useCallback((direction: 'in' | 'out' | 'reset') => {
    setState(prev => {
      let newScale = prev.scale

      if (direction === 'reset') {
        newScale = DEFAULT_SCALE
      } else {
        const currentIndex = ZOOM_LEVELS.findIndex(level => level >= prev.scale)

        if (direction === 'in') {
          const nextIndex = Math.min(currentIndex + 1, ZOOM_LEVELS.length - 1)
          newScale = ZOOM_LEVELS[nextIndex]
        } else {
          const prevIndex = Math.max(currentIndex - 1, 0)
          newScale = ZOOM_LEVELS[prevIndex]
        }
      }

      return { ...prev, scale: newScale }
    })
  }, [])

  const handleRotate = useCallback(() => {
    setState(prev => ({ ...prev, rotation: (prev.rotation + 90) % 360 }))
  }, [])

  const handleDownload = useCallback(() => {
    if (state.pdfUrl) {
      const link = document.createElement('a')
      link.href = state.pdfUrl
      link.download = `lab_report_${jobId}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }, [state.pdfUrl, jobId])

  // Get confidence color for field highlighting
  const getConfidenceColor = (confidence: number): string => {
    if (confidence < 0.5) return 'rgba(239, 68, 68, 0.3)' // red-500 with opacity
    if (confidence < 0.7) return 'rgba(245, 158, 11, 0.3)' // amber-500 with opacity
    return 'rgba(34, 197, 94, 0.3)' // green-500 with opacity
  }

  // Get border color for field highlighting
  const getBorderColor = (confidence: number): string => {
    if (confidence < 0.5) return 'rgb(239, 68, 68)' // red-500
    if (confidence < 0.7) return 'rgb(245, 158, 11)' // amber-500
    return 'rgb(34, 197, 94)' // green-500
  }

  // Render field overlays for current page (defensive against bad prop types)
  const renderFieldHighlights = useCallback(() => {
    if (!showConfidenceHighlights) return null

    const safeHighlights = Array.isArray(highlightedFields) ? highlightedFields : []
    const pageFields = safeHighlights.filter(field => field.page === state.currentPage)

    return pageFields.map((field, index) => {
      const [x, y, width, height] = field.bbox

      return (
        <div
          key={`${field.fieldPath}-${index}`}
          className="absolute cursor-pointer transition-opacity hover:opacity-80"
          style={{
            left: `${x * 100}%`,
            top: `${y * 100}%`,
            width: `${width * 100}%`,
            height: `${height * 100}%`,
            backgroundColor: getConfidenceColor(field.confidence),
            border: `2px solid ${getBorderColor(field.confidence)}`,
            borderRadius: '2px',
            pointerEvents: onFieldClick ? 'auto' : 'none'
          }}
          onClick={() => onFieldClick?.(field.fieldPath)}
          title={`Field: ${field.fieldPath} | Confidence: ${(field.confidence * 100).toFixed(1)}%`}
        />
      )
    })
  }, [highlightedFields, state.currentPage, onFieldClick, showConfidenceHighlights])

  if (state.loading) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-gray-50 ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-2" />
        <p className="text-sm text-gray-600">Loading PDF document...</p>
      </div>
    )
  }

  if (state.error && !useIframeFallback) {
    return (
      <div className={`flex flex-col items-center justify-center h-full bg-gray-50 ${className}`}>
        <AlertTriangle className="h-8 w-8 text-amber-500 mb-2" />
        <p className="text-sm text-gray-600 text-center max-w-sm">{state.error}</p>
        <p className="text-xs text-gray-500 mt-2">
          The original PDF may not be available for viewing.
        </p>
      </div>
    )
  }

  return (
    <div className={`flex flex-col h-full bg-white ${className}`}>
      {/* PDF Controls Toolbar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-2">
          {/* Page Navigation */}
          <button
            onClick={() => handlePageChange(state.currentPage - 1)}
            disabled={state.currentPage <= 1}
            className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Previous page"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <span className="text-sm font-medium px-2">
            {state.currentPage} / {state.numPages || 0}
          </span>

          <button
            onClick={() => handlePageChange(state.currentPage + 1)}
            disabled={state.currentPage >= (state.numPages || 0)}
            className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Next page"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center space-x-2">
          {/* Zoom Controls */}
          <button
            onClick={() => handleZoom('out')}
            disabled={state.scale <= ZOOM_LEVELS[0]}
            className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Zoom out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>

          <span className="text-sm font-medium px-2 min-w-[4rem] text-center">
            {Math.round(state.scale * 100)}%
          </span>

          <button
            onClick={() => handleZoom('in')}
            disabled={state.scale >= ZOOM_LEVELS[ZOOM_LEVELS.length - 1]}
            className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Zoom in"
          >
            <ZoomIn className="h-4 w-4" />
          </button>

          {/* Rotate */}
          <button
            onClick={handleRotate}
            className="p-1 rounded hover:bg-gray-200"
            title="Rotate 90°"
          >
            <RotateCcw className="h-4 w-4" />
          </button>

          {/* Download */}
          <button
            onClick={handleDownload}
            className="p-1 rounded hover:bg-gray-200"
            title="Download PDF"
          >
            <Download className="h-4 w-4" />
          </button>

          {/* Confidence Highlights Toggle */}
          {highlightedFields.length > 0 && onToggleConfidenceHighlights && (
            <button
              onClick={() => onToggleConfidenceHighlights(!showConfidenceHighlights)}
              className={`p-1 rounded transition-colors ${
                showConfidenceHighlights
                  ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                  : 'text-gray-600 hover:bg-gray-200'
              }`}
              title={showConfidenceHighlights ? "Hide confidence highlights" : "Show confidence highlights"}
            >
              {showConfidenceHighlights ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* PDF Document Viewer */}
      <div className="flex-1 overflow-auto bg-gray-100 p-4">
        <div className="flex justify-center">
          <div className="relative bg-white shadow-lg">
            {state.pdfUrl && !useIframeFallback && (
              <Document
                key={docKey}
                file={state.pdfUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                onLoadProgress={({ loaded, total }) => {
                  // keep outer loading false to use inner skeleton,
                  // but optionally log progress for debugging
                  if (total) {
                    // eslint-disable-next-line no-console
                    console.debug('PDF load progress', Math.round((loaded / total) * 100) + '%')
                  }
                }}
                loading={
                  <div className="flex items-center justify-center h-96 w-72">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                  </div>
                }
                error={
                  <div className="flex items-center justify-center h-96 w-72 bg-gray-50">
                    <div className="text-center">
                      <AlertTriangle className="h-6 w-6 text-red-500 mx-auto mb-2" />
                      <p className="text-sm text-gray-600">Failed to load PDF</p>
                    </div>
                  </div>
                }
              >
                <Page
                  pageNumber={state.currentPage}
                  scale={state.scale}
                  rotate={state.rotation}
                  renderAnnotationLayer={false}
                  renderTextLayer={false}
                />

                {/* Field highlight overlays */}
                <div className="absolute inset-0 pointer-events-none">
                  <div className="relative w-full h-full">
                    {renderFieldHighlights()}
                  </div>
                </div>
              </Document>
            )}
            {/* Optional: iframe fallback removed after dependency alignment */}
          </div>
        </div>
      </div>

      {/* Confidence Legend */}
      {showConfidenceHighlights && Array.isArray(highlightedFields) && highlightedFields.length > 0 && (
        <div className="p-3 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-center space-x-6 text-xs">
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 border border-red-500 bg-red-500 bg-opacity-30 rounded"></div>
              <span>Low confidence (&lt;50%)</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 border border-amber-500 bg-amber-500 bg-opacity-30 rounded"></div>
              <span>Medium confidence (50-70%)</span>
            </div>
            <div className="flex items-center space-x-1">
              <div className="w-3 h-3 border border-green-500 bg-green-500 bg-opacity-30 rounded"></div>
              <span>High confidence (&gt;70%)</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
