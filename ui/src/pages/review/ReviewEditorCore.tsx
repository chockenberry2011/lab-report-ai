import { useParams } from 'react-router-dom'
import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { parseResultRoute } from '@/lib/routeParsing'
import { useCorrections } from '@/hooks/useCorrections'
import { SECTION_ORDER, fieldsForSection } from '@/config/fieldSchema'
import { FALLBACK_SECTIONS, FALLBACK_FIELDS } from '@/config/fallbackSchema'
import { SectionCard } from '@/components/editor/SectionCard'
import { FieldRow } from '@/components/editor/FieldRow'
import { SectionNav } from '@/components/editor'
import { ServerUpdatePill } from '@/components/ServerUpdatePill'
import { PanelsEditor } from '@/components/PanelsEditor'
import { AppLayout } from '@/components/layout/AppLayout'
import { ReviewLayout } from '@/components/review/ReviewLayout'
import { UnifiedNavigation } from '@/components/review/UnifiedNavigation'
import { useLayoutMode, useAutoLayoutMode } from '@/hooks/useLayoutMode'
import { fetchWithError } from '@/lib/api-helpers'
import { resultsApi } from '@/services/api'
import { sectionTitleFromKey, sectionSubtitleFromKey, sectionDescFromKey, widthToCols } from '@/lib/section-helpers'
import { Save, Layout, Focus, Eye } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { loadCorrectionsFieldSchema } from '@/lib/correctionsSchema'
import { cn } from '@/utils'

type ExtractedText = string | null
type ResultData = any | null
type ApiState<T> = { loading: boolean; error?: string; data?: T }

function __probe<T>(name: string, fn: () => T): T {
  try { return fn() } catch (e) { console.warn(`[${name}]`, e); throw e }
}

export default function ReviewEditorCore() {
  const { resultId: rawIdParam = '' } = useParams()

  // Robustly parse route param
  const parsed = useMemo(() => __probe('parseResultRoute', () => parseResultRoute(rawIdParam)), [rawIdParam])
  const baseId = parsed.baseId
  const viewerId = useMemo(() => {
    if (!baseId) return ''
    const tokens = [baseId]
    if (parsed.stage) tokens.push(parsed.stage)
    const flags = Array.from(new Set(Array.from(parsed.flags)))
    if (flags.length) tokens.push(...flags)
    return tokens.join('.')
  }, [parsed, baseId])

  // Preflight fetch for extracted-text (non-blocking render) - use fullId for files
  const [extracted, setExtracted] = useState<ApiState<ExtractedText>>({ loading: true })
  const [devMode, setDevMode] = useState(false)
  const [devInfo, setDevInfo] = useState<any>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string,string>>({})

  // Layout mode management
  const { layoutMode, config, isTransitioning, changeLayoutMode, toggleFocusMode } = useLayoutMode()
  const { trackActivity } = useAutoLayoutMode(layoutMode, changeLayoutMode)

  // Force issue-driven defaults (no persistence)
  const [focusMode, setFocusMode] = useState<boolean>(true)
  const [filterNeedsReview, setFilterNeedsReview] = useState<boolean>(true)
  const initialStoredTabFlag = (() => {
    try { return localStorage.getItem('labai.review.activeTab') != null } catch { return false }
  })()
  const hadStoredTab = useRef<boolean>(initialStoredTabFlag)
  const [activeTab, setActiveTab] = useState<'headers' | 'panels'>(() => {
    try {
      const v = localStorage.getItem('labai.review.activeTab')
      return v === 'panels' ? 'panels' : 'headers'
    } catch { return 'headers' }
  })
  const autoTabbedRef = useRef(false)

  useEffect(() => {
    try { localStorage.setItem('labai.review.activeTab', activeTab) } catch {}
  }, [activeTab])

  useEffect(() => {
    const handler = (e: any) => {
      setDevInfo(e.detail)
    }
    window.addEventListener('corrections:dev-update', handler)
    return () => window.removeEventListener('corrections:dev-update', handler)
  }, [])

  // Not persisting UI state; defaults ensure an unmistakable issues-only view

  useEffect(() => {
    const handler = (e: any) => {
      const { path, error } = e.detail || {}
      if (!path || !error) return
      setFieldErrors(prev => ({ ...prev, [path]: error }))
    }
    window.addEventListener('field:error', handler)
    return () => window.removeEventListener('field:error', handler)
  }, [])

  useEffect(() => {
    // Load corrections field schema on boot for client-side canonicalization
    loadCorrectionsFieldSchema().catch(() => {})
    let alive = true
    setExtracted({ loading: true })

    const tryFetchExtractedText = async () => {
      try {
        // First try with constructed viewer-style id (deduped)
        const firstId = viewerId || baseId
        const text = await fetchWithError(`/api/files/${encodeURIComponent(firstId)}/extracted-text`)
        if (alive) setExtracted({ loading: false, data: text || null })
      } catch (error) {
        // If no stage, fallback to compose.debug
        if (!parsed.stage && baseId) {
          try {
            const fallbackId = `${baseId}.03_compose.debug`
            const text = await fetchWithError(`/api/files/${encodeURIComponent(fallbackId)}/extracted-text`)
            if (alive) setExtracted({ loading: false, data: text || null })
          } catch (fallbackError) {
            if (alive) setExtracted({ loading: false, error: String(fallbackError) })
          }
        } else {
          if (alive) setExtracted({ loading: false, error: String(error) })
        }
      }
    }

    tryFetchExtractedText()
    return () => { alive = false }
  }, [viewerId, baseId, parsed.stage])

  // Hook for corrections data with dynamic base ID (new simplified API)
  const { drafts, serverCorrections, updateDraft, saveChanges } = useCorrections(baseId)
  const serverState = serverCorrections
  const serverUpdates: Array<{ field: string; newValue: any; oldValue: any }> = []

  // Fetch structured result data for panels/test rows and header context
  const [resultData, setResultData] = useState<ApiState<ResultData>>({ loading: true })
  useEffect(() => {
    let alive = true
    setResultData({ loading: true })
    resultsApi.getResult(baseId)
      .then((data) => { if (alive) setResultData({ loading: false, data }) })
      .catch((err) => { if (alive) setResultData({ loading: false, error: String(err), data: null }) })
    return () => { alive = false }
  }, [baseId])

  // Compute panels/tests counts eagerly to keep hooks order stable
  const job = resultData.data ?? null
  const labPanels = (job as any)?.lab_panels ?? []
  const panelsCount = Array.isArray(labPanels) ? labPanels.length : 0
  const testsCount = Array.isArray(labPanels)
    ? labPanels.reduce((acc: number, p: any) => acc + (Array.isArray(p?.test_rows) ? p.test_rows.length : 0), 0)
    : 0

  // Navigation collapse (persisted)
  const [navCollapsed, setNavCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem('labai.review.navCollapsed') === 'true' } catch { return false }
  })
  useEffect(() => { try { localStorage.setItem('labai.review.navCollapsed', String(navCollapsed)) } catch {} }, [navCollapsed])

  // Auto-switch to Panels tab once if panels exist (run every render; safe when counts are 0)
  useEffect(() => {
    if (!autoTabbedRef.current && panelsCount > 0 && activeTab === 'headers' && !hadStoredTab.current) {
      setActiveTab('panels')
      autoTabbedRef.current = true
    }
  }, [panelsCount, activeTab])

  const hasAnyServerData = Object.keys(serverState).length > 0
  const hasAnyDirtyFields = Object.keys(drafts).length > 0

  // Defensive guards so the page never blanks
  const [showMeta, setShowMeta] = useState(false)
  // PDF viewer state based on layout mode
  const enablePdfViewer = config.showPdfPanel
  const [focusedFieldPath, setFocusedFieldPath] = useState<string | null>(null)

  // Field actions that work directly with useCorrections
  const handleFieldChange = useCallback((path: string, value: any) => {
    updateDraft(path, value)
  }, [updateDraft])

  const handleFieldSave = useCallback(async (path: string) => {
    try {
      await saveChanges([path])
      toast.success('Field saved')
    } catch (error) {
      toast.error(`Save failed: ${error}`)
    }
  }, [saveChanges])

  const handleFieldReset = useCallback((path: string) => {
    const original = serverState[path]?.value ?? ''
    updateDraft(path, original)
  }, [serverState, updateDraft])

  const handleSaveAll = useCallback(async () => {
    const allDrafts = Object.keys(drafts)
    if (allDrafts.length === 0) return

    try {
      await saveChanges(allDrafts)
      toast.success(`Saved ${allDrafts.length} changes`)
    } catch (error) {
      toast.error(`Save failed: ${error}`)
    }
  }, [saveChanges, drafts])

  // Schema loading and UI logic
  const [activeSectionKey, setActiveSectionKey] = useState<string>('')
  const [issueCursor, setIssueCursor] = useState<number>(0)

  // Build sections from configured field schema; fallback to minimal schema if needed
  const { sections, usingFallback } = useMemo(() => {
    try {
      const mapped = SECTION_ORDER.map(key => {
        const defs = fieldsForSection(key).map(d => ({
          path: d.path,
          label: d.label,
          width: d.width || 'full',
          input: d.input,
          required: d.required,
          source: undefined as any,
          confidence: undefined as any,
        }))
        return { key, title: sectionTitleFromKey(key), defs }
      })
      const hasAny = mapped.some(s => s.defs.length > 0)
      if (hasAny) return { sections: mapped, usingFallback: false }
    } catch {}
    // Fallback minimal sections
    const fbSections = FALLBACK_SECTIONS.map(s => ({
      key: s.key,
      title: s.title,
      defs: (s.fields || []).map(fp => FALLBACK_FIELDS[fp]).filter(Boolean),
    }))
    return { sections: fbSections, usingFallback: true }
  }, [])

  const getDraftValue = useCallback((path: string) => {
    return drafts[path] !== undefined ? drafts[path] : (serverState[path]?.value ?? '')
  }, [drafts, serverState])

  const isDraftDirty = useCallback((path: string) => {
    return drafts[path] !== undefined && drafts[path] !== (serverState[path]?.value ?? '')
  }, [drafts, serverState])

  const sectionMeta = useMemo(() => {
    return sections.map(s => {
      const sectionDefs = s.defs || []
      const dirty = sectionDefs.some((d:any) => isDraftDirty(d.path))
      const issues = sectionDefs
        .filter((d:any) => {
          const serverValue = serverState[d.path]?.value ?? ''
          const draftValue = getDraftValue(d.path)
          const val = (draftValue ?? serverValue)
          const empty = val === null || val === undefined || String(val).trim() === ''
          return empty
        })
        .map((d:any) => d.path)
      const defs = sectionDefs.map((d:any) => ({
        ...d,
        source: d.source,
        confidence: d.confidence
      }))
      const title = sectionTitleFromKey(s.key)
      return { key: s.key, title, dirty, issues, defs }
    })
  }, [sections, serverState, getDraftValue, isDraftDirty])

  const issueList = useMemo(() => sectionMeta.flatMap(m => m.issues), [sectionMeta])

  // Enhanced navigation items with labels and metadata
  const navigationItems = useMemo(() => {
    return sectionMeta.flatMap(section =>
      section.defs
        .filter(def => {
          if (!filterNeedsReview) return true
          const serverValue = serverState[def.path]?.value ?? ''
          const draftValue = getDraftValue(def.path)
          const val = (draftValue ?? serverValue)
          const empty = val === null || val === undefined || String(val).trim() === ''
          return empty
        })
        .map(def => {
          const serverValue = serverState[def.path]?.value ?? ''
          const draftValue = getDraftValue(def.path)
          const val = (draftValue ?? serverValue)
          const empty = val === null || val === undefined || String(val).trim() === ''
          const isDirty = isDraftDirty(def.path)

          return {
            path: def.path,
            label: def.label || def.path.split('.').pop() || def.path,
            type: empty ? 'issue' : isDirty ? 'warning' : 'completed' as 'issue' | 'warning' | 'completed',
            page: def.source?.page,
            line: def.source?.line
          }
        })
    )
  }, [sectionMeta, serverState, getDraftValue, isDraftDirty, filterNeedsReview])

  // Set first active section with issues on mount/when computed
  useEffect(() => {
    if (!activeSectionKey) {
      const firstWithIssues = sectionMeta.find(m => m.issues.length > 0)
      if (firstWithIssues) setActiveSectionKey(firstWithIssues.key)
    }
  }, [sectionMeta, activeSectionKey])

  useEffect(() => { if (issueCursor >= issueList.length) setIssueCursor(0) }, [issueList.length])

  // Navigation helpers: focus a field and move between issues
  const focusFieldByPath = useCallback((path: string) => {
    try {
      const el = document.querySelector(`[data-field-path="${path}"] input, [data-field-path="${path}"] textarea, [data-field-path="${path}"] select`) as HTMLElement | null
      if (el) { el.focus({ preventScroll: false }); (el as any).scrollIntoView?.({ behavior:'smooth', block:'center' }) }
    } catch {}
  }, [])

  const gotoIssue = useCallback((dir: 1 | -1) => {
    if (!issueList.length) return
    const next = (issueCursor + dir + issueList.length) % issueList.length
    setIssueCursor(next)
    focusFieldByPath(issueList[next])
  }, [issueCursor, issueList, focusFieldByPath])

  // Enhanced navigation for floating widget
  const handleNavigateToItem = useCallback((index: number) => {
    if (index >= 0 && index < navigationItems.length) {
      const item = navigationItems[index]
      focusFieldByPath(item.path)
      // Update issue cursor if it's an issue
      const issueIndex = issueList.findIndex(path => path === item.path)
      if (issueIndex >= 0) {
        setIssueCursor(issueIndex)
      }
    }
  }, [navigationItems, issueList, focusFieldByPath])

  // Current navigation index based on issue cursor
  const currentNavigationIndex = useMemo(() => {
    if (issueCursor >= 0 && issueCursor < issueList.length) {
      const currentIssuePath = issueList[issueCursor]
      return navigationItems.findIndex(item => item.path === currentIssuePath)
    }
    return 0
  }, [issueCursor, issueList, navigationItems])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault()
        gotoIssue(1)
      } else if (e.key === 'p' || e.key === 'P') {
        e.preventDefault()
        gotoIssue(-1)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [gotoIssue])

  // Early returns for loading and error states
  if (!baseId) {
    return (
      <div className="p-4">
        <div className="text-red-600">Error: Unable to parse result ID from URL: {rawIdParam}</div>
      </div>
    )
  }

  if (resultData.loading && !hasAnyServerData) {
    return (
      <div className="p-4">
        <div className="text-sm text-gray-600">Loading result data...</div>
      </div>
    )
  }

  if (!resultData.loading && !resultData.data && !hasAnyServerData) {
    return (
      <div className="p-4">
        <div className="space-y-2">
          {extracted.error && (
            <pre className="bg-red-50 p-3 rounded text-sm">{extracted.error}</pre>
          )}
          {resultData.error && (
            <pre className="bg-red-50 p-3 rounded text-sm">{resultData.error}</pre>
          )}
        </div>
      </div>
    )
  }

  if (!resultData.loading && !job) {
    return <div className="p-3 text-sm text-amber-600">Loading editor…</div>;
  }

  const totalFields = sectionMeta.reduce((acc, section) => acc + section.defs.length, 0)
  const completedFields = sectionMeta.reduce((acc, section) =>
    acc + section.defs.filter(def => {
      const serverValue = serverState[def.path]?.value ?? ''
      const draftValue = getDraftValue(def.path)
      const val = (draftValue ?? serverValue)
      return val !== null && val !== undefined && String(val).trim() !== ''
    }).length, 0
  )

  // Navigation component
  const navigationComponent = config.showNavigation ? (
    <UnifiedNavigation
      sections={sectionMeta.map(m => ({ key: m.key, title: m.title, dirty: m.dirty }))}
      activeSection={activeSectionKey}
      onSectionSelect={setActiveSectionKey}
      issues={navigationItems}
      currentIssueIndex={currentNavigationIndex}
      onNavigateIssue={handleNavigateToItem}
      onFocusField={focusFieldByPath}
      layoutMode={layoutMode}
      onLayoutModeChange={changeLayoutMode}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      panelsCount={panelsCount}
      testsCount={testsCount}
      totalFields={totalFields}
      completedFields={completedFields}
      collapsed={navCollapsed}
      onCollapseChange={setNavCollapsed}
    />
  ) : null

  // Header component
  const headerComponent = (
    <div className="px-4 py-2">
      {/* Status Messages */}
      {(!baseId || parsed.raw !== baseId || usingFallback) && (
        <div className="mb-3 space-y-2">
          {!baseId && (
            <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
              <span className="font-medium">Invalid ID:</span> <code>{rawIdParam}</code>
            </div>
          )}
          {parsed.raw !== baseId && (
            <div className="p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
              <span className="font-medium">File variant:</span> <code>{viewerId || baseId}</code>
            </div>
          )}
          {usingFallback && (
            <div className="p-2 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
              <span className="font-medium">Notice:</span> Using minimal field schema
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Open Navigation button (when collapsed) */}
          {config.showNavigation && navCollapsed && (
            <button
              onClick={() => setNavCollapsed(false)}
              className="bg-white border border-gray-200 rounded-md p-2 shadow-sm hover:shadow-md transition-all hover:bg-gray-50"
              title="Open Navigation"
              aria-label="Open Navigation"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-gray-600" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 111.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"/></svg>
            </button>
          )}

          <h1 className="text-lg font-semibold">Review & Edit</h1>
          <code className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">{baseId}</code>

          {/* Layout mode indicators */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggleFocusMode}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded text-xs transition-all",
                layoutMode === 'focus'
                  ? "bg-purple-100 text-purple-700"
                  : "text-gray-600 hover:bg-gray-100"
              )}
              title="Toggle Focus Mode (Cmd+Shift+F)"
            >
              <Focus size={12} />
              <span>Focus</span>
            </button>

            {layoutMode !== 'focus' && (
              <button
                onClick={() => changeLayoutMode(layoutMode === 'reference' ? 'navigation' : 'reference')}
                className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded text-xs transition-all",
                  layoutMode === 'reference'
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100"
                )}
                title="Toggle Reference Mode (Cmd+Shift+R)"
              >
                <Eye size={12} />
                <span>PDF</span>
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Progress indicator */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>{completedFields}/{totalFields}</span>
            <div className="w-16 bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-green-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${(completedFields / totalFields) * 100}%` }}
              />
            </div>
          </div>

          {/* Issues counter */}
          {issueList.length > 0 && (
            <div className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-200">
              {issueList.length} issues
            </div>
          )}

          {/* Save button */}
          {hasAnyDirtyFields && (
            <button
              onClick={handleSaveAll}
              className="inline-flex items-center px-3 py-1.5 border border-transparent rounded text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 transition-all"
            >
              <Save className="h-3 w-3 mr-1" />
              Save
            </button>
          )}

          {/* Settings toggle */}
          <label className="flex items-center gap-1 text-xs text-gray-600">
            <input type="checkbox" checked={showMeta} onChange={e=>setShowMeta(e.target.checked)} />
            <span>Meta</span>
          </label>
        </div>
      </div>
    </div>
  )

  // Form content component
  const formContent = (
    <>
      {devMode && (
        <div className="mb-4 p-3 bg-gray-50 border rounded">
          <div className="text-xs text-gray-700 font-mono">
            <div className="font-semibold mb-1">Corrections Dev Preview</div>
            <pre className="whitespace-pre-wrap break-all">{JSON.stringify(devInfo, null, 2)}</pre>
          </div>
        </div>
      )}

      {/* Content filters (minimal, non-sticky) */}
      {!config.enableFocusMode && (
        <div className="flex items-center justify-end gap-4 mb-6 pb-4 border-b border-gray-200">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={filterNeedsReview} onChange={e=>setFilterNeedsReview(e.target.checked)} />
            Only show issues
          </label>
        </div>
      )}

      {/* Sections A–E - Clean Layout */}
      <div className="space-y-8">
        {sections.map(({key, defs, title}) => {
          if (!defs?.length) {
            return (
              <SectionCard key={key} title={title || `Section ${key}`} subtitle="" description="">
                <div className="text-sm text-gray-500">Nothing to show here yet. You can still add values manually.</div>
              </SectionCard>
            )
          }
          const dirty = defs.some((d: any) => isDraftDirty(d.path))
          const isActiveSection = activeSectionKey === key
          const showSection = !config.enableFocusMode || isActiveSection || activeSectionKey === ''

          if (!showSection) return null

          return (
            <SectionCard
              key={key}
              {...{ id: `section-${key}` }}
              title={title || sectionTitleFromKey(key)}
              subtitle={sectionSubtitleFromKey(key)}
              description={sectionDescFromKey(key)}
              dirty={dirty}
              onSaveAll={() => {
                const dirtyPaths = (defs as any[]).filter(d => isDraftDirty(d.path)).map(d => d.path)
                if (dirtyPaths.length > 0) {
                  saveChanges(dirtyPaths)
                }
              }}
              onResetAll={() => {
                (defs as any[]).forEach(d => handleFieldReset(d.path))
              }}
            >
              <div className="grid grid-cols-12 gap-4">
                {defs.filter((def: any) => {
                  if (!filterNeedsReview) return true
                  const serverValue = serverState[def.path]?.value ?? ''
                  const draftValue = getDraftValue(def.path)
                  const val = (draftValue ?? serverValue)
                  const empty = val === null || val === undefined || String(val).trim() === ''
                  return empty
                }).map((def: any) => {
                  const serverValue = serverState[def.path]?.value ?? ''
                  const draftValue = getDraftValue(def.path)
                  const safeUpdates = Array.isArray(serverUpdates) ? serverUpdates : []
                  const fieldUpdate = safeUpdates.find((u: any) => u.field === def.path)
                  const isActiveField = focusedFieldPath === def.path

                  return (
                    <div
                      key={def.path}
                      className={widthToCols(def.width)}
                      data-field-path={def.path}
                      onMouseEnter={() => setActiveSectionKey(key)}
                      onFocus={() => {
                        setFocusedFieldPath(def.path)
                        trackActivity('form')
                      }}
                    >
                      <div className="space-y-2">
                        <FieldRow
                          def={def}
                          value={serverValue}
                          draft={draftValue}
                          error={fieldErrors[def.path]}
                          saving={false}
                          saved={false}
                          onChange={(v) => handleFieldChange(def.path, v)}
                          onSave={() => handleFieldSave(def.path)}
                          onReset={() => handleFieldReset(def.path)}
                          source={showMeta ? def.source : undefined}
                          confidence={showMeta ? def.confidence : undefined}
                          focusMode={config.enableFocusMode}
                          isActiveField={isActiveField}
                        />

                        {fieldUpdate && (
                          <ServerUpdatePill
                            update={fieldUpdate}
                            onApply={() => handleFieldChange(def.path, fieldUpdate.value)}
                            onDismiss={() => {}}
                          />
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </SectionCard>
          )
        })}
      </div>

      {/* Panels & Tests - Only show in panels tab */}
      {activeTab === 'panels' && (
        <div className="mt-12 pt-8 border-t border-gray-200">
          {labPanels.length > 0 ? (
            <PanelsEditor
              panels={labPanels}
              baseId={baseId}
            />
          ) : (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
              <h2 className="text-xl font-semibold mb-3">Panels & Tests</h2>
              <p className="text-gray-600">
                {resultData.loading
                  ? 'Loading panels and tests...'
                  : resultData.error
                  ? 'Error loading panels and tests'
                  : 'No panels found in this result'
                }
              </p>
            </div>
          )}
        </div>
      )}

      {/* Bottom padding for comfortable scrolling */}
      <div className="h-32"></div>
    </>
  )

  return (
    <AppLayout
      navigation={navigationComponent}
      header={headerComponent}
      showNavigation={config.showNavigation && !navCollapsed}
    >
      {enablePdfViewer ? (
        <ReviewLayout
          jobId={baseId}
          resultData={resultData.data}
          formContent={formContent}
          onFieldFocus={(fieldPath) => {
            setFocusedFieldPath(fieldPath)
            trackActivity('form')
          }}
          defaultPdfWidth={60}
          showPdf={config.showPdfPanel}
          className="h-full"
        />
      ) : (
        <div className="h-full overflow-y-auto p-6">
          {formContent}
        </div>
      )}
    </AppLayout>
  )
}
