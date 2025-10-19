// Lightweight types for review form fields - only what we actually render

export interface FieldDefinition {
  key: string
  label: string
  type: 'text' | 'date' | 'phone' | 'number' | 'select'
  section: 'envelope' | 'patient' | 'provider' | 'specimen' | 'report' | 'panel' | 'test'
  path: string // JSON path like "vendor.name" or "patient.first_name"
  helperText?: string
}

export interface FieldValue {
  current: string | number | null
  original?: string | number | null // extracted value
  state: 'extracted' | 'corrected' | 'empty'
  confidence?: number // 0-1 for extracted values
  sourceLine?: string // original extracted text line
  sourcePage?: number
}

export interface ReviewFieldState {
  [fieldKey: string]: FieldValue
}

// Save status for user feedback
export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

// Existing correction format - DO NOT CHANGE
export interface LegacyCorrection {
  line_number?: number
  field: string
  new_value?: string
  old_value?: string
  reason?: string
}

// Component props
export interface LabeledFieldProps {
  label: string
  value: string | number | null
  state: 'extracted' | 'corrected' | 'empty'
  confidence?: number
  helperText?: string
  onEdit: () => void
  onReset?: () => void
  onPeekOriginal?: () => void
}

export interface InlineEditorProps {
  initialValue: any
  type: 'text' | 'date' | 'phone' | 'number' | 'select'
  options?: string[] // for select type
  onSave: (value: any) => void
  onCancel: () => void
}

export interface FieldRowProps {
  definition: FieldDefinition
  fieldState: FieldValue
  onUpdate: (value: any) => void
  onReset: () => void
}

// New corrections item format
export interface CorrectionItem {
  op: 'set' | 'unset' | 'append'
  path: string // JSON pointer format like "/patient/first_name"
  value?: any
}

// New corrections payload format
export interface CorrectionsPayload {
  items: CorrectionItem[]
  schema_version: number
}

// Enhanced field definition for dynamic panel/test fields
export interface DynamicFieldDefinition extends FieldDefinition {
  panelIndex?: number
  testIndex?: number
}

// Cell editing state for tables
export interface CellEditState {
  isEditing: boolean
  panelIndex?: number
  rowIndex?: number
  field?: string
}