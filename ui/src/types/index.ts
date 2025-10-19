// Job and processing types
export interface Job {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  created_at: string
  started_at?: string
  completed_at?: string
  progress: Record<string, ProgressStep>
  result_url?: string
  error?: string
  source?: 'upload' | 'url'
  filename?: string
  pdf_url?: string
}

// Job Registry Entry (from the new API endpoint)
export interface JobRegistryEntry {
  id: string
  filename?: string
  created_at: string
  updated_at: string
  status: 'queued' | 'processing' | 'done' | 'failed'
  result_path?: string
  error?: string
}

// Job List Response from new API
export interface JobListResponse {
  jobs: JobRegistryEntry[]
  total: number
  page: number
  per_page: number
  has_next: boolean
}

export interface ProgressStep {
  message: string
  timestamp: string
  progress?: number
  [key: string]: any
}

export interface JobSubmissionResponse {
  job_id: string
  status: string
  created_at: string
  message: string
}

// Lab data types
export interface FieldConfidence {
  value_parse: number
  unit_validity: number
  reference_range: number
  test_name_clarity: number
  classifier_proba: number
  overall: number
}

// Reference range can be either a string or object with structured data
export type RefRange = string | {
  text?: string | null
  low?: number | null
  high?: number | null
  raw?: string | null
  value?: string | null
}

export interface TestCodes {
  loinc?: string | null
  cpt?: string | null
}

export interface TestRow {
  text: string
  page: number
  line_number: number
  y_norm: number
  test_name?: string
  result_value?: string
  units?: string
  
  // Legacy and structured reference range
  reference_range?: RefRange
  reference_range_text?: string | null
  reference_range_low?: number | null
  reference_range_high?: number | null
  
  // Flags (original and normalized)
  flag?: string
  flag_norm?: string
  flags?: string[]
  
  // Enhanced fields
  comments?: string | null
  methodology?: string | null
  observed_at?: string | null
  codes?: TestCodes | null
  
  confidence: number
  field_confidences: FieldConfidence
}

export interface Panel {
  id: string
  name: string
  started_at_page: number
  started_at_line: number
  continuity_score: number
  open: boolean
  panel_type?: string
  collected_date?: string
  reference_lab?: string
  test_count: number
  coherence_score: number
  panel_score: number
  needs_review: boolean
  review_reasons: string[]
  test_rows: TestRow[]
}

export interface DocumentInfo {
  source?: string
  processed_at: string
  total_panels: number
  total_tests: number
  document_score: number
  needs_review: boolean
  review_reasons: string[]
  confidence_distribution: {
    mean: number
    median: number
    min: number
    max: number
    std: number
  }
  patient_info?: Record<string, string>
  specimen_info?: Record<string, string>
  lab_info?: Record<string, string>
  processing_stats: {
    lines_processed: number
    page_breaks_handled: number
    repairs_made: number
    processing_time_seconds: number
  }
}

// Enhanced document header types
export interface Address {
  street?: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
}

export interface Patient {
  last_name?: string | null
  first_name?: string | null
  middle?: string | null
  dob?: string | null
  sex?: string | null
  mrn?: string | null
  phone?: string | null
  address?: Address | null
  age_at_collection?: number | null
}

export interface Vendor {
  name?: string | null
  account_number?: string | null
  address?: Address | null
  phone?: string | null
  fax?: string | null
}

export interface PerformingLab {
  name?: string | null
  clia?: string | null
  director?: string | null
  address?: Address | null
}

export interface OrderingLocation {
  name?: string | null
  address?: Address | null
}

export interface Ordering {
  provider_name?: string | null
  npi?: string | null
  location?: OrderingLocation | null
}

export interface Specimen {
  id?: string | null
  control_id?: string | null
  type?: string | null
  collected_at?: string | null
  received_at?: string | null
  entered_at?: string | null
  reported_at?: string | null
}

export interface Report {
  id?: string | null
  page_count?: number | null
  clinical_info?: string | null
  comments?: string | null
  ordered_items?: string[] | null
}

export interface EnhancedDocumentInfo {
  vendor?: Vendor | null
  performing_lab?: PerformingLab | null
  patient?: Patient | null
  ordering?: Ordering | null
  specimen?: Specimen | null
  report?: Report | null
}

export interface LabResult {
  document_info: DocumentInfo | EnhancedDocumentInfo
  lab_panels: Panel[]
  processing_summary?: {
    quality_metrics: any
    panel_summary: any
  }
}

// Manual review types
export interface EditableTestRow extends TestRow {
  isEditing?: boolean
  originalData?: Partial<TestRow>
}

export interface HeaderField {
  id: string
  text: string
  page: number
  line_number: number
  role: string
  label?: string
  value?: string
  confidence?: number
}

export interface EditableHeaderField extends HeaderField {
  isEditing?: boolean
  originalData?: Partial<HeaderField>
}

export interface EditablePanel extends Panel {
  test_rows: EditableTestRow[]
}

export interface ReviewSession {
  job_id: string
  result: LabResult
  corrections: Record<string, any>
  trainingData: TrainingAnnotation[]
  headerFields: EditableHeaderField[]
}

export interface TrainingAnnotation {
  line_number: number
  text: string
  original_role?: string
  corrected_role?: string
  original_tokens?: TokenAnnotation[]
  corrected_tokens?: TokenAnnotation[]
  timestamp: string
  reviewer: string
}

// Flexible training annotation type for API calls
export type FlexibleTrainingAnnotation = Record<string, unknown>;

export interface TokenAnnotation {
  text: string
  label: string
  start: number
  end: number
  confidence?: number
}

// Filter and search types
export interface ResultFilter {
  status?: string[]
  needs_review?: boolean
  confidence_range?: [number, number]
  date_range?: [string, string]
  search_query?: string
  panel_types?: string[]
}

// System stats
export type StatusCounts = { queued: number; processing: number; failed: number; completed: number };
export type Stats = { status_counts: Partial<StatusCounts> } & Record<string, any>;

export interface SystemStats {
  total_jobs: number
  status_counts: Record<string, number>
  queue_info: any
}

// Configuration types
export interface ProcessingConfig {
  extraction?: {
    dpi?: number
    extract_images?: boolean
  }
  composition?: {
    composer?: {
      page_break_lookahead?: number
      min_continuity_score?: number
      cost_weight_switches?: number
      cost_weight_coherence?: number
    }
    scoring?: {
      value_parse_threshold?: number
      unit_validity_threshold?: number
      ref_range_threshold?: number
      panel_score_threshold?: number
      document_score_threshold?: number
    }
  }
}

// Utility types
export type ConfidenceLevel = 'low' | 'medium' | 'high'

export interface PageThumbnail {
  page_number: number
  thumbnail_url: string
  width: number
  height: number
}

export interface ExtractedText {
  page: number
  lines: Array<{
    text: string
    bbox: [number, number, number, number]
    confidence?: number
    role?: string
  }>
}

// Correction types
export interface Correction {
  line_number?: number
  field: string
  new_value?: string
  old_value?: string
  reason?: string
}

// PDF Viewer types
export interface PdfFieldHighlight {
  page: number
  bbox: [number, number, number, number] // [x, y, width, height] normalized 0-1
  confidence: number
  fieldPath: string
  lineNumber?: number
  testName?: string
}

export interface PdfViewerState {
  numPages: number | null
  currentPage: number
  scale: number
  rotation: number
  loading: boolean
  error: string | null
  pdfUrl: string | null
}

// API response types
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
}