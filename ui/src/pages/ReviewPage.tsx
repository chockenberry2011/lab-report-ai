import { useState, useEffect, useMemo } from 'react'
import '@/styles/review-form.css'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import {
  ArrowLeft,
  Save,
  RotateCcw,
  BookOpen,
  Check,
  X,
  AlertTriangle,
  Eye,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { resultsApi, reviewApi, systemApi } from '@/services/api'
import { normalizeResultId } from '@/lib/normalizeIds'
import { ensureViewerId } from '@/lib/resultId'
import { buildResultPath } from '@/lib/routeParsing'
import { SECTIONS, SECTION_ORDER, fieldsForSection } from '@/config/fieldSchema'
import { SectionCard, FieldRow, SectionNav, MobileSectionNav } from '@/components/editor'
import {
  formatConfidence,
  getConfidenceBadgeClass,
  analyzeFieldConfidence,
  cn,
} from '@/utils'
import {
  formatReferenceRange,
  getFlagClass,
  formatDate,
} from '@/utils/formatters'
import HeaderCards from '@/components/HeaderCards'
import { FieldSection } from '@/components/review/FieldSection'
import { SaveStatusIndicator } from '@/components/SaveStatusIndicator'
import { PanelsTable } from '@/components/review/PanelsTable'
import { TestsTable } from '@/components/review/TestsTable'
import { useCorrections } from '@/hooks/useCorrections'
import { getFieldsBySection } from '@/lib/field-definitions'
import type {
  EditableTestRow,
  EditablePanel,
  ReviewSession,
  TrainingAnnotation,
  EnhancedDocumentInfo,
  EditableHeaderField,
  Correction
} from '@/types'

// View model repair for backward compatibility
function applyViewModelRepair(testRow: EditableTestRow): EditableTestRow {
  const flagTokens = ['H', 'HIGH', 'L', 'LOW', 'ABN', 'CRIT']
  
  // Check if flag is empty and units contains a flag token
  if (!testRow.flag && testRow.units) {
    const unitsUpper = testRow.units.trim().toUpperCase()
    if (flagTokens.includes(unitsUpper)) {
      return {
        ...testRow,
        flag: testRow.units,
        units: '' // Clear units since it was actually a flag
      }
    }
  }
  
  return testRow
}

// View guard to keep test rows table clean
function isProbablyTestRowView(text: string): boolean {
  /*
   * Frontend view guard to determine if a line should be shown in the test rows table
   * or moved to the header fields section. Similar to backend logic but optimized for UI.
   */
  if (!text || !text.trim()) {
    return false
  }
  
  text = text.trim()
  
  // Header patterns to exclude from test rows table
  const headerPatterns = [
    /specimen\s+id\s*:/i,
    /accession\s*:?/i,
    /acct\s*#/i,
    /mrn\s*:?/i,
    /patient\s+id\s*:?/i,
    /phone\s*:?/i,
    /fax\s*:?/i,
    /rte\s*:?/i,
    /clia\s*:?/i,
    /npi\s*:?/i,
    /director\s*:?/i,
    /location\s*:?/i,
    /collected\s*:?/i,
    /received\s*:?/i,
    /entered\s*:?/i,
    /reported\s*:?/i,
  ]
  
  // Check for header patterns
  for (const pattern of headerPatterns) {
    if (pattern.test(text)) {
      return false
    }
  }
  
  // Check for phone numbers
  if (/(\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})/.test(text)) {
    return false
  }
  
  // Check for CLIA/NPI patterns
  if (/clia\s*#?\s*\d{2}[a-z]\d{7}/i.test(text) || /npi\s*:?\s*\d{10}/i.test(text)) {
    return false
  }
  
  // Check for multiple colons (key-value pairs)
  if ((text.match(/:/g) || []).length >= 2) {
    return false
  }
  
  // Must have a numeric value to be considered a test row
  if (!/\d/.test(text)) {
    return false
  }
  
  return true
}

function parseHeaderField(text: string): { label: string; value: string } {
  /* Parse a header field text into label and value components */
  if (text.includes(':')) {
    const colonIndex = text.indexOf(':')
    return {
      label: text.substring(0, colonIndex).trim(),
      value: text.substring(colonIndex + 1).trim()
    }
  }
  
  // For lines without colons, try to identify key-value patterns
  const tokens = text.split(/\s+/)
  if (tokens.length >= 2) {
    // First token as label, rest as value
    return {
      label: tokens[0],
      value: tokens.slice(1).join(' ')
    }
  }
  
  return {
    label: 'Field',
    value: text
  }
}

interface EditableFieldProps {
  value: string | undefined
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  isEditing: boolean
  onToggleEdit: () => void
}

interface FlagEditorProps {
  value: string | undefined
  onChange: (value: string) => void
  isEditing: boolean
  onToggleEdit: () => void
}

function EditableField({ 
  value, 
  onChange, 
  placeholder, 
  className = '', 
  isEditing, 
  onToggleEdit 
}: EditableFieldProps) {
  const [localValue, setLocalValue] = useState(value || '')

  useEffect(() => {
    setLocalValue(value || '')
  }, [value])

  const handleSave = () => {
    onChange(localValue)
    onToggleEdit()
  }

  const handleCancel = () => {
    setLocalValue(value || '')
    onToggleEdit()
  }

  if (isEditing) {
    return (
      <div className="flex items-center space-x-2">
        <input
          type="text"
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          placeholder={placeholder}
          className={cn('input text-sm', className)}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave()
            if (e.key === 'Escape') handleCancel()
          }}
        />
        <button onClick={handleSave} className="btn-success p-1" title="Save">
          <Check size={14} />
        </button>
        <button onClick={handleCancel} className="btn-ghost p-1" title="Cancel">
          <X size={14} />
        </button>
      </div>
    )
  }

  const isEmpty = value === null || value === undefined || value === ''
  return (
    <div
      onClick={onToggleEdit}
      className={cn(
        'editable-field cursor-pointer min-h-6 flex items-center',
        isEmpty && 'text-gray-400',
        className
      )}
      title={isEmpty ? 'Not provided on report' : 'Edit field'}
    >
      {isEmpty ? '—' : (value as any)}
    </div>
  )
}

function FlagEditor({ 
  value, 
  onChange, 
  isEditing, 
  onToggleEdit 
}: FlagEditorProps) {
  const [localValue, setLocalValue] = useState(value || '')
  const flagOptions = ['', 'H', 'HIGH', 'L', 'LOW', 'ABN', 'CRIT']

  useEffect(() => {
    setLocalValue(value || '')
  }, [value])

  const handleSave = () => {
    onChange(localValue)
    onToggleEdit()
  }

  const handleCancel = () => {
    setLocalValue(value || '')
    onToggleEdit()
  }

  if (isEditing) {
    return (
      <div className="flex items-center space-x-2">
        <div className="relative">
          <select
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            className="input text-sm pr-8 min-w-20"
            autoFocus
          >
            {flagOptions.map((option) => (
              <option key={option} value={option}>
                {option || 'None'}
              </option>
            ))}
          </select>
          {/* Allow manual typing as fallback */}
          <input
            type="text"
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            placeholder="Or type flag"
            className="input text-sm mt-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
              if (e.key === 'Escape') handleCancel()
            }}
          />
        </div>
        <button onClick={handleSave} className="btn-success p-1" title="Save">
          <Check size={14} />
        </button>
        <button onClick={handleCancel} className="btn-ghost p-1" title="Cancel">
          <X size={14} />
        </button>
      </div>
    )
  }

  return (
    <div
      onClick={onToggleEdit}
      className="editable-field cursor-pointer min-h-6 flex items-center"
      title="Edit flag"
    >
      {value ? (
        <span className={getFlagClass(value)} title={`Flag: ${value}`}>
          {value}
        </span>
      ) : (
        <span className="text-gray-400">No flag</span>
      )}
    </div>
  )
}

// Enhanced test row components

interface CodePillsProps {
  codes?: { loinc?: string | null; cpt?: string | null } | null
}

function CodePills({ codes }: CodePillsProps) {
  if (!codes || (!codes.loinc && !codes.cpt)) return null
  
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {codes.loinc && (
        <span className="code-pill" title="LOINC Code">
          LOINC: {codes.loinc}
        </span>
      )}
      {codes.cpt && (
        <span className="code-pill" title="CPT Code">
          CPT: {codes.cpt}
        </span>
      )}
    </div>
  )
}

interface NotesExpanderProps {
  testRow: EditableTestRow
}

function NotesExpander({ testRow }: NotesExpanderProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const hasNotes = testRow.comments || testRow.methodology || testRow.observed_at
  if (!hasNotes) return null
  
  return (
    <div className="mt-2 border-t border-gray-100 pt-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center text-sm text-gray-600 hover:text-gray-800"
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="ml-1">Notes & Details</span>
      </button>
      
      {isExpanded && (
        <div className="mt-2 space-y-2 text-sm bg-gray-50 p-3 rounded">
          {testRow.comments && (
            <div>
              <span className="font-medium text-gray-700">Comments:</span>
              <div className="text-gray-600 mt-1">{testRow.comments}</div>
            </div>
          )}
          {testRow.methodology && (
            <div>
              <span className="font-medium text-gray-700">Methodology:</span>
              <div className="text-gray-600 mt-1">{testRow.methodology}</div>
            </div>
          )}
          {testRow.observed_at && (
            <div>
              <span className="font-medium text-gray-700">Observed:</span>
              <div className="text-gray-600 mt-1">{formatDate(testRow.observed_at)}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Old TestRowEditor component removed - replaced by enhanced TestsTable component

interface HeaderFieldEditorProps {
  headerField: EditableHeaderField
  onUpdate: (updates: Partial<EditableHeaderField>) => void
  onRevert: () => void
}

function HeaderFieldEditor({ headerField, onUpdate, onRevert }: HeaderFieldEditorProps) {
  const [editingFields, setEditingFields] = useState<Set<string>>(new Set())
  const isModified = headerField.originalData !== undefined
  
  const toggleFieldEdit = (field: string) => {
    const newEditing = new Set(editingFields)
    if (newEditing.has(field)) {
      newEditing.delete(field)
    } else {
      newEditing.add(field)
    }
    setEditingFields(newEditing)
  }

  const updateField = (field: keyof EditableHeaderField, value: string) => {
    if (!headerField.originalData) {
      // Store original data on first edit
      onUpdate({
        originalData: {
          label: headerField.label,
          value: headerField.value,
        },
      })
    }
    onUpdate({ [field]: value || undefined })
  }

  return (
    <div className={cn(
      'flex items-center space-x-4 p-3 border rounded',
      isModified && 'border-warning-300 bg-warning-50'
    )}>
      <div className="flex-1 grid grid-cols-2 gap-4">
        <div>
          <label className="label text-xs">Label</label>
          <EditableField
            value={headerField.label}
            onChange={(value) => updateField('label', value)}
            placeholder="Field label"
            isEditing={editingFields.has('label')}
            onToggleEdit={() => toggleFieldEdit('label')}
            className="text-sm"
          />
        </div>
        <div>
          <label className="label text-xs">Value</label>
          <EditableField
            value={headerField.value}
            onChange={(value) => updateField('value', value)}
            placeholder="Field value"
            isEditing={editingFields.has('value')}
            onToggleEdit={() => toggleFieldEdit('value')}
            className="text-sm"
          />
        </div>
      </div>
      
      <div className="flex items-center space-x-2">
        <div className="text-xs text-gray-500">
          Line {headerField.line_number}
        </div>
        {isModified && (
          <button
            onClick={onRevert}
            className="btn-ghost p-1 text-warning-600"
            title="Revert changes"
          >
            <RotateCcw size={14} />
          </button>
        )}
      </div>
    </div>
  )
}

interface HeaderFieldsEditorProps {
  headerFields: EditableHeaderField[]
  onUpdateHeaderField: (index: number, updates: Partial<EditableHeaderField>) => void
  onRevertHeaderField: (index: number) => void
}

function HeaderFieldsEditor({ 
  headerFields, 
  onUpdateHeaderField, 
  onRevertHeaderField 
}: HeaderFieldsEditorProps) {
  const modifiedHeaderFields = headerFields.filter(field => field.originalData)

  if (headerFields.length === 0) {
    return null
  }

  return (
    <div className="space-y-4 mb-6">
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900">Header & Envelope</h3>
            <div className="text-sm text-gray-600 mt-1">
              {headerFields.length} field{headerFields.length !== 1 ? 's' : ''}
              {modifiedHeaderFields.length > 0 && (
                <span className="ml-2 text-warning-600">
                  ({modifiedHeaderFields.length} modified)
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          {headerFields.map((headerField, index) => (
            <HeaderFieldEditor
              key={headerField.id}
              headerField={headerField}
              onUpdate={(updates) => onUpdateHeaderField(index, updates)}
              onRevert={() => onRevertHeaderField(index)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// Old PanelEditor and TestRowEditor components removed
// Replaced by enhanced PanelsTable and TestsTable components

export default function ReviewPage() {
  const { jobId: paramId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [reviewSession, setReviewSession] = useState<ReviewSession | null>(null)
  const [showConfidence, setShowConfidence] = useState(true)
  const [autosaveEnabled, setAutosaveEnabled] = useState(true)
  const [selectedPanel, setSelectedPanel] = useState(0)
  const [backendUnavailable, setBackendUnavailable] = useState(false)
  // Track corrected fields from server corrections (line_number + field)
  const [correctedSet, setCorrectedSet] = useState<Set<string>>(new Set())
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({})

  // New schema-driven editor state
  const [showMetadata, setShowMetadata] = useState(true)
  const [compactMode, setCompactMode] = useState(false)

  // Normalize the IDs
  const viewerId = paramId ? ensureViewerId(paramId) : undefined
  const jobId = paramId ? normalizeResultId(paramId) : undefined // Use normalized ID for API calls

  // Initialize corrections hook
  const {
    fieldStates,
    isDirty: isFieldsDirty,
    isLoading: isFieldsLoading,
    isSaving: isFieldsSaving,
    saveStatus,
    error: fieldsError,
    updateField,
    resetField,
    saveAll: saveAllFields,
    resetAll
  } = useCorrections({
    jobId: jobId!,
    resultData: reviewSession?.result,
    extractedTextData: extractedText,
    autosave: autosaveEnabled
  })

  // New schema-driven corrections hook
  const {
    data: schemaData,
    corrections: schemaCorrections,
    drafts: schemaDrafts,
    setDraft: setSchemaDraft,
    saveField: saveSchemaField,
    resetField_generic: resetSchemaField,
    fieldStatus: schemaFieldStatus,
    saveSection: saveSchemaSection,
    resetSection: resetSchemaSection,
    getValue: getSchemaValue
  } = useCorrections({
    jobId: jobId!,
    resultData: reviewSession?.result,
    extractedTextData: extractedText,
    autosave: false // We'll handle saves explicitly via buttons
  })

  // Health check on mount
  const { } = useQuery({
    queryKey: ['health-check'],
    queryFn: async () => {
      try {
        const result = await systemApi.health()
        setBackendUnavailable(false)
        return result
      } catch (error) {
        setBackendUnavailable(true)
        throw error
      }
    },
    retry: false,
    refetchOnWindowFocus: false,
  })

  // Fetch lab result data
  const { data: labResult, isLoading, error } = useQuery({
    queryKey: ['lab-result', jobId],
    queryFn: () => resultsApi.getResult(jobId!),
    enabled: !!jobId,
  })

  // Fetch existing corrections (for optional "Corrected" badge only)
  const { data: existingCorrections } = useQuery({
    queryKey: ['corrections', jobId],
    queryFn: () => reviewApi.getCorrections(jobId!),
    enabled: !!jobId,
  })

  // Fetch extracted text data to get raw lines with roles (non-blocking)
  const { data: extractedText } = useQuery({
    queryKey: ['extracted-text', jobId],
    queryFn: () => resultsApi.getExtractedText(jobId!),
    enabled: !!jobId,
    retry: false,
    refetchOnWindowFocus: false,
    onError: (err) => {
      console.warn('Extracted-text fetch failed; keeping compose view intact:', err)
    },
  })

  // Initialize review session primarily from compose endpoint (source of truth)
  useEffect(() => {
    if (labResult && !reviewSession) {
      // Process test rows with view model repair and filtering
      const editablePanels: EditablePanel[] = labResult.lab_panels.map(panel => ({
        ...panel,
        test_rows: panel.test_rows
          .filter(testRow => isProbablyTestRowView(testRow.text)) // Filter clean test rows
          .map(testRow => applyViewModelRepair({
            ...testRow,
            isEditing: false,
          })),
      }))

      setReviewSession({
        job_id: jobId!,
        result: {
          ...labResult,
          lab_panels: editablePanels,
        },
        corrections: existingCorrections || {},
        trainingData: [],
        headerFields: [],
      })
    }
  }, [labResult, existingCorrections, reviewSession, jobId])

  // When extracted text arrives, derive header fields without touching composed result
  useEffect(() => {
    if (!reviewSession) return
    if (!extractedText || !extractedText.pages?.length) return

    const allLines = (extractedText.pages || []).flatMap(page =>
      (page.lines || []).map(line => ({
        ...line,
        page: page.page
      }))
    )

    const headerFields: EditableHeaderField[] = allLines
      .filter(line => (
        ['HEADER_FIELD', 'OTHER'].includes(line.role || '') ||
        (line.role === 'TEST_ROW' && !isProbablyTestRowView(line.text))
      ))
      .map((line, index) => {
        const parsed = parseHeaderField(line.text)
        return {
          id: `header_${line.page}_${index}`,
          text: line.text,
          page: line.page,
          line_number: index + 1,
          role: line.role || 'OTHER',
          label: parsed.label,
          value: parsed.value,
          confidence: line.confidence || 1.0,
          isEditing: false,
        }
      })

    setReviewSession(prev => prev ? { ...prev, headerFields } : prev)
  }, [extractedText, reviewSession])

  // Add beforeunload guard if any schema fields are dirty
  useEffect(() => {
    const hasAnyDirtyField = () => {
      return SECTION_ORDER.some(sectionKey => {
        const defs = fieldsForSection(sectionKey)
        return defs.some(def => schemaFieldStatus(def.path).dirty)
      })
    }

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasAnyDirtyField() || isDirty) {
        e.preventDefault()
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?'
        return 'You have unsaved changes. Are you sure you want to leave?'
      }
    }

    if (reviewSession) {
      window.addEventListener('beforeunload', handleBeforeUnload)
    }

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [reviewSession, isDirty, schemaFieldStatus])

  // Build corrected set when corrections data changes
  useEffect(() => {
    const next = new Set<string>()
    const raw = existingCorrections
    if (Array.isArray(raw)) {
      raw.forEach((c: any) => {
        if (c && typeof c === 'object' && c.line_number && c.field) {
          next.add(`${c.line_number}:${c.field}`)
        }
      })
    } else if (raw && typeof raw === 'object') {
      const list = Array.isArray(raw.corrections) ? raw.corrections : (Array.isArray(raw.items) ? raw.items : [])
      list.forEach((c: any) => {
        if (c && typeof c === 'object' && c.line_number && c.field) {
          next.add(`${c.line_number}:${c.field}`)
        }
      })
    }
    setCorrectedSet(next)
  }, [existingCorrections])

  // Save corrections mutation (using legacy API for panels/tests)
  const saveCorrectsMutation = useMutation({
    mutationFn: (corrections: Correction[]) => 
      reviewApi.saveCorrection(jobId!, corrections),
    onSuccess: async () => {
      toast.success('Corrections saved successfully')
      // Invalidate and refetch both corrections and the composed result
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['corrections', jobId] }),
        queryClient.invalidateQueries({ queryKey: ['lab-result', jobId] }),
      ])
      await Promise.all([
        queryClient.refetchQueries({ queryKey: ['corrections', jobId] }),
        queryClient.refetchQueries({ queryKey: ['lab-result', jobId] }),
      ])
    },
    onError: (error) => {
      // Error is already properly formatted from the API service
      toast.error(error.message)
    },
  })

  // Add to training mutation
  const addToTrainingMutation = useMutation({
    mutationFn: (annotations: TrainingAnnotation[]) =>
      reviewApi.addToTraining(jobId!, annotations),
    onSuccess: () => {
      toast.success('Added to training data successfully')
    },
    onError: (error) => {
      toast.error(`Failed to add to training: ${error.message}`)
    },
  })

  const updateTestRow = (panelIndex: number, testRowIndex: number, updates: Partial<EditableTestRow>) => {
    if (!reviewSession) return

    const newSession = { ...reviewSession }
    const panel = newSession.result.lab_panels[panelIndex]
    const testRow = panel.test_rows[testRowIndex]
    
    // Update the test row
    panel.test_rows[testRowIndex] = { ...testRow, ...updates }
    
    setReviewSession(newSession)
  }

  const revertTestRow = (panelIndex: number, testRowIndex: number) => {
    if (!reviewSession) return

    const newSession = { ...reviewSession }
    const panel = newSession.result.lab_panels[panelIndex]
    const testRow = panel.test_rows[testRowIndex]
    
    if (testRow.originalData) {
      // Restore original values
      panel.test_rows[testRowIndex] = {
        ...testRow,
        ...testRow.originalData,
        originalData: undefined,
      }
      
      setReviewSession(newSession)
    }
  }

  // When new labResult arrives (after save or refresh), update the view from server
  useEffect(() => {
    if (!labResult || !reviewSession) return
    const editablePanels: EditablePanel[] = labResult.lab_panels.map(panel => ({
      ...panel,
      test_rows: panel.test_rows
        .filter(testRow => isProbablyTestRowView(testRow.text))
        .map(testRow => applyViewModelRepair({ ...testRow, isEditing: false }))
    }))
    setReviewSession(prev => prev ? { ...prev, result: { ...labResult, lab_panels: editablePanels } } : prev)
  }, [labResult])

  const updateHeaderField = (headerFieldIndex: number, updates: Partial<EditableHeaderField>) => {
    if (!reviewSession) return
    const newSession = { ...reviewSession }
    const headerField = newSession.headerFields[headerFieldIndex]
    
    // Update the header field
    newSession.headerFields[headerFieldIndex] = { ...headerField, ...updates }
    
    setReviewSession(newSession)
  }

  const revertHeaderField = (headerFieldIndex: number) => {
    if (!reviewSession) return
    const newSession = { ...reviewSession }
    const headerField = newSession.headerFields[headerFieldIndex]
    
    if (headerField.originalData) {
      // Restore original values
      newSession.headerFields[headerFieldIndex] = {
        ...headerField,
        ...headerField.originalData,
        originalData: undefined,
      }
      
      setReviewSession(newSession)
    }
  }

  const saveAllCorrections = () => {
    if (!reviewSession) return

    // Collect all corrections in the new format
    const corrections: Correction[] = []
    
    reviewSession.result.lab_panels.forEach((panel, panelIndex) => {
      panel.test_rows.forEach((testRow, testRowIndex) => {
        if (testRow.originalData) {
          // Check each field for changes and add individual corrections
          if (testRow.test_name !== testRow.originalData.test_name) {
            corrections.push({
              line_number: testRow.line_number,
              field: 'test_name',
              new_value: testRow.test_name,
              old_value: testRow.originalData.test_name,
              reason: 'Manual correction'
            })
          }
          if (testRow.result_value !== testRow.originalData.result_value) {
            corrections.push({
              line_number: testRow.line_number,
              field: 'result_value',
              new_value: testRow.result_value,
              old_value: testRow.originalData.result_value,
              reason: 'Manual correction'
            })
          }
          if (testRow.units !== testRow.originalData.units) {
            corrections.push({
              line_number: testRow.line_number,
              field: 'units',
              new_value: testRow.units,
              old_value: testRow.originalData.units,
              reason: 'Manual correction'
            })
          }
          if (testRow.reference_range !== testRow.originalData.reference_range) {
            corrections.push({
              line_number: testRow.line_number,
              field: 'reference_range',
              new_value: testRow.reference_range,
              old_value: testRow.originalData.reference_range,
              reason: 'Manual correction'
            })
          }
          if (testRow.flag !== testRow.originalData.flag) {
            corrections.push({
              line_number: testRow.line_number,
              field: 'flag',
              new_value: testRow.flag,
              old_value: testRow.originalData.flag,
              reason: 'Manual correction'
            })
          }
        }
      })
    })

    // Collect header field corrections
    reviewSession.headerFields.forEach((headerField, headerFieldIndex) => {
      if (headerField.originalData) {
        if (headerField.label !== headerField.originalData.label) {
          corrections.push({
            line_number: headerField.line_number,
            field: 'header_label',
            new_value: headerField.label,
            old_value: headerField.originalData.label,
            reason: 'Manual correction'
          })
        }
        if (headerField.value !== headerField.originalData.value) {
          corrections.push({
            line_number: headerField.line_number,
            field: 'header_value',
            new_value: headerField.value,
            old_value: headerField.originalData.value,
            reason: 'Manual correction'
          })
        }
      }
    })

    if (corrections.length === 0) {
      toast.info('No changes to save')
      return
    }

    saveCorrectsMutation.mutate(corrections)
  }

  const addToTraining = () => {
    if (!reviewSession) return

    // Generate training annotations from corrections
    const annotations: TrainingAnnotation[] = []
    
    reviewSession.result.lab_panels.forEach((panel, panelIndex) => {
      panel.test_rows.forEach((testRow, testRowIndex) => {
        if (testRow.originalData) {
          // Create annotation for corrected test row
          annotations.push({
            line_number: testRow.line_number,
            text: testRow.text,
            original_role: 'TEST_ROW', // Assuming all are test rows
            corrected_role: 'TEST_ROW', // Could be different if role classification was wrong
            original_tokens: [
              { text: testRow.originalData.test_name || '', label: 'TEST_NAME', start: 0, end: 0 },
              { text: testRow.originalData.result_value || '', label: 'RESULT_VALUE', start: 0, end: 0 },
              { text: testRow.originalData.units || '', label: 'UNITS', start: 0, end: 0 },
              { text: formatReferenceRange(testRow.originalData.reference_range), label: 'REFERENCE_RANGE', start: 0, end: 0 },
              { text: testRow.originalData.flag || '', label: 'FLAG', start: 0, end: 0 },
            ].filter(token => token.text && token.text !== '—'),
            corrected_tokens: [
              { text: testRow.test_name || '', label: 'TEST_NAME', start: 0, end: 0 },
              { text: testRow.result_value || '', label: 'RESULT_VALUE', start: 0, end: 0 },
              { text: testRow.units || '', label: 'UNITS', start: 0, end: 0 },
              { text: formatReferenceRange(testRow.reference_range), label: 'REFERENCE_RANGE', start: 0, end: 0 },
              { text: testRow.flag || '', label: 'FLAG', start: 0, end: 0 },
            ].filter(token => token.text && token.text !== '—'),
            timestamp: new Date().toISOString(),
            reviewer: 'manual', // Could be user ID in real app
          })
        }
      })
    })

    if (annotations.length === 0) {
      toast.info('No corrections to add to training')
      return
    }

    addToTrainingMutation.mutate(annotations)
  }

  if (!jobId) {
    return <div>Invalid job ID</div>
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle size={48} className="mx-auto text-error-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Failed to Load Result
        </h2>
        <p className="text-gray-600 mb-4">
          {error.message || 'An error occurred while loading the result'}
        </p>
        <button onClick={() => navigate('/processed')} className="btn-primary">
          Back to Results
        </button>
      </div>
    )
  }

  if (isLoading || !reviewSession) {
    return (
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-200 p-4 bg-white">
          <div className="h-6 w-64 bg-gray-200 rounded animate-pulse" />
          <div className="h-8 w-80 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="header-card animate-pulse">
              <div className="h-5 w-40 bg-gray-200 rounded mb-3" />
              {Array.from({ length: 4 }).map((_, j) => (
                <div key={j} className="flex justify-between items-center mb-2">
                  <div className="h-4 w-24 bg-gray-200 rounded" />
                  <div className="h-4 w-32 bg-gray-200 rounded" />
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
          <div className="h-5 w-48 bg-gray-200 rounded mb-4" />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-4 w-full bg-gray-200 rounded mb-3" />
          ))}
        </div>
      </div>
    )
  }

  // Helper functions for metadata
  const findSourceMeta = (path: string) => {
    // Try to find source information from extracted text
    if (!extractedText?.pages) return undefined

    const value = getSchemaValue(path)
    if (!value) return undefined

    // Simple search through extracted text for matching content
    for (const page of extractedText.pages) {
      const matchingLine = page.lines?.find((line: any) =>
        line.text && String(value).includes(line.text.trim())
      )
      if (matchingLine) {
        return {
          line: page.lines?.indexOf(matchingLine) + 1,
          page: page.page
        }
      }
    }
    return undefined
  }

  const findConfidence = (path: string) => {
    // Try to find confidence from extracted text
    if (!extractedText?.pages) return undefined

    const value = getSchemaValue(path)
    if (!value) return undefined

    // Simple search through extracted text for confidence
    for (const page of extractedText.pages) {
      const matchingLine = page.lines?.find((line: any) =>
        line.text && String(value).includes(line.text.trim())
      )
      if (matchingLine?.confidence) {
        return matchingLine.confidence
      }
    }
    return undefined
  }

  const modifiedTestRowsCount = reviewSession.result.lab_panels
    .reduce((sum, panel) => sum + panel.test_rows.filter(row => row.originalData).length, 0)
  const modifiedHeaderFieldsCount = reviewSession.headerFields.filter(field => field.originalData).length
  const correctedFieldsCount = Object.values(fieldStates).filter(state => state.state === 'corrected').length
  const totalModifiedCount = modifiedTestRowsCount + modifiedHeaderFieldsCount + (isFieldsDirty ? correctedFieldsCount : 0)

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isFieldsDirty) {
        e.preventDefault()
        e.returnValue = ''
        return ''
      }
      return undefined
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isFieldsDirty])

  // Prepare section navigation data
  const navigationSections = useMemo(() => {
    const sections = SECTION_ORDER.map(sectionKey => {
      const section = SECTIONS.find(s => s.key === sectionKey)
      if (!section) return null

      const defs = fieldsForSection(sectionKey)
      if (defs.length === 0) return null

      const sectionDirty = defs.some(def => schemaFieldStatus(def.path).dirty)

      return {
        key: sectionKey,
        title: section.title,
        dirty: sectionDirty
      }
    }).filter(Boolean) as { key: string; title: string; dirty: boolean }[]

    // Add Panels & Tests section
    const panelsTestsDirty = reviewSession.result.lab_panels
      .some(panel => panel.test_rows.some(row => row.originalData))
    sections.push({
      key: 'panels-tests',
      title: 'Panels & Tests',
      dirty: panelsTestsDirty
    })

    return sections
  }, [schemaFieldStatus, reviewSession])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 p-4 bg-white">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate(buildResultPath('viewer', jobId))}
            className="btn-ghost p-2"
            title="Back to viewer"
            aria-label="Back to viewer"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Manual Review & Correction
            </h1>
            <p className="text-sm text-gray-600">
              Job ID: {jobId.slice(0, 8)}...
              {totalModifiedCount > 0 && (
                <span className="ml-4 text-warning-600">
                  {totalModifiedCount} modification{totalModifiedCount !== 1 ? 's' : ''}
                  {isFieldsDirty && (
                    <span className="ml-2 text-blue-600">
                      (autosave enabled)
                    </span>
                  )}
                  {modifiedHeaderFieldsCount > 0 && modifiedTestRowsCount > 0 &&
                    ` (${modifiedTestRowsCount} test rows, ${modifiedHeaderFieldsCount} header fields)`
                  }
                </span>
              )}
            </p>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          {/* Status */}
          <SaveStatusIndicator status={saveStatus} />

          {/* Autosave toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
            <input
              type="checkbox"
              className="rounded border-gray-300"
              checked={autosaveEnabled}
              onChange={(e) => setAutosaveEnabled(e.target.checked)}
            />
            Autosave
          </label>

          {/* Show metadata toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
            <input
              type="checkbox"
              className="rounded border-gray-300"
              checked={showMetadata}
              onChange={(e) => setShowMetadata(e.target.checked)}
            />
            Show confidence & source
          </label>

          {/* Compact mode toggle */}
          <label className="flex items-center gap-2 text-sm text-gray-700 select-none">
            <input
              type="checkbox"
              className="rounded border-gray-300"
              checked={compactMode}
              onChange={(e) => setCompactMode(e.target.checked)}
            />
            Compact mode
          </label>

          {/* Save all */}
          <button
            onClick={() => {
              const handleSave = async () => {
                try {
                  if (isFieldsDirty) {
                    await saveAllFields()
                  }
                  if (totalModifiedCount - (isFieldsDirty ? correctedFieldsCount : 0) > 0) {
                    saveAllCorrections()
                  }
                } catch (error) {
                  console.error('Save failed:', error)
                  toast.error('Save failed. Please try again.')
                }
              }
              void handleSave()
            }}
            disabled={(saveCorrectsMutation.isPending || isFieldsLoading) || totalModifiedCount === 0}
            className="btn-success flex items-center space-x-2"
          >
            <Save size={16} />
            <span>Save all</span>
            {(saveCorrectsMutation.isPending || isFieldsLoading) && <div className="spinner w-4 h-4 ml-2" />}
          </button>

          {/* Reset all corrections */}
          <button
            onClick={() => {
              if (window.confirm('Reset all corrections back to extracted values?')) {
                resetAll()
              }
            }}
            className="btn-ghost text-gray-700"
            disabled={totalModifiedCount === 0 && !isFieldsDirty}
            title="Reset all corrections"
          >
            Reset all
          </button>
        </div>
      </div>

      {/* Small legend */}
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-600 flex items-center gap-3">
        <span>Legend:</span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">Extracted</span>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">Corrected</span>
        <button
          onClick={() => setShowConfidence(!showConfidence)}
          className={cn(
            'ml-auto btn-ghost flex items-center space-x-2',
            showConfidence && 'bg-blue-50 text-blue-700'
          )}
        >
          <Eye size={14} />
          <span>Confidence</span>
        </button>
      </div>

      {/* Backend unavailable banner */}
      {backendUnavailable && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-3">
          <div className="flex items-center">
            <AlertTriangle size={16} className="text-red-600 mr-2" />
            <span className="text-red-800 text-sm font-medium">
              Backend unavailable - Some features may not work correctly
            </span>
          </div>
        </div>
      )}
      
      {/* Fields error banner */}
      {fieldsError && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <AlertTriangle size={16} className="text-red-600 mr-2" />
              <span className="text-red-800 text-sm font-medium">
                {saveStatus === 'error' ? 'Save failed' : 'Error loading field data'}: {fieldsError}
              </span>
            </div>
            {saveStatus === 'error' && (
              <button
                onClick={() => window.location.reload()}
                className="text-red-600 hover:text-red-700 text-sm underline"
              >
                Refresh page
              </button>
            )}
          </div>
        </div>
      )}

      {/* Panel tabs */}
      {reviewSession.result.lab_panels.length > 1 && (
        <div className="flex space-x-1 p-4 border-b border-gray-200 bg-gray-50">
          {reviewSession.result.lab_panels.map((panel, index) => {
            const modifiedCount = panel.test_rows.filter(row => row.originalData).length
            return (
              <button
                key={panel.id}
                onClick={() => setSelectedPanel(index)}
                className={cn(
                  'px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center space-x-2',
                  selectedPanel === index
                    ? 'bg-white text-primary-700 shadow-sm border border-primary-200'
                    : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                )}
              >
                <span>{panel.name}</span>
                {modifiedCount > 0 && (
                  <span className="bg-warning-200 text-warning-800 text-xs px-1.5 py-0.5 rounded-full">
                    {modifiedCount}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Mobile navigation */}
      <div className="block md:hidden px-4 py-3 bg-gray-50 border-b border-gray-200">
        <MobileSectionNav sections={navigationSections} />
      </div>

      {/* Main content */}
      <div className="flex-1 flex">
        {/* Desktop side navigation */}
        <div className="hidden md:block w-64 bg-gray-50 border-r border-gray-200 p-4">
          <SectionNav sections={navigationSections} />
        </div>

        {/* Content area */}
        <div className="flex-1 p-6 overflow-y-auto">
        {/* Header cards with document info (defensive: only when enhanced info present) */}
        {(() => {
          const info = reviewSession.result.document_info as EnhancedDocumentInfo | undefined
          const hasEnhanced = info && (
            !!info.patient ||
            !!info.specimen ||
            !!info.performing_lab ||
            !!info.vendor ||
            !!info.ordering ||
            !!info.report
          )
          return hasEnhanced ? (
            <HeaderCards documentInfo={info} className="mb-6" />
          ) : null
        })()}

        {/* Header & Envelope Fields */}
        <HeaderFieldsEditor 
          headerFields={reviewSession.headerFields}
          onUpdateHeaderField={updateHeaderField}
          onRevertHeaderField={revertHeaderField}
        />

        {/* Schema-driven Review Form Sections */}
        <div className={cn("space-y-6", compactMode && "space-y-4")}>
          {SECTION_ORDER.map(sectionKey => {
            const section = SECTIONS.find(s => s.key === sectionKey)
            if (!section) return null

            const defs = fieldsForSection(sectionKey)
            if (defs.length === 0) return null

            const sectionDirty = defs.some(def => schemaFieldStatus(def.path).dirty)
            const sectionSaving = defs.some(def => schemaFieldStatus(def.path).saving)

            return (
              <div key={sectionKey} id={`section-${sectionKey}`}>
                <SectionCard
                  title={section.title}
                  subtitle={section.subtitle}
                  description={section.description}
                  dirty={sectionDirty}
                  saving={sectionSaving}
                  onSaveAll={() => saveSchemaSection(defs.map(def => def.path))}
                  onResetAll={() => resetSchemaSection(defs.map(def => def.path))}
                >
                <div className={cn(
                  "grid grid-cols-12 gap-4",
                  compactMode && "gap-2"
                )}>
                  {defs.map(def => {
                    const value = getSchemaValue(def.path)
                    const draft = schemaDrafts[def.path] ?? value
                    const { dirty, saving, saved, error } = schemaFieldStatus(def.path)

                    return (
                      <FieldRow
                        key={def.path}
                        def={def}
                        value={value}
                        draft={draft}
                        error={error}
                        saving={saving}
                        saved={saved}
                        onChange={(v) => setSchemaDraft(def.path, v)}
                        onSave={() => saveSchemaField(def.path)}
                        onReset={() => resetSchemaField(def.path)}
                        source={showMetadata ? findSourceMeta(def.path) : undefined}
                        confidence={showMetadata ? findConfidence(def.path) : undefined}
                      />
                    )
                  })}
                </div>
                </SectionCard>
              </div>
            )
          })}
        </div>

        {/* Panels & Tests */}
        <div id="section-panels-tests" className="space-y-8">
          <h2 className="text-xl font-semibold text-gray-900 border-b border-gray-200 pb-2">
            Panels & Tests
          </h2>
          {/* Panels Table */}
          <PanelsTable
            panels={reviewSession.result.lab_panels}
            onUpdatePanel={(panelIndex, updates) => {
              if (!reviewSession) return
              const newSession = { ...reviewSession }
              newSession.result.lab_panels[panelIndex] = {
                ...newSession.result.lab_panels[panelIndex],
                ...updates
              }
              setReviewSession(newSession)
            }}
            onRevertPanel={(panelIndex) => {
              if (!reviewSession) return
              // Revert panel to original state
              // This would need original data tracking
              console.log('Revert panel', panelIndex)
            }}
            showConfidence={showConfidence}
            jobId={jobId!}
            resultData={reviewSession.result}
            extractedTextData={extractedText}
          />

          {/* Tests Table */}
          {reviewSession.result.lab_panels.length > 0 && (
            <TestsTable
              panels={reviewSession.result.lab_panels}
              onUpdateTestRow={updateTestRow}
              onRevertTestRow={revertTestRow}
              onRevertAllTestsInRow={(panelIndex, testRowIndex) => {
                // Revert entire test row
                revertTestRow(panelIndex, testRowIndex)
              }}
              showConfidence={showConfidence}
              selectedPanel={selectedPanel}
              jobId={jobId!}
              resultData={reviewSession.result}
              extractedTextData={extractedText}
              autosaveEnabled={autosaveEnabled}
            />
          )}
        </div>
        </div>
      </div>
    </div>
  )
}
