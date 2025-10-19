import React from 'react'
import { useCorrections } from '@/hooks/useCorrections'

interface Props {
  resultId: string
  fieldKey: string
  label: string
}

/**
 * Example component showing the correct pattern for manual correction textareas
 * that won't reset while typing due to polling
 */
export function ManualCorrectionExample({ resultId, fieldKey, label }: Props) {
  const { drafts, updateDraft, saveChanges, markDirty } = useCorrections(resultId)

  return (
    <div className="space-y-2">
      <label htmlFor={fieldKey} className="block text-sm font-medium text-gray-700">
        {label}
      </label>

      <textarea
        id={fieldKey}
        value={drafts[fieldKey] ?? ''}
        onChange={(e) => updateDraft(fieldKey, e.target.value)}
        onFocus={() => markDirty(fieldKey)}
        onBlur={() => saveChanges([fieldKey])}
        rows={3}
        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
        placeholder={`Enter ${label.toLowerCase()}...`}
      />

      <p className="text-xs text-gray-500">
        Changes auto-save 600ms after you stop typing, or when you click outside the field.
      </p>
    </div>
  )
}