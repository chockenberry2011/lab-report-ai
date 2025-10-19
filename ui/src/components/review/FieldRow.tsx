import React, { useState } from 'react'
import { LabeledField } from './LabeledField'
import { InlineEditor } from './InlineEditor'
import type { FieldRowProps } from '@/types/review-fields'

export function FieldRow({
  definition,
  fieldState,
  onUpdate,
  onReset
}: FieldRowProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [showOriginalTooltip, setShowOriginalTooltip] = useState(false)

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleSave = (newValue: any) => {
    onUpdate(newValue)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setIsEditing(false)
  }

  const handleReset = () => {
    if (fieldState.original !== undefined) {
      onUpdate(fieldState.original)
    }
    onReset()
  }

  const handlePeekOriginal = () => {
    setShowOriginalTooltip(!showOriginalTooltip)
  }

  // Select options for specific fields
  const getSelectOptions = (): string[] | undefined => {
    if (definition.key === 'patient_sex') {
      return ['M', 'F', 'Male', 'Female', 'Other', 'Unknown']
    }
    return undefined
  }

  if (isEditing) {
    return (
      <div className="py-3 border-b border-gray-100">
        <div className="flex flex-col sm:flex-row sm:items-start gap-2">
          <div className="sm:w-48 flex-shrink-0">
            <label className="text-sm font-medium text-gray-700">
              {definition.label}
            </label>
          </div>
          <div className="flex-1">
            <InlineEditor
              initialValue={fieldState.current}
              type={definition.type}
              options={getSelectOptions()}
              onSave={handleSave}
              onCancel={handleCancel}
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <LabeledField
        label={definition.label}
        value={fieldState.current}
        state={fieldState.state}
        confidence={fieldState.confidence}
        helperText={definition.helperText}
        onEdit={handleEdit}
        onReset={fieldState.state === 'corrected' ? handleReset : undefined}
        onPeekOriginal={fieldState.sourceLine ? handlePeekOriginal : undefined}
      />
      
      {/* Original text tooltip */}
      {showOriginalTooltip && fieldState.sourceLine && (
        <div className="absolute top-full left-0 z-10 mt-2 p-3 bg-gray-900 text-white text-xs rounded-md shadow-lg max-w-md">
          <div className="font-medium mb-1">Original extracted text:</div>
          <div className="font-mono bg-gray-800 p-2 rounded">
            {fieldState.sourceLine}
          </div>
          {fieldState.sourcePage && (
            <div className="text-gray-300 mt-1">Page {fieldState.sourcePage}</div>
          )}
          <button
            onClick={() => setShowOriginalTooltip(false)}
            className="absolute top-1 right-1 text-gray-400 hover:text-white"
          >
            ×
          </button>
        </div>
      )}
    </div>
  )
}