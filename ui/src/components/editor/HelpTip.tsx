import React, { useState } from 'react'
import { HelpCircle } from 'lucide-react'

interface HelpTipProps {
  description: string
}

export function HelpTip({ description }: HelpTipProps) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className="relative inline-block ml-1">
      <button
        type="button"
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        className="text-gray-400 hover:text-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-full"
        aria-label={`Help: ${description}`}
      >
        <HelpCircle size={14} />
      </button>

      {isVisible && (
        <div className="absolute z-10 bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64">
          <div className="bg-gray-900 text-white text-xs rounded px-3 py-2 shadow-lg">
            {description}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900" />
          </div>
        </div>
      )}
    </div>
  )
}