// Pure selector functions for processing result data
// No React imports - just pure functions for data transformation

import type { SharedLabResult, SharedPanel, SharedTestRow, ParsedResultRoute } from './types'

export function selectFirstPanel(result?: SharedLabResult): SharedPanel | undefined {
  return result?.lab_panels?.[0]
}

export function selectPanelById(result: SharedLabResult | undefined, panelId: string): SharedPanel | undefined {
  return result?.lab_panels.find(panel => panel.id === panelId)
}

export function selectTestRowsByPanel(panel: SharedPanel): SharedTestRow[] {
  return panel.test_rows || []
}

export function selectLowConfidenceTests(panel: SharedPanel, threshold: number = 0.7): SharedTestRow[] {
  return panel.test_rows.filter(test => test.confidence < threshold)
}

export function selectPanelsNeedingReview(result: SharedLabResult): SharedPanel[] {
  return result.lab_panels.filter(panel => panel.needs_review)
}

export function selectDocumentScore(result: SharedLabResult): number | undefined {
  return result.document_info?.document_score
}

export function selectNeedsReview(result: SharedLabResult): boolean {
  return result.document_info?.needs_review || false
}

export function selectTotalTests(result: SharedLabResult): number {
  return result.lab_panels.reduce((total, panel) => total + panel.test_rows.length, 0)
}

export function selectTotalPanels(result: SharedLabResult): number {
  return result.lab_panels.length
}

// Route parsing utilities
export function parseResultRoute(rawParam: string): ParsedResultRoute {
  if (!rawParam || typeof rawParam !== 'string') {
    return { raw: rawParam, baseId: '', flags: new Set() }
  }

  const trimmed = rawParam.trim()
  const parts = trimmed.split('.')

  if (parts.length === 0) {
    return { raw: rawParam, baseId: '', flags: new Set() }
  }

  // First part is always the baseId
  const baseId = parts[0]
  let stage: string | undefined
  const flags = new Set<string>()

  // Process remaining parts
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i]

    // Check if it's a processing stage (numeric prefix)
    if (part.match(/^\d{2}_/)) {
      stage = part
    } else {
      // Everything else is a flag
      flags.add(part)
    }
  }

  return {
    raw: rawParam,
    baseId,
    stage,
    flags
  }
}

export function buildViewerId(parsed: ParsedResultRoute): string {
  if (!parsed.baseId) return ''

  const tokens = [parsed.baseId]
  if (parsed.stage) tokens.push(parsed.stage)

  const flags = Array.from(parsed.flags).sort()
  if (flags.length) tokens.push(...flags)

  return tokens.join('.')
}