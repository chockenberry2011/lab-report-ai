import { AlertCircle, Eye, X } from 'lucide-react'
import type { ServerUpdateInfo } from '@/hooks/useDraftState'

interface ServerUpdatePillProps {
  update: ServerUpdateInfo
  onCommit: () => void
  onDismiss: () => void
}

export function ServerUpdatePill({ update, onCommit, onDismiss }: ServerUpdatePillProps) {
  return (
    <div className="flex items-center gap-2 px-2 py-1 bg-blue-50 border border-blue-200 rounded-full text-xs">
      <AlertCircle size={12} className="text-blue-600" />
      <span className="text-blue-700 font-medium">Server updated</span>

      <button
        onClick={onCommit}
        className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 hover:bg-blue-200 rounded text-blue-700 font-medium transition-colors"
        title="Review and apply server changes"
      >
        <Eye size={10} />
        Review changes
      </button>

      <button
        onClick={onDismiss}
        className="p-0.5 hover:bg-blue-200 rounded text-blue-600 transition-colors"
        title="Dismiss notification"
      >
        <X size={10} />
      </button>
    </div>
  )
}