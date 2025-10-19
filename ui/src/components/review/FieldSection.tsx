import React from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { FieldRow } from './FieldRow'
import type { FieldDefinition, FieldValue } from '@/types/review-fields'

interface FieldSectionProps {
  title: string
  fields: FieldDefinition[]
  fieldStates: Record<string, FieldValue>
  onFieldUpdate: (fieldKey: string, value: any) => void
  onFieldReset: (fieldKey: string) => void
  isCollapsed?: boolean
  onToggleCollapsed?: () => void
}

export function FieldSection({
  title,
  fields,
  fieldStates,
  onFieldUpdate,
  onFieldReset,
  isCollapsed = false,
  onToggleCollapsed
}: FieldSectionProps) {
  // Only show fields that have values or have been corrected
  const visibleFields = fields.filter(field => {
    const fieldState = fieldStates[field.key]
    return fieldState && (
      fieldState.current !== null ||
      fieldState.state === 'corrected' ||
      fieldState.state === 'extracted'
    )
  })

  if (visibleFields.length === 0) {
    return null
  }

  const correctedCount = visibleFields.filter(field => 
    fieldStates[field.key]?.state === 'corrected'
  ).length

  return (
    <div className="bg-white rounded-lg border border-gray-200 mb-6">
      <div 
        className="flex items-center justify-between p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50"
        onClick={onToggleCollapsed}
      >
        <div className="flex items-center gap-3">
          {onToggleCollapsed && (
            isCollapsed ? 
              <ChevronRight size={16} className="text-gray-400" /> : 
              <ChevronDown size={16} className="text-gray-400" />
          )}
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <span className="text-sm text-gray-500">
            {visibleFields.length} field{visibleFields.length !== 1 ? 's' : ''}
          </span>
        </div>
        
        {correctedCount > 0 && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            {correctedCount} corrected
          </span>
        )}
      </div>
      
      {!isCollapsed && (
        <div className="p-4">
          <div className="space-y-0">
            {visibleFields.map(field => (
              <FieldRow
                key={field.key}
                definition={field}
                fieldState={fieldStates[field.key]}
                onUpdate={(value) => onFieldUpdate(field.key, value)}
                onReset={() => onFieldReset(field.key)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}