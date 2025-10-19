// Shared result and lab data types used by both Viewer and Review pages
// This module contains pure TypeScript interfaces and types without React dependencies

export interface SharedLabResult {
  document_info: any
  lab_panels: SharedPanel[]
  processing_summary?: {
    quality_metrics: any
    panel_summary: any
  }
}

export interface SharedPanel {
  id: string
  name: string
  test_rows: SharedTestRow[]
  panel_score?: number
  needs_review?: boolean
  review_reasons?: string[]
}

export interface SharedTestRow {
  text: string
  test_name?: string
  result_value?: string
  units?: string
  reference_range?: any
  flag?: string
  confidence: number
  field_confidences?: any
}

export interface SharedExtractedText {
  pages?: Array<{
    lines: Array<{
      text: string
      confidence?: number
      role?: string
    }>
  }>
}

export interface ParsedResultRoute {
  raw: string
  baseId: string
  stage?: string
  flags: Set<string>
}