import React, { useCallback } from 'react'
import { Save, RotateCcw, Check, AlertTriangle, FileText, ExternalLink } from 'lucide-react'
import type { FieldDef } from '@/config/fieldSchema'
import { InputSwitch } from './InputSwitch'
import { HelpTip } from './HelpTip'
import { usePdfJump } from '@/components/review/PdfJumpContext'
import { cn } from '@/utils'

interface FieldRowProps {
  def: FieldDef
  value: any
  draft: any
  error?: string | null
  saving?: boolean
  saved?: boolean
  onChange: (v: any) => void
  onSave: () => Promise<void> | void
  onReset: () => void
  source?: { line?: number; page?: number }
  confidence?: number
  onJumpToPdf?: (fieldPath: string) => void
  focusMode?: boolean
  isActiveField?: boolean
}

export function FieldRow({
  def,
  value,
  draft,
  error,
  saving = false,
  saved = false,
  onChange,
  onSave,
  onReset,
  source,
  confidence,
  onJumpToPdf,
  focusMode = false,
  isActiveField = false
}: FieldRowProps) {
  const { onJumpToPdf: contextJumpToPdf } = usePdfJump()
  const effectiveJumpToPdf = onJumpToPdf || contextJumpToPdf

  const isDirty = draft !== value
  const showActions = isDirty || error || saving || saved

  const handleSave = useCallback(() => {
    const result = onSave()
    if (result instanceof Promise) {
      void result
    }
  }, [onSave])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const isTextarea = def.input === 'textarea'

    // Enter key handling
    if (e.key === 'Enter') {
      if (isTextarea && (e.metaKey || e.ctrlKey)) {
        // Cmd/Ctrl+Enter on textarea saves
        e.preventDefault()
        if (isDirty && !saving) {
          handleSave()
        }
      } else if (!isTextarea) {
        // Enter on other inputs saves
        e.preventDefault()
        if (isDirty && !saving) {
          handleSave()
        }
      }
    }

    // Escape key handling
    if (e.key === 'Escape' && isDirty && !saving) {
      e.preventDefault()
      onReset()
    }
  }, [def.input, isDirty, saving, handleSave, onReset])

  const getWidthClass = () => {
    switch (def.width) {
      case 'half':
        return 'col-span-12 md:col-span-6'
      case 'third':
        return 'col-span-12 md:col-span-4'
      case 'full':
      default:
        return 'col-span-12'
    }
  }

  const fieldId = `field-${def.path.replace(/\./g, '-')}`

  return (
    <div
      className={cn(
        'space-y-2 transition-all duration-200',
        getWidthClass(),
        focusMode && !isActiveField && 'opacity-40 blur-[1px]',
        isActiveField && 'ring-2 ring-blue-500 ring-opacity-50 rounded-lg p-2 bg-blue-50/30'
      )}
    >
      {/* Label and Help */}
      <div className="flex items-center justify-between">
        <div className="flex items-center">
          <label htmlFor={fieldId} className="block text-sm font-medium text-gray-700">
            {def.label}
            {def.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          {def.description && <HelpTip description={def.description} />}
          {/* PDF location indicator */}
          {source && (source.page || source.line) && (
            <span className="ml-2 text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">
              {source.page && `Page ${source.page}`}
              {source.page && source.line && ', '}
              {source.line && `Line ${source.line}`}
            </span>
          )}
        </div>

        {/* Jump to PDF button */}
        {effectiveJumpToPdf && source && (source.page || source.line) && (
          <button
            onClick={() => effectiveJumpToPdf(def.path)}
            className="text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded transition-colors flex items-center gap-1"
            title={`Jump to PDF ${source.page ? `page ${source.page}` : ''}${source.page && source.line ? ', ' : ''}${source.line ? `line ${source.line}` : ''}`}
          >
            <ExternalLink size={12} />
            <span>PDF</span>
          </button>
        )}
      </div>

      {/* Display current value when not editing */}
      {!isDirty && !value && (
        <div className="text-sm text-gray-400 italic" aria-hidden="true">—</div>
      )}

      {/* Input */}
      <div className="space-y-2">
        <div onKeyDown={handleKeyDown}>
          <InputSwitch def={def} value={draft} onChange={onChange} fieldId={fieldId} />
        </div>

        {/* Status Row */}
        {showActions && (
          <div className="flex items-center justify-between">
            {/* Actions */}
            <div className="flex items-center space-x-2">
              {isDirty && (
                <>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="btn-success p-1 text-xs focus:outline-none focus:ring-2 focus:ring-green-500"
                    title="Save field"
                  >
                    <Save size={12} />
                  </button>
                  <button
                    onClick={onReset}
                    disabled={saving}
                    className="btn-ghost p-1 text-xs text-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500"
                    title="Reset field"
                  >
                    <RotateCcw size={12} />
                  </button>
                </>
              )}
            </div>

            {/* Status and Info */}
            <div className="flex items-center space-x-2">
              {/* Status Messages */}
              {saving && (
                <div className="flex items-center">
                  <div className="w-3 h-3 mr-1">
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600"></div>
                  </div>
                  <span className="text-xs text-blue-600">Saving...</span>
                </div>
              )}
              {saved && !saving && !error && (
                <div className="flex items-center text-xs text-green-600">
                  <Check size={12} className="mr-1" />
                  <span>Saved</span>
                </div>
              )}
              {error && (
                <div className="flex items-center space-x-2">
                  <div className="flex items-center text-xs text-red-600">
                    <AlertTriangle size={12} className="mr-1" />
                    <span>{error}</span>
                  </div>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="text-xs text-red-600 hover:text-red-700 underline focus:outline-none focus:ring-2 focus:ring-red-500"
                    title="Retry save"
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Source Info */}
              {source && (source.line || source.page) && (
                <span className="text-xs text-gray-500">
                  {source.line && `Line ${source.line}`}
                  {source.line && source.page && ' • '}
                  {source.page && `Page ${source.page}`}
                </span>
              )}

              {/* Confidence Chip */}
              {confidence !== undefined && (
                <span className={cn(
                  'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                  confidence >= 0.9 ? 'bg-green-100 text-green-800' :
                  confidence >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                )}>
                  {Math.round(confidence * 100)}%
                </span>
              )}
            </div>
          </div>
        )}

        {/* Source and Confidence (when no actions shown) */}
        {!showActions && (source?.line || source?.page || confidence !== undefined) && (
          <div className="flex items-center justify-end space-x-2">
            {source && (source.line || source.page) && (
              <span className="text-xs text-gray-500">
                {source.line && `Line ${source.line}`}
                {source.line && source.page && ' • '}
                {source.page && `Page ${source.page}`}
              </span>
            )}

            {confidence !== undefined && (
              <span className={cn(
                'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                confidence >= 0.9 ? 'bg-green-100 text-green-800' :
                confidence >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              )}>
                {Math.round(confidence * 100)}%
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}