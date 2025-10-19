import React, { useState } from 'react'
import { MessageCircle, AlertTriangle, RotateCcw } from 'lucide-react'
import { FieldRow } from './FieldRow'
import { useCorrections } from '@/hooks/useCorrections'
import { cn } from '@/utils'
import type { EditablePanel } from '@/types'
import type { FieldDefinition } from '@/types/review-fields'

interface PanelsTableProps {
  panels: EditablePanel[]
  onUpdatePanel: (panelIndex: number, updates: Partial<EditablePanel>) => void
  onRevertPanel: (panelIndex: number) => void
  showConfidence: boolean
  jobId: string
  resultData: any
  extractedTextData?: any
}

// Panel field definitions for corrections system
const PANEL_FIELD_DEFINITIONS: FieldDefinition[] = [
  {
    key: 'panel_name',
    label: 'Panel Name',
    type: 'text',
    section: 'panel',
    path: 'name'
  },
  {
    key: 'panel_type',
    label: 'Panel Type',
    type: 'text',
    section: 'panel',
    path: 'panel_type'
  },
  {
    key: 'collected_date',
    label: 'Collection Date',
    type: 'date',
    section: 'panel',
    path: 'collected_date'
  },
  {
    key: 'reference_lab',
    label: 'Reference Lab',
    type: 'text',
    section: 'panel',
    path: 'reference_lab'
  }
]

interface PanelRowProps {
  panel: EditablePanel
  panelIndex: number
  onUpdatePanel: (updates: Partial<EditablePanel>) => void
  onRevertPanel: () => void
  showConfidence: boolean
  fieldStates: any
  updateField: (fieldKey: string, value: any) => void
  resetField: (fieldKey: string) => void
}

function PanelRow({
  panel,
  panelIndex,
  onUpdatePanel,
  onRevertPanel,
  showConfidence,
  fieldStates,
  updateField,
  resetField
}: PanelRowProps) {
  const [showComments, setShowComments] = useState(false)
  const [isExpanded, setIsExpanded] = useState(false)

  const hasModifications = panel.test_rows.some(row => row.originalData)
  const panelFieldKey = `panel_${panelIndex}`

  const handleFieldUpdate = (field: string, value: any) => {
    // Create field key for this specific panel
    const fieldKey = `${panelFieldKey}_${field}`
    updateField(fieldKey, value)

    // Also update the panel directly for immediate UI feedback
    onUpdatePanel({ [field]: value })
  }

  const handleFieldReset = (field: string) => {
    const fieldKey = `${panelFieldKey}_${field}`
    resetField(fieldKey)

    // Reset panel field to original
    // This would need the original data structure
    onRevertPanel()
  }

  // Mock comments for demo - in real app this would come from panel data
  const comments = panel.review_reasons && panel.review_reasons.length > 0
    ? panel.review_reasons.join('; ')
    : null

  return (
    <div className={cn(
      'border rounded-lg mb-4',
      hasModifications && 'border-warning-300 bg-warning-50',
      panel.needs_review && 'border-orange-300'
    )}>
      {/* Panel Header */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Panel Name - Editable */}
            <div className="min-w-0 flex-1">
              <div className="font-medium text-gray-900 cursor-pointer hover:bg-gray-100 px-2 py-1 rounded">
                {panel.name || 'Unnamed Panel'}
              </div>
            </div>

            {/* Panel Type Badge */}
            {panel.panel_type && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {panel.panel_type}
              </span>
            )}

            {/* Test Count */}
            <span className="text-sm text-gray-500">
              {panel.test_count} test{panel.test_count !== 1 ? 's' : ''}
            </span>

            {/* Comments Icon */}
            {comments && (
              <button
                onClick={() => setShowComments(!showComments)}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors relative"
                title="View comments"
              >
                <MessageCircle size={16} />
                {showComments && (
                  <div className="absolute top-8 left-0 z-10 w-80 p-3 bg-gray-900 text-white text-sm rounded-md shadow-lg">
                    <div className="font-medium mb-1">Panel Comments:</div>
                    <div>{comments}</div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowComments(false)
                      }}
                      className="absolute top-1 right-1 text-gray-400 hover:text-white"
                    >
                      ×
                    </button>
                  </div>
                )}
              </button>
            )}

            {/* Needs Review Badge */}
            {panel.needs_review && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                <AlertTriangle size={12} className="mr-1" />
                Needs Review
              </span>
            )}

            {/* Confidence Score */}
            {showConfidence && (
              <span className={cn(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                panel.panel_score >= 0.8
                  ? 'bg-green-100 text-green-800'
                  : panel.panel_score >= 0.6
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-red-100 text-red-800'
              )}>
                {Math.round(panel.panel_score * 100)}%
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Modifications indicator */}
            {hasModifications && (
              <span className="text-xs text-warning-600 font-medium">
                {panel.test_rows.filter(row => row.originalData).length} modified
              </span>
            )}

            {/* Expand/Collapse Panel Details */}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="text-sm text-gray-500 hover:text-gray-700 px-2 py-1 rounded"
            >
              {isExpanded ? 'Hide Details' : 'Show Details'}
            </button>

            {/* Reset Panel Button */}
            {hasModifications && (
              <button
                onClick={onRevertPanel}
                className="p-1 text-gray-400 hover:text-orange-600 transition-colors"
                title="Reset all panel changes"
              >
                <RotateCcw size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Expanded Panel Details */}
        {isExpanded && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-2 gap-4">
              {PANEL_FIELD_DEFINITIONS.map((fieldDef) => {
                const fieldKey = `${panelFieldKey}_${fieldDef.path}`
                const fieldState = fieldStates[fieldKey] || {
                  current: (panel as any)[fieldDef.path],
                  original: (panel as any)[fieldDef.path],
                  state: 'extracted'
                }

                return (
                  <FieldRow
                    key={fieldDef.key}
                    definition={fieldDef}
                    fieldState={fieldState}
                    onUpdate={(value) => handleFieldUpdate(fieldDef.path, value)}
                    onReset={() => handleFieldReset(fieldDef.path)}
                  />
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function PanelsTable({
  panels,
  onUpdatePanel,
  onRevertPanel,
  showConfidence,
  jobId,
  resultData,
  extractedTextData
}: PanelsTableProps) {
  // Use corrections hook for panel-level fields
  const {
    fieldStates,
    updateField,
    resetField
  } = useCorrections({
    jobId,
    resultData,
    extractedTextData
  })

  if (panels.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No panels found in this lab report.
      </div>
    )
  }

  return (
    <div className="space-y-0">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Lab Panels</h3>
        <div className="text-sm text-gray-600">
          {panels.length} panel{panels.length !== 1 ? 's' : ''} •
          Click panel names or "Show Details" to edit panel information
        </div>
      </div>

      {panels.map((panel, index) => (
        <PanelRow
          key={panel.id}
          panel={panel}
          panelIndex={index}
          onUpdatePanel={(updates) => onUpdatePanel(index, updates)}
          onRevertPanel={() => onRevertPanel(index)}
          showConfidence={showConfidence}
          fieldStates={fieldStates}
          updateField={updateField}
          resetField={resetField}
        />
      ))}
    </div>
  )
}