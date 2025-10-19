import React, { useState } from 'react'
import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { EmptyState } from '@/components/EmptyState'
import { formatConfidence, getConfidenceTextClass, cn } from '@/utils'

interface PreviewPaneProps {
  extractedText?: any
  selectedPage: number
  onPageChange: (page: number) => void
  showLowConfidence: boolean
  onRetry?: () => void
  jobId?: string
  loading?: boolean
}

export function PreviewPane({
  extractedText,
  selectedPage,
  onPageChange,
  showLowConfidence,
  onRetry,
  jobId,
  loading = false
}: PreviewPaneProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="spinner w-8 h-8" />
      </div>
    )
  }

  // Handle empty or null extracted text
  if (!extractedText || !extractedText.pages?.length) {
    return (
      <div className="flex items-center justify-center h-full">
        <EmptyState
          title="No extracted text yet"
          description="Text extraction may still be processing or unavailable for this document."
          actionText="Refresh"
          onAction={onRetry}
        />
      </div>
    )
  }

  // Get total pages
  const totalPages = extractedText?.pages?.length || 1
  const currentPageData = extractedText?.pages?.[selectedPage - 1]

  return (
    <div className="h-full flex flex-col">
      {/* Page navigation */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <button
            onClick={() => onPageChange(Math.max(1, selectedPage - 1))}
            disabled={selectedPage === 1}
            className="btn-ghost p-2 disabled:opacity-50"
            title="Previous page"
            aria-label="Previous page"
          >
            <ChevronLeft size={16} />
          </button>

          <span className="text-sm font-medium">
            Page {selectedPage} of {totalPages}
          </span>

          <button
            onClick={() => onPageChange(Math.min(totalPages, selectedPage + 1))}
            disabled={selectedPage === totalPages}
            className="btn-ghost p-2 disabled:opacity-50"
            title="Next page"
            aria-label="Next page"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* Extracted text */}
      <div className="flex-1 p-4 overflow-y-auto scrollbar-thin">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Extracted Text {currentPageData && `(Page ${selectedPage})`}
        </h3>

        {currentPageData?.lines?.length ? (
          <div className="space-y-1 font-mono text-sm">
            {(currentPageData.lines || []).map((line: any, index: number) => {
              const confidence = line.confidence || 1
              const shouldHighlight = showLowConfidence && confidence < 0.7

              return (
                <div
                  key={index}
                  className={cn(
                    'p-1 rounded',
                    shouldHighlight && getConfidenceTextClass(confidence),
                    line.role && `border-l-2 border-${line.role === 'TEST_ROW' ? 'primary' : line.role === 'SECTION_PANEL' ? 'green' : 'gray'}-300 pl-2`
                  )}
                >
                  <div className="flex items-start space-x-2">
                    {line.role && (
                      <span className="text-xs text-gray-500 min-w-16">
                        {line.role.replace('_', ' ')}
                      </span>
                    )}
                    <span className="flex-1">{line.text}</span>
                    {showLowConfidence && confidence < 1 && (
                      <span className="text-xs text-gray-400">
                        {formatConfidence(confidence)}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-gray-500 text-center py-8">
            <FileText size={48} className="mx-auto mb-4 text-gray-300" />
            <p>No extracted text available</p>
            <p className="text-sm">Text will appear here once processing is complete</p>
          </div>
        )}
      </div>
    </div>
  )
}