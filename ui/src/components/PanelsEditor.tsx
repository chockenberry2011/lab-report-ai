import { useState, useCallback, useMemo, useEffect, memo } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Plus,
  Save,
  RotateCcw,
  Trash2,
  AlertTriangle
} from 'lucide-react'
import { useCorrections } from '@/hooks/useCorrections'
import { cn } from '@/utils'
import { toast } from 'react-hot-toast'

// Local types for type safety
interface Panel {
  id?: string
  name?: string
  panel_type?: string
  test_count?: number
  needs_review?: boolean
  panel_score?: number
  started_at_page?: number
  started_at_line?: number
  test_rows?: TestRow[]
}

interface TestRow {
  id?: string
  test_name?: string
  result_value?: string
  units?: string
  flag?: string
  reference_range_text?: string
  reference_range_low?: number | string
  reference_range_high?: number | string
  line_number?: number
  [key: string]: any
}

interface Props {
  panels: Panel[]
  baseId: string
}

const FLAG_OPTIONS = ['', 'H', 'L', 'CRIT', 'ABN'] as const

function PanelsEditorComponent({ panels = [], baseId }: Props) {
  const [expandedPanels, setExpandedPanels] = useState<Set<number>>(new Set([0]))
  const [savingRows, setSavingRows] = useState<Set<string>>(new Set())
  const [savedRows, setSavedRows] = useState<Set<string>>(new Set())
  // Defaults with persistence: issues-only OFF, auto-collapse clean ON
  const [onlyIssues, setOnlyIssues] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('labai.panels.onlyIssues')
      return v === null ? false : v === 'true'
    } catch { return false }
  })
  const [autoCollapseClean, setAutoCollapseClean] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('labai.panels.autoCollapseClean')
      return v === null ? true : v === 'true'
    } catch { return true }
  })
  useEffect(() => { try { localStorage.setItem('labai.panels.onlyIssues', String(onlyIssues)) } catch {} }, [onlyIssues])
  useEffect(() => { try { localStorage.setItem('labai.panels.autoCollapseClean', String(autoCollapseClean)) } catch {} }, [autoCollapseClean])

  const { drafts, updateDraft, saveChanges } = useCorrections(baseId)

  // Optional ordering: needs-review first (persisted)
  const [sortNeedsFirst, setSortNeedsFirst] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('labai.panels.sortNeedsFirst')
      return v === null ? true : v === 'true'
    } catch { return true }
  })
  useEffect(() => { try { localStorage.setItem('labai.panels.sortNeedsFirst', String(sortNeedsFirst)) } catch {} }, [sortNeedsFirst])

  // Field names aligned with backend serializer
  const TEST_FIELDS = useMemo(() => (
    [
      'test_name',
      'result_value',
      'units',
      'flag',
      'reference_range_text',
    ] as const
  ), [])

  type TestField = typeof TEST_FIELDS[number]

  const buildKey = useCallback((panelIndex: number, testIndex: number, field: TestField) => {
    return `lab_panels.${panelIndex}.test_rows.${testIndex}.${field}`
  }, [])

  const getBaseValue = useCallback((panelIndex: number, testIndex: number, field: TestField) => {
    const row: any = panels?.[panelIndex]?.test_rows?.[testIndex]
    if (!row) return ''

    // Direct hit
    let val = row?.[field]
    if (val !== undefined && val !== null && String(val) !== '') return val

    // Fallbacks for common alternate shapes
    const alt = (f: string) => row?.[f]
    switch (field) {
      case 'test_name':
        val = alt('name') ?? alt('test') ?? alt('testName') ?? alt('label')
        break
      case 'result_value':
        val = alt('value') ?? alt('result') ?? alt('resultValue')
        break
      case 'units':
        val = alt('unit') ?? alt('uom')
        break
      case 'flag':
        val = alt('flag_norm') ?? alt('abnormal_flag')
        break
      case 'reference_range_text': {
        const rr = alt('reference_range')
        val = alt('reference') ?? alt('ref_range') ?? (typeof rr === 'object' ? rr?.text : rr)
        break
      }
    }
    return val ?? ''
  }, [panels])

  const getValue = useCallback((panelIndex: number, testIndex: number, field: TestField) => {
    const key = buildKey(panelIndex, testIndex, field)
    const draft = drafts[key]
    if (draft !== undefined && draft !== null && String(draft) !== '') return draft
    return getBaseValue(panelIndex, testIndex, field)
  }, [buildKey, drafts, getBaseValue])

  // UI debug-only: derive first test name without invoking helpers (to avoid any edge scoping issues)
  const uiDebugFirstTestName = useMemo(() => {
    try {
      const row: any = panels?.[0]?.test_rows?.[0]
      return (
        row?.test_name ?? row?.name ?? row?.test ?? row?.label ?? ''
      )
    } catch {
      return ''
    }
  }, [panels])

  // Memoized handlers to prevent child component rerenders
  const togglePanel = useCallback((panelIndex: number) => {
    setExpandedPanels(prev => {
      const next = new Set(prev)
      if (next.has(panelIndex)) {
        next.delete(panelIndex)
      } else {
        next.add(panelIndex)
      }
      return next
    })
  }, [])

  const handleFieldChange = useCallback((panelIndex: number, testIndex: number, field: TestField, value: string) => {
    updateDraft(buildKey(panelIndex, testIndex, field), value || '')
  }, [updateDraft, buildKey])

  const getModifiedKeysForRow = (panelIndex: number, testIndex: number): string[] => {
    const changed: string[] = []
    for (const field of TEST_FIELDS) {
      const key = buildKey(panelIndex, testIndex, field)
      const draft = drafts[key]
      if (draft !== undefined && draft !== null) {
        const baseVal = getBaseValue(panelIndex, testIndex, field)
        const d = String(draft).trim()
        const b = String(baseVal ?? '').trim()
        if (d.localeCompare(b, undefined, { sensitivity: 'accent' }) !== 0) {
          changed.push(key)
        }
      }
    }
    return changed
  }

  const saveRow = useCallback(async (panelIndex: number, testIndex: number) => {
    const rowKey = `${panelIndex}-${testIndex}`
    const modifiedKeys = getModifiedKeysForRow(panelIndex, testIndex)

    setSavingRows(prev => new Set(prev).add(rowKey))
    setSavedRows(prev => {
      const next = new Set(prev)
      next.delete(rowKey)
      return next
    })

    try {
      await saveChanges(modifiedKeys)
      setSavedRows(prev => new Set(prev).add(rowKey))
      toast.success('Row saved successfully')

      // Clear saved indicator after 2 seconds
      setTimeout(() => {
        setSavedRows(prev => {
          const next = new Set(prev)
          next.delete(rowKey)
          return next
        })
      }, 2000)
    } catch (error) {
      console.error('Failed to save row:', error)
      toast.error('Failed to save row')
    } finally {
      setSavingRows(prev => {
        const next = new Set(prev)
        next.delete(rowKey)
        return next
      })
    }
  }, [saveChanges])

  const resetRow = useCallback(async (panelIndex: number, testIndex: number) => {
    const rowKey = `${panelIndex}-${testIndex}`
    const rowKeys = (TEST_FIELDS as readonly string[]).map(field => buildKey(panelIndex, testIndex, field as TestField))

    // Reset drafts to base values (no save; revert local changes)
    (TEST_FIELDS as readonly TestField[]).forEach(field => {
      const key = buildKey(panelIndex, testIndex, field)
      const baseVal = getBaseValue(panelIndex, testIndex, field)
      updateDraft(key, String(baseVal ?? ''))
    })
  }, [updateDraft, buildKey, getBaseValue])

  const deleteRow = useCallback(async (panelIndex: number, testIndex: number) => {
    if (!window.confirm('Are you sure you want to delete this test row?')) return

    const rowKey = `${panelIndex}-${testIndex}`
    const panel = panels[panelIndex] ?? {}
    if (!panel.test_rows) return

    setSavingRows(prev => new Set(prev).add(rowKey))

    try {
      // Remove from local state
      panel.test_rows.splice(testIndex, 1)

      // For now, we'll handle this as removing all fields for the test
      const testKeys = (TEST_FIELDS as readonly string[]).map(field => buildKey(panelIndex, testIndex, field as TestField))

      // Set all fields to empty/undefined to effectively remove the row
      testKeys.forEach(key => updateDraft(key, ''))
      await saveChanges(testKeys)

      toast.success('Test row deleted successfully')
    } catch (error) {
      console.error('Failed to delete row:', error)
      toast.error('Failed to delete row')
    } finally {
      setSavingRows(prev => {
        const next = new Set(prev)
        next.delete(rowKey)
        return next
      })
    }
  }, [panels, updateDraft, saveChanges])

  const addTest = async (panelIndex: number) => {
    const panel = panels[panelIndex] ?? {}
    if (!panel.test_rows) panel.test_rows = []

    const newTestIndex = panel.test_rows.length
    const newTestId = `new_${Date.now()}`

    const newTest: TestRow = {
      id: newTestId,
      test_name: '',
      result_value: '',
      units: '',
      flag: '',
      reference_range_text: '',
      line_number: 0
    }

    // Add to local state
    panel.test_rows.push(newTest)

    // Save the new test via corrections
    const newTestKeys = (TEST_FIELDS as readonly string[]).map(field => buildKey(panelIndex, newTestIndex, field as TestField))

    try {
      await saveChanges(newTestKeys)
      toast.success('Test added successfully')
    } catch (error) {
      console.error('Failed to add test:', error)
      toast.error('Failed to add test')
      // Remove from local state on failure
      panel.test_rows.pop()
    }
  }

  // Debug: peek at incoming data to verify shape
  useEffect(() => {
    try {
      const firstPanel = panels?.[0]
      const firstRow = firstPanel?.test_rows?.[0]
      // eslint-disable-next-line no-console
      console.log('[PanelsEditor] data preview', {
        baseId,
        panelCount: Array.isArray(panels) ? panels.length : 0,
        firstPanelKeys: firstPanel ? Object.keys(firstPanel) : [],
        firstRow,
      })
    } catch {}
  }, [panels, baseId])

  // Helper: determine if a test row likely needs review
  const rowNeedsReview = useCallback((row: TestRow): boolean => {
    if (!row) return true
    const empty = (v: any) => v === undefined || v === null || String(v).trim() === ''
    const abnormal = (() => {
      const f = String(row.flag || '').trim().toUpperCase()
      return ['H','HIGH','L','LOW','CRIT','ABN'].includes(f)
    })()
    return abnormal || empty(row.test_name) || empty(row.result_value) || empty(row.units) || empty(row.reference_range_text)
  }, [])

  // No persistence beyond localStorage flags above

  // Early return for empty state
  if (!panels || panels.length === 0) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">No panels found in this result</h3>
        <p className="text-gray-600">This result does not contain any lab panels or test data.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">Panels & Tests</h2>
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={onlyIssues} onChange={e=>setOnlyIssues(e.target.checked)} />
            Only issues
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={autoCollapseClean} onChange={e=>setAutoCollapseClean(e.target.checked)} />
            Auto-collapse clean panels
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={sortNeedsFirst} onChange={e=>setSortNeedsFirst(e.target.checked)} />
            Needs-review first
          </label>
          {(() => {
            try {
              const totalPanels = panels.length
              const totalTests = panels.reduce((acc, p) => acc + (Array.isArray(p?.test_rows) ? p!.test_rows!.length : 0), 0)
              const totalIssues = panels.reduce((acc, p) => acc + ((Array.isArray(p?.test_rows) ? p!.test_rows! : []).filter(r => rowNeedsReview(r as any)).length), 0)
              return (
                <div className="flex items-center gap-2 text-gray-600">
                  <span>{totalPanels} panel{totalPanels !== 1 ? 's' : ''}</span>
                  <span>•</span>
                  <span>{totalTests} test{totalTests !== 1 ? 's' : ''}</span>
                  {onlyIssues && (
                    <>
                      <span>•</span>
                      <span>{totalIssues} issue{totalIssues !== 1 ? 's' : ''}</span>
                    </>
                  )}
                </div>
              )
            } catch { return null }
          })()}
        </div>
      </div>
      {/* Debug marker to verify data binding in UI */}
      <div className="text-xs text-gray-500" data-debug="panels-first-test">
        First test: {String(uiDebugFirstTestName || '—')}
      </div>

      {/* Hint when Only issues filters out all rows */}
      {(() => {
        try {
          if (!onlyIssues) return null
          let count = 0
          for (const p of panels || []) {
            const rows = Array.isArray(p?.test_rows) ? p!.test_rows! : []
            for (const r of rows) {
              const needs = rowNeedsReview(r as any)
              if (needs) count++
            }
          }
          if (count === 0) {
            return (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded">
                All tests look complete. Uncheck "Only issues" to view all tests.
              </div>
            )
          }
        } catch {}
        return null
      })()}

      {/* Order panels so those with issues appear first */}
      {(sortNeedsFirst
        ? panels
            .map((panel, idx) => ({ panel, idx, issueCount: (Array.isArray(panel?.test_rows) ? panel!.test_rows! : []).filter(r => rowNeedsReview(r as any)).length }))
            .sort((a, b) => (b.issueCount > 0 ? 1 : 0) - (a.issueCount > 0 ? 1 : 0) || b.issueCount - a.issueCount || a.idx - b.idx)
        : panels.map((panel, idx) => ({ panel, idx, issueCount: 0 }))
      )
        .map(({ panel, idx: panelIndex, issueCount: preIssueCount }) => {
        // Guard panel data with safe defaults
        const safePanel = panel ?? {};
        const isExpanded = expandedPanels.has(panelIndex)
        const testRows = safePanel.test_rows || []
        const issuesCount = testRows.reduce((acc, r) => acc + (rowNeedsReview(r) ? 1 : 0), 0)
        const allIdx = testRows.map((_, i) => i)
        const filteredIndices = onlyIssues
          ? allIdx.filter(i => rowNeedsReview(testRows[i]))
          : (sortNeedsFirst
              ? allIdx.slice().sort((a, b) => {
                  const na = rowNeedsReview(testRows[a])
                  const nb = rowNeedsReview(testRows[b])
                  if (na !== nb) return na ? -1 : 1 // issues first
                  return a - b
                })
              : allIdx)
        const panelName = safePanel.name || 'UNNAMED'

        return (
          <div key={safePanel.id || panelIndex} className="border border-gray-200 rounded-lg bg-white">
            {/* Panel Header */}
            <div
              className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 rounded-t-lg"
              onClick={() => togglePanel(panelIndex)}
            >
              <div className="flex items-center space-x-3">
                {isExpanded ? (
                  <ChevronDown className="h-5 w-5 text-gray-400" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-gray-400" />
                )}
                <h3 className="text-lg font-medium text-gray-900">
                  Panel: {panelName}
                </h3>
                <div className="flex items-center space-x-2">
                  {safePanel.test_count !== undefined && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {safePanel.test_count} test{safePanel.test_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  {safePanel.needs_review && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      Needs Review
                    </span>
                  )}
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                    Issues: {issuesCount}
                  </span>
                  {safePanel.panel_score !== undefined && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      Score: {Math.round(safePanel.panel_score * 100)}%
                    </span>
                  )}
                  {safePanel.started_at_page && safePanel.started_at_line && (
                    <span className="text-xs text-gray-500">
                      Page {safePanel.started_at_page}:{safePanel.started_at_line}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Panel Content */}
            {(isExpanded && (!autoCollapseClean || issuesCount > 0)) && (
              <div className="border-t border-gray-200">
                {filteredIndices.length === 0 ? (
                  <div className="p-4 text-center text-gray-500">
                    {onlyIssues ? 'No issues in this panel' : 'No tests in this panel'}
                  </div>
                ) : (
                  <>
                    {/* Desktop Table View */}
                    <div className="hidden lg:block overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Test Name
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Result Value
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Units
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Flag
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Reference Range
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {filteredIndices.map((testIndex) => {
                            const testRow = testRows[testIndex]
                            // Guard test row data with safe defaults
                            const safeTestRow = testRow ?? {};
                            const hasModifications = getModifiedKeysForRow(panelIndex, testIndex).length > 0
                            const rowKey = `${panelIndex}-${testIndex}`
                            const isSaving = savingRows.has(rowKey)
                            const wasSaved = savedRows.has(rowKey)

                            return (
                              <tr
                                key={safeTestRow.id || testIndex}
                                className={cn(
                                  "hover:bg-gray-50",
                                  hasModifications && "bg-yellow-50",
                                  isSaving && "bg-blue-50",
                                  wasSaved && "bg-green-50"
                                )}
                              >
                                <td className="px-4 py-3">
                                  <input
                                    type="text"
                                    value={getValue(panelIndex, testIndex, 'test_name') as any}
                                    onChange={(e) => handleFieldChange(panelIndex, testIndex, 'test_name', e.target.value)}
                                    className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
                                    placeholder="Test name"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <input
                                    type="text"
                                    value={getValue(panelIndex, testIndex, 'result_value') as any}
                                    onChange={(e) => handleFieldChange(panelIndex, testIndex, 'result_value', e.target.value)}
                                    className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
                                    placeholder="Result value"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <input
                                    type="text"
                                    value={getValue(panelIndex, testIndex, 'units') as any}
                                    onChange={(e) => handleFieldChange(panelIndex, testIndex, 'units', e.target.value)}
                                    className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
                                    placeholder="Units"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <select
                                    value={getValue(panelIndex, testIndex, 'flag') as any}
                                    onChange={(e) => handleFieldChange(panelIndex, testIndex, 'flag', e.target.value)}
                                    className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
                                  >
                                    {FLAG_OPTIONS.map(option => (
                                      <option key={option} value={option}>
                                        {option || 'None'}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                                <td className="px-4 py-3">
                                  <input
                                    type="text"
                                    value={getValue(panelIndex, testIndex, 'reference_range_text') as any}
                                    onChange={(e) => handleFieldChange(panelIndex, testIndex, 'reference_range_text', e.target.value)}
                                    className="w-full border-0 p-0 text-sm focus:ring-2 focus:ring-blue-500 rounded"
                                    placeholder="Reference range"
                                  />
                                </td>
                                <td className="px-4 py-3 text-right">
                                  <div className="flex items-center justify-end space-x-2">
                                    {(isSaving || wasSaved) && (
                                      <span
                                        className={cn(
                                          "text-xs px-2 py-1 rounded-full",
                                          isSaving && "bg-blue-100 text-blue-800",
                                          wasSaved && "bg-green-100 text-green-800"
                                        )}
                                        aria-live="polite"
                                      >
                                        {isSaving ? 'Saving…' : 'Saved'}
                                      </span>
                                    )}
                                    <button
                                      onClick={() => saveRow(panelIndex, testIndex)}
                                      className="text-green-600 hover:text-green-900 p-1 disabled:opacity-50"
                                      title="Save row"
                                      disabled={!hasModifications || isSaving}
                                    >
                                      <Save className="h-4 w-4" />
                                    </button>
                                    <button
                                      onClick={() => resetRow(panelIndex, testIndex)}
                                      className="text-gray-600 hover:text-gray-900 p-1 disabled:opacity-50"
                                      title="Reset row"
                                      disabled={isSaving}
                                    >
                                      <RotateCcw className="h-4 w-4" />
                                    </button>
                                    <button
                                      onClick={() => deleteRow(panelIndex, testIndex)}
                                      className="text-red-600 hover:text-red-900 p-1 disabled:opacity-50"
                                      title="Delete row"
                                      disabled={isSaving}
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Mobile Card View */}
                    <div className="lg:hidden space-y-4 p-4">
                      {testRows.map((testRow, testIndex) => {
                        // Guard test row data with safe defaults
                        const safeTestRow = testRow ?? {};
                        const hasModifications = getModifiedKeysForRow(panelIndex, testIndex).length > 0
                        const rowKey = `${panelIndex}-${testIndex}`
                        const isSaving = savingRows.has(rowKey)
                        const wasSaved = savedRows.has(rowKey)

                        return (
                          <div
                            key={safeTestRow.id || testIndex}
                            className={cn(
                              "border border-gray-200 rounded-lg p-4 space-y-3",
                              hasModifications && "bg-yellow-50 border-yellow-200",
                              isSaving && "bg-blue-50 border-blue-200",
                              wasSaved && "bg-green-50 border-green-200"
                            )}
                          >
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                  Test Name
                                </label>
                                <input
                                  type="text"
                                  value={getValue(panelIndex, testIndex, 'test_name') as any}
                                  onChange={(e) => handleFieldChange(panelIndex, testIndex, 'test_name', e.target.value)}
                                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                  placeholder="Test name"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                  Result Value
                                </label>
                                <input
                                  type="text"
                                  value={getValue(panelIndex, testIndex, 'result_value') as any}
                                  onChange={(e) => handleFieldChange(panelIndex, testIndex, 'result_value', e.target.value)}
                                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                  placeholder="Result value"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                  Units
                                </label>
                                <input
                                  type="text"
                                  value={getValue(panelIndex, testIndex, 'units') as any}
                                  onChange={(e) => handleFieldChange(panelIndex, testIndex, 'units', e.target.value)}
                                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                  placeholder="Units"
                                />
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-700 mb-1">
                                  Flag
                                </label>
                                <select
                                  value={getValue(panelIndex, testIndex, 'flag') as any}
                                  onChange={(e) => handleFieldChange(panelIndex, testIndex, 'flag', e.target.value)}
                                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                  {FLAG_OPTIONS.map(option => (
                                    <option key={option} value={option}>
                                      {option || 'None'}
                                    </option>
                                  ))}
                                </select>
                              </div>
                            </div>

                            <div>
                              <label className="block text-xs font-medium text-gray-700 mb-1">
                                Reference Range
                              </label>
                                <input
                                  type="text"
                                  value={getValue(panelIndex, testIndex, 'reference_range_text') as any}
                                  onChange={(e) => handleFieldChange(panelIndex, testIndex, 'reference_range_text', e.target.value)}
                                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                placeholder="Reference range"
                              />
                            </div>

                            <div className="flex items-center justify-between pt-2">
                              <div className="flex items-center space-x-2">
                                <span className="text-xs text-gray-500">
                                  Test {testIndex + 1}
                                </span>
                                {(isSaving || wasSaved) && (
                                  <span
                                    className={cn(
                                      "text-xs px-2 py-1 rounded-full",
                                      isSaving && "bg-blue-100 text-blue-800",
                                      wasSaved && "bg-green-100 text-green-800"
                                    )}
                                    aria-live="polite"
                                  >
                                    {isSaving ? 'Saving…' : 'Saved'}
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => saveRow(panelIndex, testIndex)}
                                  className="inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                                  disabled={!hasModifications || isSaving}
                                >
                                  <Save className="h-3 w-3 mr-1" />
                                  Save
                                </button>
                                <button
                                  onClick={() => resetRow(panelIndex, testIndex)}
                                  className="inline-flex items-center px-3 py-1 border border-gray-300 text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50"
                                  disabled={isSaving}
                                >
                                  <RotateCcw className="h-3 w-3 mr-1" />
                                  Reset
                                </button>
                                <button
                                  onClick={() => deleteRow(panelIndex, testIndex)}
                                  className="inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
                                  disabled={isSaving}
                                >
                                  <Trash2 className="h-3 w-3 mr-1" />
                                  Delete
                                </button>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </>
                )}

                {/* Add Test Button */}
                <div className="border-t border-gray-100 p-4">
                  <button
                    onClick={() => addTest(panelIndex)}
                    className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Test
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Export memoized component to prevent unnecessary rerenders
export const PanelsEditor = memo(PanelsEditorComponent)
