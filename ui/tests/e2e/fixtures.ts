import { Route, APIRequestContext } from '@playwright/test'

// Minimal LabResult payload to let the Review editor render
export const minimalLabResult = {
  document_info: {
    vendor: { name: null },
    performing_lab: {},
    patient: {},
    ordering: {},
    specimen: {},
    report: {},
  },
  lab_panels: [
    {
      id: 'panel-1',
      name: 'Basic Panel',
      started_at_page: 1,
      started_at_line: 1,
      continuity_score: 1,
      open: true,
      test_count: 1,
      coherence_score: 1,
      panel_score: 1,
      needs_review: false,
      review_reasons: [],
      test_rows: [
        {
          text: 'GLUCOSE 100 mg/dL',
          page: 1,
          line_number: 1,
          y_norm: 0,
          test_name: 'GLUCOSE',
          result_value: '100',
          units: 'mg/dL',
          reference_range: { text: '70-110' },
          flag: '',
          flag_norm: '',
          flags: [],
          comments: null,
          methodology: null,
          observed_at: null,
          codes: null,
          confidence: 0.95,
          field_confidences: {
            value_parse: 1,
            unit_validity: 1,
            reference_range: 1,
            test_name_clarity: 1,
            classifier_proba: 1,
            overall: 1,
          },
        },
      ],
    },
  ],
}

export const healthyResponse = { status: 'healthy', timestamp: new Date().toISOString(), redis: 'ok', celery: 'ok', data_dirs: {} }

export const correctionsMap = (entries: Record<string, any>) => {
  // Server shape expected by useCorrections: key -> { value }
  const out: Record<string, { value: any }> = {}
  for (const [k, v] of Object.entries(entries)) out[k] = { value: v }
  return out
}

export function isCorrectionsPostArray(payload: unknown): payload is Array<Record<string, unknown>> {
  return Array.isArray(payload)
}

