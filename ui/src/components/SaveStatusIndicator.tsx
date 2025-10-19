import React from 'react'
import { Check, AlertCircle, Loader2 } from 'lucide-react'
import type { SaveStatus } from '@/types/review-fields'
import { cn } from '@/utils'

interface SaveStatusIndicatorProps {
  status: SaveStatus
  className?: string
}

export function SaveStatusIndicator({ status, className }: SaveStatusIndicatorProps) {
  if (status === 'idle') {
    return null
  }

  const getStatusDisplay = () => {
    switch (status) {
      case 'saving':
        return {
          icon: <Loader2 size={16} className="animate-spin" />,
          text: 'Saving...',
          className: 'text-blue-600 bg-blue-50 border-blue-200'
        }
      case 'saved':
        return {
          icon: <Check size={16} />,
          text: 'Saved',
          className: 'text-green-600 bg-green-50 border-green-200'
        }
      case 'error':
        return {
          icon: <AlertCircle size={16} />,
          text: 'Save failed',
          className: 'text-red-600 bg-red-50 border-red-200'
        }
      default:
        return null
    }
  }

  const statusDisplay = getStatusDisplay()
  if (!statusDisplay) return null

  return (
    <div className={cn(
      'inline-flex items-center gap-2 px-3 py-1.5 rounded-md border text-sm font-medium transition-all',
      statusDisplay.className,
      className
    )}>
      {statusDisplay.icon}
      {statusDisplay.text}
    </div>
  )
}