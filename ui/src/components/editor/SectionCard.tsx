import React from 'react'
import { Save, RotateCcw } from 'lucide-react'
import { EmptyState } from '../EmptyState'

interface SectionCardProps {
  title: string
  subtitle?: string
  description?: string
  children: React.ReactNode
  dirty?: boolean
  saving?: boolean
  onSaveAll?: () => Promise<void> | void
  onResetAll?: () => void
  isEmpty?: boolean
}

export function SectionCard({
  title,
  subtitle,
  description,
  children,
  dirty = false,
  saving = false,
  onSaveAll,
  onResetAll,
  isEmpty = false
}: SectionCardProps) {
  const handleSaveAll = () => {
    if (onSaveAll) {
      const result = onSaveAll()
      if (result instanceof Promise) {
        void result
      }
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            {subtitle && (
              <p className="text-sm text-gray-600 mt-1">{subtitle}</p>
            )}
            {description && (
              <p className="text-sm text-gray-500 mt-2">{description}</p>
            )}
          </div>

          {/* Section Actions */}
          {dirty && (onSaveAll || onResetAll) && (
            <div className="flex items-center space-x-2 ml-4">
              {onSaveAll && (
                <button
                  onClick={handleSaveAll}
                  disabled={saving}
                  className="btn-success flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green-500"
                  title={saving ? "Saving in progress..." : "Save all changes in this section"}
                >
                  <Save size={16} />
                  <span>{saving ? 'Saving...' : 'Save Section'}</span>
                </button>
              )}

              {onResetAll && (
                <button
                  onClick={onResetAll}
                  className="btn-ghost text-gray-600 hover:text-gray-800 flex items-center space-x-2 focus:outline-none focus:ring-2 focus:ring-gray-500"
                  title="Reset all changes in this section"
                >
                  <RotateCcw size={16} />
                  <span>Reset Section</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-4">
        {isEmpty ? (
          <EmptyState
            title="Nothing extracted here (yet)"
            description="You can still enter values manually—just fill the fields and hit Save."
            compact={true}
          />
        ) : (
          children
        )}
      </div>
    </div>
  )
}