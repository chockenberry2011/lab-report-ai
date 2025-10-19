// Shared React hooks for result data management
// Can import React hooks but must not import any page modules

import { useMemo } from 'react'
import type { SharedLabResult, SharedPanel, ParsedResultRoute } from './types'
import { parseResultRoute, buildViewerId, selectFirstPanel } from './selectors'

export function useParsedResultRoute(rawParam?: string): ParsedResultRoute {
  return useMemo(() => parseResultRoute(rawParam || ''), [rawParam])
}

export function useViewerId(parsed: ParsedResultRoute): string {
  return useMemo(() => buildViewerId(parsed), [parsed])
}

export function useFirstPanel(result?: SharedLabResult): SharedPanel | undefined {
  return useMemo(() => selectFirstPanel(result), [result])
}

export function useResultMetrics(result?: SharedLabResult) {
  return useMemo(() => {
    if (!result) return null

    const totalPanels = result.lab_panels.length
    const totalTests = result.lab_panels.reduce((sum, panel) => sum + panel.test_rows.length, 0)
    const lowConfidenceTests = result.lab_panels.reduce(
      (sum, panel) => sum + panel.test_rows.filter(test => test.confidence < 0.7).length,
      0
    )
    const panelsNeedingReview = result.lab_panels.filter(panel => panel.needs_review).length

    return {
      totalPanels,
      totalTests,
      lowConfidenceTests,
      panelsNeedingReview,
      documentScore: result.document_info?.document_score,
      needsReview: result.document_info?.needs_review || false
    }
  }, [result])
}

export function useExtractedTextPages(extractedText: any): number {
  return useMemo(() => {
    return extractedText?.pages?.length || 1
  }, [extractedText])
}