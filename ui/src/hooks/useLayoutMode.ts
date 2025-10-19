import { useState, useCallback, useEffect } from 'react'

export type LayoutMode = 'focus' | 'reference' | 'navigation'

interface LayoutModeConfig {
  showPdfPanel: boolean
  showNavigation: boolean
  autoCollapsePdf: boolean
  navigationCollapsed: boolean
  enableFocusMode: boolean
}

const LAYOUT_CONFIGS: Record<LayoutMode, LayoutModeConfig> = {
  focus: {
    showPdfPanel: false,
    showNavigation: false,
    autoCollapsePdf: true,
    navigationCollapsed: true,
    enableFocusMode: true
  },
  reference: {
    showPdfPanel: true,
    showNavigation: false,
    autoCollapsePdf: false,
    navigationCollapsed: true,
    enableFocusMode: false
  },
  navigation: {
    showPdfPanel: true,
    showNavigation: true,
    autoCollapsePdf: false,
    navigationCollapsed: false,
    enableFocusMode: false
  }
}

export function useLayoutMode() {
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => {
    const saved = localStorage.getItem('lab-ai-layout-mode')
    return (saved as LayoutMode) || 'navigation'
  })

  const [isTransitioning, setIsTransitioning] = useState(false)

  // Save mode to localStorage
  useEffect(() => {
    localStorage.setItem('lab-ai-layout-mode', layoutMode)
  }, [layoutMode])

  const changeLayoutMode = useCallback((newMode: LayoutMode) => {
    if (newMode === layoutMode) return

    setIsTransitioning(true)
    setLayoutMode(newMode)

    // Reset transition state after animation
    setTimeout(() => setIsTransitioning(false), 300)
  }, [layoutMode])

  const toggleFocusMode = useCallback(() => {
    changeLayoutMode(layoutMode === 'focus' ? 'navigation' : 'focus')
  }, [layoutMode, changeLayoutMode])

  const config = LAYOUT_CONFIGS[layoutMode]

  return {
    layoutMode,
    config,
    isTransitioning,
    changeLayoutMode,
    toggleFocusMode
  }
}

// Hook for detecting user activity to auto-switch modes
export function useAutoLayoutMode(
  layoutMode: LayoutMode,
  changeLayoutMode: (mode: LayoutMode) => void
) {
  const [lastActivity, setLastActivity] = useState<'pdf' | 'form' | null>(null)
  const [activityTimeout, setActivityTimeout] = useState<NodeJS.Timeout | null>(null)

  const trackActivity = useCallback((type: 'pdf' | 'form') => {
    setLastActivity(type)

    // Clear existing timeout
    if (activityTimeout) {
      clearTimeout(activityTimeout)
    }

    // Auto-switch to reference mode when user clicks PDF
    if (type === 'pdf' && layoutMode === 'focus') {
      changeLayoutMode('reference')
    }

    // Auto-switch to focus mode after typing in form for 2 seconds
    if (type === 'form' && layoutMode === 'reference') {
      const timeout = setTimeout(() => {
        changeLayoutMode('focus')
      }, 2000)
      setActivityTimeout(timeout)
    }
  }, [layoutMode, changeLayoutMode, activityTimeout])

  // Clean up timeout
  useEffect(() => {
    return () => {
      if (activityTimeout) {
        clearTimeout(activityTimeout)
      }
    }
  }, [activityTimeout])

  return { trackActivity, lastActivity }
}