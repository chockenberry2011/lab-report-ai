import React, { memo } from 'react'
import { Save, RotateCcw, Trash2 } from 'lucide-react'
import { cn } from '@/utils'

interface TestRowProps {
  testRow: any
  testIndex: number
  panelIndex: number
  hasModifications: boolean
  isSaving: boolean
  wasSaved: boolean
  resolvedValue: (fieldKey: string) => string
  onFieldChange: (fieldKey: string, value: string) => void
  onSave: (panelIndex: number, testIndex: number) => void
  onReset: (panelIndex: number, testIndex: number) => void
  onDelete: (panelIndex: number, testIndex: number) => void
}

const FLAG_OPTIONS = ['', 'H', 'L', 'CRIT', 'ABN'] as const

// Memoized component to prevent unnecessary rerenders
export const TestRow = memo(function TestRow({
  testRow,
  testIndex,
  panelIndex,
  hasModifications,
  isSaving,
  wasSaved,
  resolvedValue,
  onFieldChange,
  onSave,
  onReset,
  onDelete
}: TestRowProps) {
  return (
    <tr
      className={cn(
        "hover:bg-gray-50",
        hasModifications && "bg-yellow-50",
        isSaving && "bg-blue-50",
        wasSaved && "bg-green-50"
      )}
    >
      <td className="px-4 py-3">
        <input
          type="text"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.test_name`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.test_name`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="Test name"
        />
      </td>
      <td className="px-4 py-3">
        <input
          type="text"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.result_value`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.result_value`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="Result value"
        />
      </td>
      <td className="px-4 py-3">
        <input
          type="text"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.units`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.units`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="Units"
        />
      </td>
      <td className="px-4 py-3">
        <select
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.flag`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.flag`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
        >
          {FLAG_OPTIONS.map(option => (
            <option key={option} value={option}>
              {option || 'None'}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3">
        <input
          type="text"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.reference_range_text`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.reference_range_text`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="Reference range"
        />
      </td>
      <td className="px-4 py-3">
        <input
          type="number"
          step="0.01"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.reference_low`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.reference_low`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="Low"
        />
      </td>
      <td className="px-4 py-3">
        <input
          type="number"
          step="0.01"
          value={resolvedValue(`panels.${panelIndex}.tests.${testIndex}.reference_high`)}
          onChange={(e) => onFieldChange(`panels.${panelIndex}.tests.${testIndex}.reference_high`, e.target.value)}
          className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
          placeholder="High"
        />
      </td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end space-x-2">
          {(isSaving || wasSaved) && (
            <span
              className={cn(
                "text-xs px-2 py-1 rounded-full",
                isSaving && "bg-blue-100 text-blue-800",
                wasSaved && "bg-green-100 text-green-800"
              )}
              aria-live="polite"
            >
              {isSaving ? 'Saving…' : 'Saved'}
            </span>
          )}
          <button
            onClick={() => onSave(panelIndex, testIndex)}
            className="text-green-600 hover:text-green-900 p-1 disabled:opacity-50"
            title="Save row"
            disabled={!hasModifications || isSaving}
          >
            <Save className="h-4 w-4" />
          </button>
          <button
            onClick={() => onReset(panelIndex, testIndex)}
            className="text-gray-600 hover:text-gray-900 p-1 disabled:opacity-50"
            title="Reset row"
            disabled={isSaving}
          >
            <RotateCcw className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(panelIndex, testIndex)}
            className="text-red-600 hover:text-red-900 p-1 disabled:opacity-50"
            title="Delete row"
            disabled={isSaving}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  )
})