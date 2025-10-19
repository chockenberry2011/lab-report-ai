import { useMemo } from 'react'
import type { LabResult, TestRow, Panel } from '@/types'

interface FieldHighlight {
  page: number
  bbox: [number, number, number, number] // [x, y, width, height] normalized 0-1
  confidence: number
  fieldPath: string
  lineNumber?: number
  testName?: string
}

interface UsePdfFieldHighlightsProps {
  resultData?: LabResult | null
  activeFieldPath?: string
  confidenceThreshold?: number
}

/**
 * Hook to generate field highlights for PDF viewer based on lab result data
 * Maps form fields to their corresponding locations in the PDF
 */
export function usePdfFieldHighlights({
  resultData,
  activeFieldPath,
  confidenceThreshold = 0.0
}: UsePdfFieldHighlightsProps) {
  const highlights = useMemo<FieldHighlight[]>(() => {
    if (!resultData?.lab_panels) return []

    const fieldHighlights: FieldHighlight[] = []

    resultData.lab_panels.forEach((panel: Panel, panelIndex: number) => {
      // Panel-level highlights
      if (panel.started_at_page && panel.started_at_line) {
        fieldHighlights.push({
          page: panel.started_at_page,
          bbox: [0.05, (panel.started_at_line - 1) * 0.02, 0.9, 0.02], // Rough line estimation
          confidence: panel.panel_score || 0,
          fieldPath: `panels.${panelIndex}.name`,
          lineNumber: panel.started_at_line,
          testName: panel.name
        })
      }

      // Test row highlights
      panel.test_rows?.forEach((testRow: TestRow, testIndex: number) => {
        const basePath = `panels.${panelIndex}.test_rows.${testIndex}`

        // Only show highlights above confidence threshold
        if (testRow.confidence < confidenceThreshold) return

        // Calculate normalized position based on page and line
        const pageNorm = testRow.page || 1
        const lineNorm = testRow.line_number || 1
        const yPosition = ((lineNorm - 1) * 0.025) % 1 // Rough line-to-position mapping

        // Test name field
        if (testRow.test_name) {
          fieldHighlights.push({
            page: pageNorm,
            bbox: [0.05, yPosition, 0.25, 0.02],
            confidence: testRow.field_confidences?.test_name_clarity || testRow.confidence,
            fieldPath: `${basePath}.test_name`,
            lineNumber: testRow.line_number,
            testName: testRow.test_name
          })
        }

        // Result value field
        if (testRow.result_value) {
          fieldHighlights.push({
            page: pageNorm,
            bbox: [0.35, yPosition, 0.15, 0.02],
            confidence: testRow.field_confidences?.value_parse || testRow.confidence,
            fieldPath: `${basePath}.result_value`,
            lineNumber: testRow.line_number,
            testName: testRow.test_name
          })
        }

        // Units field
        if (testRow.units) {
          fieldHighlights.push({
            page: pageNorm,
            bbox: [0.55, yPosition, 0.1, 0.02],
            confidence: testRow.field_confidences?.unit_validity || testRow.confidence,
            fieldPath: `${basePath}.units`,
            lineNumber: testRow.line_number,
            testName: testRow.test_name
          })
        }

        // Reference range field
        if (testRow.reference_range) {
          fieldHighlights.push({
            page: pageNorm,
            bbox: [0.7, yPosition, 0.25, 0.02],
            confidence: testRow.field_confidences?.reference_range || testRow.confidence,
            fieldPath: `${basePath}.reference_range`,
            lineNumber: testRow.line_number,
            testName: testRow.test_name
          })
        }
      })
    })

    return fieldHighlights
  }, [resultData, confidenceThreshold])

  // Filter highlights based on active field (for focus mode)
  const focusedHighlights = useMemo(() => {
    if (!activeFieldPath) return highlights

    return highlights.filter(highlight =>
      highlight.fieldPath === activeFieldPath ||
      highlight.fieldPath.startsWith(activeFieldPath + '.') ||
      activeFieldPath.startsWith(highlight.fieldPath + '.')
    )
  }, [highlights, activeFieldPath])

  // Get highlights below certain confidence threshold for review priority
  const lowConfidenceHighlights = useMemo(() => {
    return highlights.filter(highlight => highlight.confidence < 0.7)
  }, [highlights])

  // Get page numbers that have highlights
  const pagesWithHighlights = useMemo(() => {
    const pages = new Set(highlights.map(h => h.page))
    return Array.from(pages).sort((a, b) => a - b)
  }, [highlights])

  return {
    highlights: activeFieldPath ? focusedHighlights : highlights,
    allHighlights: highlights,
    lowConfidenceHighlights,
    pagesWithHighlights,
    totalHighlights: highlights.length,
    lowConfidenceCount: lowConfidenceHighlights.length
  }
}