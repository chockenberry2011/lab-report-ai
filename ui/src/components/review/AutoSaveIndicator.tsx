import React, { useState, useEffect } from 'react'
import { Check, Save, Loader2, AlertCircle } from 'lucide-react'
import { cn } from '@/utils'

interface AutoSaveIndicatorProps {
  status: 'idle' | 'saving' | 'saved' | 'error'
  lastSaved?: Date
  error?: string
  className?: string
}

export function AutoSaveIndicator({
  status,
  lastSaved,
  error,
  className = ''
}: AutoSaveIndicatorProps) {
  const [showSaved, setShowSaved] = useState(false)

  useEffect(() => {
    if (status === 'saved') {
      setShowSaved(true)
      const timer = setTimeout(() => setShowSaved(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [status])

  const getStatusIcon = () => {
    switch (status) {
      case 'saving':
        return <Loader2 size={14} className="animate-spin text-blue-500" />
      case 'saved':
        return <Check size={14} className="text-green-500" />
      case 'error':
        return <AlertCircle size={14} className="text-red-500" />
      default:
        return <Save size={14} className="text-gray-400" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'saving':
        return 'Saving...'
      case 'saved':
        return 'Saved'
      case 'error':
        return 'Save failed'
      default:
        return 'Auto-save'
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'saving':
        return 'text-blue-600 bg-blue-50'
      case 'saved':
        return 'text-green-600 bg-green-50'
      case 'error':
        return 'text-red-600 bg-red-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs transition-all duration-200',
        getStatusColor(),
        showSaved && 'scale-110'
      )}>
        {getStatusIcon()}
        <span className="font-medium">{getStatusText()}</span>
      </div>

      {lastSaved && status !== 'saving' && (
        <span className="text-xs text-gray-500">
          {new Date(lastSaved).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          })}
        </span>
      )}

      {error && status === 'error' && (
        <div className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded border border-red-200">
          {error}
        </div>
      )}
    </div>
  )
}

// Hook for managing auto-save state
export function useAutoSave() {
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [lastSaved, setLastSaved] = useState<Date | undefined>()
  const [error, setError] = useState<string | undefined>()

  const save = async (saveFunction: () => Promise<void>) => {
    try {
      setStatus('saving')
      setError(undefined)
      await saveFunction()
      setStatus('saved')
      setLastSaved(new Date())
    } catch (err) {
      setStatus('error')
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  const reset = () => {
    setStatus('idle')
    setError(undefined)
  }

  return {
    status,
    lastSaved,
    error,
    save,
    reset
  }
}