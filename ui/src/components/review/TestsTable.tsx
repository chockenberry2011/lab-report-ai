import React, { useState, useRef, useCallback, useEffect } from 'react'
import { RotateCcw, AlertTriangle, Info } from 'lucide-react'
import { InlineEditor } from './InlineEditor'
import { useCorrections } from '@/hooks/useCorrections'
import { cn, formatConfidence, getConfidenceBadgeClass } from '@/utils'
import { getFlagClass } from '@/utils/formatters'
import type { EditableTestRow, EditablePanel } from '@/types'
import type { FieldDefinition } from '@/types/review-fields'

interface TestsTableProps {
  panels: EditablePanel[]
  onUpdateTestRow: (panelIndex: number, testRowIndex: number, updates: Partial<EditableTestRow>) => void
  onRevertTestRow: (panelIndex: number, testRowIndex: number) => void
  onRevertAllTestsInRow: (panelIndex: number, testRowIndex: number) => void
  showConfidence: boolean
  jobId: string
  resultData: any
  extractedTextData?: any
  selectedPanel: number
  autosaveEnabled?: boolean
}

interface CellPosition {
  panelIndex: number
  rowIndex: number
  field: string
}

interface TestCellProps {
  testRow: EditableTestRow
  field: keyof EditableTestRow
  panelIndex: number
  rowIndex: number
  isEditing: boolean
  onStartEdit: () => void
  onSave: (value: any) => void
  onCancel: () => void
  onKeyDown: (e: React.KeyboardEvent) => void
  showConfidence: boolean
  className?: string
}

// Test field definitions for the table
const TEST_FIELD_DEFINITIONS: FieldDefinition[] = [
  { key: 'test_name', label: 'Test Name', type: 'text', section: 'test', path: 'test_name' },
  { key: 'result_value', label: 'Result', type: 'text', section: 'test', path: 'result_value' },
  { key: 'units', label: 'Units', type: 'text', section: 'test', path: 'units' },
  { key: 'reference_range_text', label: 'Ref Range', type: 'text', section: 'test', path: 'reference_range_text' },
  { key: 'reference_range_low', label: 'Low', type: 'number', section: 'test', path: 'reference_range_low' },
  { key: 'reference_range_high', label: 'High', type: 'number', section: 'test', path: 'reference_range_high' },
  { key: 'flag', label: 'Flag', type: 'select', section: 'test', path: 'flag' }
]

function TestCell({
  testRow,
  field,
  panelIndex,
  rowIndex,
  isEditing,
  onStartEdit,
  onSave,
  onCancel,
  onKeyDown,
  showConfidence,
  className
}: TestCellProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  const cellRef = useRef<HTMLDivElement>(null)

  const value = testRow[field]
  const isEmpty = value === null || value === undefined || value === ''
  const displayValue = isEmpty ? '—' : (value as any)
  const isModified = testRow.originalData && testRow.originalData[field] !== value

  // Get confidence for this specific field
  const fieldConfidence = testRow.field_confidences?.[
    field === 'reference_range_text' ? 'reference_range' :
    field === 'result_value' ? 'value_parse' :
    field === 'test_name' ? 'test_name_clarity' :
    field === 'units' ? 'unit_validity' :
    'overall'
  ]

  const handleClick = () => {
    if (!isEditing) {
      onStartEdit()
    }
  }

  const handleSave = (newValue: any) => {
    onSave(newValue)
  }

  // Format value for display
  const getDisplayValue = () => {
    if (field === 'flag' && value) {
      return (
        <span className={getFlagClass(value)}>
          {value}
        </span>
      )
    }

    // Truncate long values and show in tooltip
    if (!isEmpty && typeof displayValue === 'string' && displayValue.length > 20) {
      return (
        <div
          className="relative cursor-help"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          {displayValue.slice(0, 17)}...
          {showTooltip && (
            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap z-10">
              {displayValue}
            </div>
          )}
        </div>
      )
    }

    if (isEmpty) {
      return (
        <span className="text-gray-400 italic" title="Not provided on report">—</span>
      )
    }

    return displayValue as any
  }

  if (isEditing) {
    const fieldDef = TEST_FIELD_DEFINITIONS.find(f => f.key === field)
    const selectOptions = field === 'flag'
      ? ['', 'H', 'HIGH', 'L', 'LOW', 'ABN', 'CRIT']
      : undefined

    return (
      <td className={cn('px-2 py-1 min-w-0', className)}>
        <InlineEditor
          initialValue={value}
          type={fieldDef?.type || 'text'}
          options={selectOptions}
          onSave={handleSave}
          onCancel={onCancel}
        />
      </td>
    )
  }

  return (
    <td
      ref={cellRef}
      className={cn(
        'px-2 py-2 text-sm cursor-pointer hover:bg-gray-50 transition-colors min-w-0 relative',
        isModified && 'bg-yellow-50 border-l-2 border-yellow-400',
        className
      )}
      onClick={handleClick}
      onKeyDown={onKeyDown}
      tabIndex={0}
    >
      <div className="flex items-center gap-1">
        <div className="min-w-0 flex-1">
          {getDisplayValue()}
        </div>

        {/* Confidence badge */}
        {showConfidence && fieldConfidence !== undefined && (
          <span className={cn(
            'inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium',
            getConfidenceBadgeClass(fieldConfidence)
          )}>
            {Math.round(fieldConfidence * 100)}%
          </span>
        )}

        {/* Modified indicator */}
        {isModified && (
          <div className="w-1 h-1 bg-yellow-600 rounded-full" title="Modified" />
        )}
      </div>
    </td>
  )
}

interface TestRowProps {
  testRow: EditableTestRow
  panelIndex: number
  rowIndex: number
  isStriped: boolean
  editingCell: CellPosition | null
  onStartEdit: (position: CellPosition) => void
  onSave: (field: keyof EditableTestRow, value: any) => void
  onCancel: () => void
  onRevertRow: () => void
  onKeyDown: (e: React.KeyboardEvent, field: string) => void
  showConfidence: boolean
}

function TestRow({
  testRow,
  panelIndex,
  rowIndex,
  isStriped,
  editingCell,
  onStartEdit,
  onSave,
  onCancel,
  onRevertRow,
  onKeyDown,
  showConfidence
}: TestRowProps) {
  const isModified = testRow.originalData !== undefined
  const hasLowConfidence = testRow.confidence < 0.7

  const fields: (keyof EditableTestRow)[] = [
    'test_name',
    'result_value',
    'units',
    'reference_range_text',
    'reference_range_low',
    'reference_range_high',
    'flag'
  ]

  return (
    <tr className={cn(
      isStriped && 'bg-gray-50',
      isModified && 'ring-1 ring-yellow-400',
      hasLowConfidence && showConfidence && 'ring-1 ring-orange-400'
    )}>
      {/* Row indicator */}
      <td className="w-12 px-2 py-2 text-xs text-gray-500 text-center">
        <div className="flex flex-col items-center gap-1">
          <span>{rowIndex + 1}</span>
          {isModified && (
            <button
              onClick={onRevertRow}
              className="p-0.5 text-gray-400 hover:text-orange-600 transition-colors"
              title="Reset row"
            >
              <RotateCcw size={12} />
            </button>
          )}
        </div>
      </td>

      {/* Test fields */}
      {fields.map((field) => (
        <TestCell
          key={field}
          testRow={testRow}
          field={field}
          panelIndex={panelIndex}
          rowIndex={rowIndex}
          isEditing={editingCell?.panelIndex === panelIndex &&
                     editingCell?.rowIndex === rowIndex &&
                     editingCell?.field === field}
          onStartEdit={() => onStartEdit({ panelIndex, rowIndex, field })}
          onSave={(value) => onSave(field, value)}
          onCancel={onCancel}
          onKeyDown={(e) => onKeyDown(e, field)}
          showConfidence={showConfidence}
          className={field === 'test_name' ? 'min-w-[150px]' :
                    field === 'result_value' ? 'min-w-[100px]' :
                    field === 'reference_range_text' ? 'min-w-[120px]' :
                    'min-w-[80px]'}
        />
      ))}

      {/* Quality indicators */}
      <td className="w-16 px-2 py-2 text-center">
        <div className="flex items-center justify-center gap-1">
          {hasLowConfidence && showConfidence && (
            <AlertTriangle size={14} className="text-orange-500" title="Low confidence" />
          )}
          {testRow.comments && (
            <Info size={14} className="text-blue-500" title={testRow.comments} />
          )}
        </div>
      </td>
    </tr>
  )
}

export function TestsTable({
  panels,
  onUpdateTestRow,
  onRevertTestRow,
  onRevertAllTestsInRow,
  showConfidence,
  selectedPanel,
  jobId,
  resultData,
  extractedTextData,
  autosaveEnabled = true
}: TestsTableProps) {
  const [editingCell, setEditingCell] = useState<CellPosition | null>(null)
  const tableRef = useRef<HTMLTableElement>(null)

  // Use corrections hook for test-level fields
  const {
    fieldStates,
    updateField,
    resetField
  } = useCorrections({
    jobId,
    resultData,
    extractedTextData,
    autosave: autosaveEnabled
  })

  const currentPanel = panels[selectedPanel]
  const allTests = currentPanel?.test_rows || []

  // Should we virtualize for performance?
  const shouldVirtualize = allTests.length > 100

  const handleStartEdit = useCallback((position: CellPosition) => {
    setEditingCell(position)
  }, [])

  const handleSave = useCallback((field: keyof EditableTestRow, value: any) => {
    if (!editingCell) return

    const { panelIndex, rowIndex } = editingCell

    // Update via corrections system
    const fieldKey = `test_${panelIndex}_${rowIndex}_${field}`
    updateField(fieldKey, value)

    // Also update the test row directly for immediate UI feedback
    onUpdateTestRow(panelIndex, rowIndex, { [field]: value })

    setEditingCell(null)
  }, [editingCell, updateField, onUpdateTestRow])

  const handleCancel = useCallback(() => {
    setEditingCell(null)
  }, [])

  const handleRevertRow = useCallback((panelIndex: number, rowIndex: number) => {
    onRevertTestRow(panelIndex, rowIndex)
    setEditingCell(null)
  }, [onRevertTestRow])

  // Keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent, currentField: string) => {
    if (!editingCell) return

    const fields = ['test_name', 'result_value', 'units', 'reference_range_text',
                   'reference_range_low', 'reference_range_high', 'flag']
    const currentFieldIndex = fields.indexOf(currentField)
    const { panelIndex, rowIndex } = editingCell

    let newPosition: CellPosition | null = null

    switch (e.key) {
      case 'Tab':
        e.preventDefault()
        if (e.shiftKey) {
          // Previous cell
          if (currentFieldIndex > 0) {
            newPosition = { panelIndex, rowIndex, field: fields[currentFieldIndex - 1] }
          } else if (rowIndex > 0) {
            newPosition = { panelIndex, rowIndex: rowIndex - 1, field: fields[fields.length - 1] }
          }
        } else {
          // Next cell
          if (currentFieldIndex < fields.length - 1) {
            newPosition = { panelIndex, rowIndex, field: fields[currentFieldIndex + 1] }
          } else if (rowIndex < allTests.length - 1) {
            newPosition = { panelIndex, rowIndex: rowIndex + 1, field: fields[0] }
          }
        }
        break

      case 'ArrowUp':
        e.preventDefault()
        if (rowIndex > 0) {
          newPosition = { panelIndex, rowIndex: rowIndex - 1, field: currentField }
        }
        break

      case 'ArrowDown':
        e.preventDefault()
        if (rowIndex < allTests.length - 1) {
          newPosition = { panelIndex, rowIndex: rowIndex + 1, field: currentField }
        }
        break

      case 'ArrowLeft':
        e.preventDefault()
        if (currentFieldIndex > 0) {
          newPosition = { panelIndex, rowIndex, field: fields[currentFieldIndex - 1] }
        }
        break

      case 'ArrowRight':
        e.preventDefault()
        if (currentFieldIndex < fields.length - 1) {
          newPosition = { panelIndex, rowIndex, field: fields[currentFieldIndex + 1] }
        }
        break

      case 'Enter':
        e.preventDefault()
        // Save current edit
        break

      case 'Escape':
        e.preventDefault()
        handleCancel()
        return
    }

    if (newPosition) {
      setEditingCell(newPosition)
    }
  }, [editingCell, allTests.length, handleCancel])

  // Close editing when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (tableRef.current && !tableRef.current.contains(event.target as Node)) {
        setEditingCell(null)
      }
    }

    if (editingCell) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [editingCell])

  if (!currentPanel) {
    return (
      <div className="text-center py-8 text-gray-500">
        No panel selected.
      </div>
    )
  }

  if (allTests.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No tests found in this panel.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Test Results - {currentPanel.name}
        </h3>
        <div className="text-sm text-gray-600">
          {allTests.length} test{allTests.length !== 1 ? 's' : ''} •
          Click cells to edit • Use Tab/Arrow keys to navigate
        </div>
      </div>

      <div className="overflow-x-auto border rounded-lg">
        <table ref={tableRef} className="min-w-full divide-y divide-gray-200">
          {/* Sticky header */}
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th className="w-12 px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                #
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[150px]">
                Test Name
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[100px]">
                Result
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                Units
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                Ref Range
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                Low
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                High
              </th>
              <th className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                Flag
              </th>
              <th className="w-16 px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                <AlertTriangle size={12} title="Quality indicators" />
              </th>
            </tr>
          </thead>

          <tbody className="bg-white divide-y divide-gray-200">
            {allTests.map((testRow, rowIndex) => (
              <TestRow
                key={`${testRow.line_number}-${rowIndex}`}
                testRow={testRow}
                panelIndex={selectedPanel}
                rowIndex={rowIndex}
                isStriped={rowIndex % 2 === 1}
                editingCell={editingCell}
                onStartEdit={handleStartEdit}
                onSave={handleSave}
                onCancel={handleCancel}
                onRevertRow={() => handleRevertRow(selectedPanel, rowIndex)}
                onKeyDown={handleKeyDown}
                showConfidence={showConfidence}
              />
            ))}
          </tbody>
        </table>
      </div>

      {shouldVirtualize && (
        <div className="text-xs text-gray-500 text-center py-2">
          Large dataset detected. Consider implementing virtualization for better performance.
        </div>
      )}
    </div>
  )
}
