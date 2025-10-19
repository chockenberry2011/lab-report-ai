import React from 'react'
import { Edit2, RotateCcw, Eye } from 'lucide-react'
import type { LabeledFieldProps } from '@/types/review-fields'
import { cn } from '@/utils'

export function LabeledField({
  label,
  value,
  state,
  confidence,
  helperText,
  onEdit,
  onReset,
  onPeekOriginal
}: LabeledFieldProps) {
  const isEmpty = value === null || value === undefined || value === ''
  const displayValue = isEmpty ? '—' : (value as any)

  const getStateBadge = () => {
    if (state === 'corrected') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
          Corrected
        </span>
      )
    }
    
    if (state === 'extracted' && confidence !== undefined) {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
          Extracted {Math.round(confidence * 100)}%
        </span>
      )
    }

    return null
  }

  return (
    <div className="group flex flex-col sm:flex-row sm:items-start gap-2 py-3 border-b border-gray-100">
      {/* Label */}
      <div className="sm:w-48 flex-shrink-0">
        <label className="text-sm font-medium text-gray-700">
          {label}
        </label>
        {helperText && (
          <p className="text-xs text-gray-500 mt-0.5">{helperText}</p>
        )}
      </div>

      {/* Value and Controls */}
      <div className="flex-1 flex items-start justify-between">
        <div className="flex flex-col gap-1">
          {/* Value */}
          <div
            className={cn(
              'text-sm',
              isEmpty ? 'text-gray-400 italic' : 'text-gray-900'
            )}
            title={isEmpty ? 'Not provided on report' : undefined}
          >
            {displayValue}
          </div>
          
          {/* Status Badge */}
          <div className="flex items-center gap-2">
            {getStateBadge()}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onEdit}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title={`Edit ${label}`}
          >
            <Edit2 size={14} />
          </button>
          
          {state === 'corrected' && onReset && (
            <button
              onClick={onReset}
              className="p-1 text-gray-400 hover:text-orange-600 transition-colors"
              title="Reset to extracted value"
            >
              <RotateCcw size={14} />
            </button>
          )}
          
          {onPeekOriginal && (
            <button
              onClick={onPeekOriginal}
              className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
              title="View original text"
            >
              <Eye size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
