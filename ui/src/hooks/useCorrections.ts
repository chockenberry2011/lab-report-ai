import { useCallback, useEffect, useRef, useState } from 'react'
import { resultsFetch } from '@/lib/apiClient'
import { loadCorrectionsFieldSchema, getCanonicalKey, getSuggestedCanonicalKeys, debugSchemaState } from '@/lib/correctionsSchema'
import { buildCorrectionPayload, isNoOp, normalizeValue } from '@/lib/correctionsPayload'
import { toast } from 'react-hot-toast'
import { normalizeResultId } from '@/lib/normalizeIds'
import { CorrectionsFileFormatError } from '@/lib/correctionsApi'

type FieldKey = string
type ServerCorrection = { value: string | null, meta?: any }

type CorrectionsMap = Record<FieldKey, ServerCorrection>
type DraftsMap = Record<FieldKey, string>

const now = () => Date.now()

// Core hook implementation
function useCorrectionsCore(resultId: string) {
  const [serverCorrections, setServerCorrections] = useState<CorrectionsMap>({})
  const [drafts, setDrafts] = useState<DraftsMap>({})
  const dirtyRef = useRef<Set<FieldKey>>(new Set())
  const lastInputAt = useRef<number>(0)
  const inFlight = useRef<boolean>(false)
  const pollTimer = useRef<number | null>(null)
  const saveTimer = useRef<number | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const markDirty = useCallback((k: FieldKey) => {
    dirtyRef.current = new Set(dirtyRef.current).add(k)
    lastInputAt.current = now()
  }, [])

  const updateDraft = useCallback((k: FieldKey, v: string) => {
    setDrafts(d => ({ ...d, [k]: v }))
    markDirty(k)
    // 🔧 FIX: Disable auto-save to prevent premature validation
    // Auto-save was causing "Value required" errors when user is still typing
    // The UI has explicit Save buttons, so auto-save is not needed
    console.log('📝 Draft updated:', { field: k, value: v })
  }, [markDirty])

  const applyFromServer = useCallback((fresh: CorrectionsMap) => {
    setServerCorrections(fresh)
    setDrafts(prev => {
      const next = { ...prev }
      for (const [k, sc] of Object.entries(fresh)) {
        // Only update drafts for non-dirty fields to preserve user input
        if (!dirtyRef.current.has(k)) {
          next[k] = sc?.value ?? ''
        }
      }
      return next
    })
  }, [])

  const fetchCorrections = useCallback(async (signal?: AbortSignal) => {
    if (inFlight.current) return
    // pause if user typed recently
    if (now() - lastInputAt.current < 1000) return
    inFlight.current = true
    try {
      const normId = normalizeResultId(resultId)
      const r = await fetch(`/api/results/${normId}/corrections`, {
        signal,
        headers: { "Cache-Control": "no-store" }
      })
      if (signal?.aborted) return
      if (!r.ok) {
        if (r.status !== 404) { // 404 is expected for new results
          console.warn('Failed to fetch corrections:', r.status)
        }
        return
      }
      // Normalize server response (array or wrapper) into path-keyed map
      const raw = await r.json() as any
      const list: any[] = Array.isArray(raw)
        ? raw
        : (Array.isArray(raw?.corrections)
            ? raw.corrections
            : (Array.isArray(raw?.items) ? raw.items : []))

      const toUiPath = (canonical: string): string | null => {
        const map: Record<string, string> = {
          vendor_name: 'vendor.name',
          patient_first_name: 'patient.first_name',
          patient_last_name: 'patient.last_name',
          header_label: 'header.label',
          header_value: 'header.value',
        }
        return map[canonical] || null
      }

      const fresh: CorrectionsMap = {}
      for (const it of list) {
        if (!it || typeof it !== 'object') continue
        const value = (it.value ?? it.new_value ?? it.val ?? null) as string | null
        let key: string | null = null
        if (typeof it.path === 'string' && it.path.trim() !== '') {
          key = it.path.trim()
        } else if (typeof it.field === 'string' && it.field.trim() !== '') {
          // Map canonical field back to a best-effort UI path
          key = toUiPath(it.field.trim()) || it.field.trim()
        }
        if (!key) continue
        fresh[key] = { value, meta: { source: it.source, ts: it.ts, op: it.op, field: it.field, path: it.path } }
      }
      applyFromServer(fresh)
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.warn('Error fetching corrections:', err)
      }
    } finally {
      inFlight.current = false
    }
  }, [resultId, applyFromServer])

  const startPolling = useCallback(() => {
    stopPolling()
    const controller = new AbortController()
    abortControllerRef.current = controller

    // immediately fetch once
    void fetchCorrections(controller.signal)

    pollTimer.current = setInterval(() => {
      void fetchCorrections(controller.signal)
    }, 3000) as unknown as number

    return () => {
      controller.abort()
    }
  }, [fetchCorrections])

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }, [])

  async function saveChanges(fields: FieldKey[]) {
    if (!fields.length) return

    // Sanitize RID: strip debug suffixes then normalize
    const baseRid = String(resultId).replace(/\.(?:\d+[a-z]?_.*|03_compose\.debug)+$/gi, '')
    const normId = normalizeResultId(baseRid)
    // Ensure schema is loaded once (try API prefix for dev proxy)
    try { await loadCorrectionsFieldSchema('/api') } catch {}

    // Build canonical payload, with validation and no-op guard
    const out: any[] = []
    const fieldMappingDebug: any[] = []

    const schemaDebug = debugSchemaState()
    console.log('🔍 Field mapping debug - saveChanges called with:', {
      fields,
      drafts,
      schema: schemaDebug
    })

    for (const k of fields) {
      const newVal = normalizeValue(drafts[k] ?? '').trim()
      const oldVal = normalizeValue(serverCorrections[k]?.value ?? '').trim()

      // Debug field mapping
      const canonical = getCanonicalKey(k)
      const suggestions = getSuggestedCanonicalKeys(10)
      const debugInfo = {
        originalField: k,
        newValue: newVal,
        oldValue: oldVal,
        canonicalField: canonical,
        availableFields: suggestions.slice(0, 5) // Show first 5 for brevity
      }
      fieldMappingDebug.push(debugInfo)

      if (newVal === '') {
        console.log('❌ Empty value for field:', debugInfo)
        try { window.dispatchEvent(new CustomEvent('corrections:field-error', { detail: { path: k, error: 'Value required' } })) } catch {}
        continue
      }

      if (isNoOp(oldVal, newVal)) {
        console.log('⏭️ No-op for field (no change):', debugInfo)
        continue
      }

      const ts = new Date().toISOString()

      // Always use path-based corrections for lab_panels to preserve context
      if (k.includes('lab_panels') || !canonical) {
        // Use path-based correction to support rich UI paths
        out.push({ path: k, op: 'replace', value: newVal, source: 'review-ui', ts })
        console.log('✅ Saved via path:', debugInfo)
      } else {
        out.push({ field: canonical, op: 'replace', value: newVal, source: 'review-ui', ts })
        console.log('✅ Field mapped successfully:', debugInfo)
      }
    }

    console.log('📋 Field mapping summary:', {
      totalFields: fields.length,
      mappedSuccessfully: out.length,
      debugInfo: fieldMappingDebug
    })

    try {
      const payload = out
      try { window.dispatchEvent(new CustomEvent('corrections:dev-update', { detail: { when: 'before', payload } })) } catch {}

      const resp = await resultsFetch(normId, '/corrections', { method: 'POST', body: JSON.stringify(payload) })
      const status = resp.status
      let respBody: any = null
      try { respBody = await resp.json() } catch {}
      try { window.dispatchEvent(new CustomEvent('corrections:dev-update', { detail: { when: 'after', payload, status, body: respBody } })) } catch {}
      if (!resp.ok) {
        const err = respBody || {}
        const field = err.field
        const message = err.detail || err.error || 'Save failed'
        if (field) window.dispatchEvent(new CustomEvent('corrections:field-error', { detail: { path: field, error: message } }))
        else toast.error(message)
        return
      }

      // Immediately GET fresh data with cache bypass
      const freshResponse = await fetch(`/api/results/${normId}/corrections`, {
        headers: { "Cache-Control": "no-store" }
      })

      if (freshResponse.ok) {
        const raw = await freshResponse.json() as any
        const list: any[] = Array.isArray(raw)
          ? raw
          : (Array.isArray(raw?.corrections)
              ? raw.corrections
              : (Array.isArray(raw?.items) ? raw.items : []))

        const toUiPath = (canonical: string): string | null => {
          const map: Record<string, string> = {
            vendor_name: 'vendor.name',
            patient_first_name: 'patient.first_name',
            patient_last_name: 'patient.last_name',
            header_label: 'header.label',
            header_value: 'header.value',
          }
          return map[canonical] || null
        }

        const fresh: CorrectionsMap = {}
        for (const it of list) {
          if (!it || typeof it !== 'object') continue
          const value = (it.value ?? it.new_value ?? it.val ?? null) as string | null
          let key: string | null = null
          if (typeof it.path === 'string' && it.path.trim() !== '') {
            key = it.path.trim()
          } else if (typeof it.field === 'string' && it.field.trim() !== '') {
            key = toUiPath(it.field.trim()) || it.field.trim()
          }
          if (!key) continue
          fresh[key] = { value, meta: { source: it.source, ts: it.ts, op: it.op, field: it.field, path: it.path } }
        }
        applyFromServer(fresh)
      }

      // Proactively refetch the structured result so viewers see updates immediately
      try {
        const bust = Date.now()
        await fetch(`/api/results/${normId}?t=${bust}`, { headers: { "Cache-Control": "no-store" } })
        try { window.dispatchEvent(new CustomEvent('corrections:result-refetch', { detail: { t: bust, rid: normId } })) } catch {}
      } catch {}

      // Clear dirty flags for saved fields
      const next = new Set(dirtyRef.current)
      fields.forEach(k => next.delete(k))
      dirtyRef.current = next
    } catch (error: any) {
      // Handle 422 CORRECTIONS_FILE_WRONG_TYPE errors specifically
      if (error.response?.status === 422 &&
          error.response?.data?.error === 'CORRECTIONS_FILE_WRONG_TYPE') {
        const formatError = new CorrectionsFileFormatError(error.response.data);
        formatError.showToast();
        throw formatError;
      }
      console.error('Error saving corrections:', error)
      throw error
    }
  }

  // Start polling on mount and resultId change
  useEffect(() => {
    const abort = startPolling()
    return () => {
      stopPolling();
      abort?.()
    }
  }, [startPolling, stopPolling])

  // Reset local state on ID change
  useEffect(() => {
    dirtyRef.current = new Set()
    setServerCorrections({})
    setDrafts({})
  }, [resultId])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (saveTimer.current) {
        clearTimeout(saveTimer.current)
      }
      stopPolling()
    }
  }, [stopPolling])

  return {
    drafts,
    serverCorrections,
    updateDraft,
    saveChanges,
    markDirty,
  }
}

// Legacy overload for backward compatibility
interface UseCorrectionOptions {
  jobId: string
  resultData?: any
  extractedTextData?: any
  autosave?: boolean
}

interface UseCorrectionsReturn {
  // Legacy API (preserved for backward compatibility)
  fieldStates: Record<string, any>
  isDirty: boolean
  isLoading: boolean
  isSaving: boolean
  error: string | null
  saveStatus: 'idle' | 'saving' | 'saved' | 'error'
  updateField: (fieldKey: string, value: any) => void
  resetField: (fieldKey: string) => void
  saveAll: () => Promise<void>
  resetAll: () => void

  // New generic field API
  data: any
  corrections: Record<string, any>
  drafts: Record<string, any>
  setDraft: (path: string, value: any) => void
  saveChanges: (paths: string[]) => Promise<void>
  saveField: (path: string) => Promise<void>
  resetField_generic: (path: string) => void
  fieldStatus: (path: string) => { dirty: boolean; saving: boolean; saved: boolean; error?: string | null }
  saveSection: (paths: string[]) => Promise<void>
  resetSection: (paths: string[]) => void
  getValue: (path: string) => any
}

// Overloaded function signature for backward compatibility
export function useCorrections(resultId: string): { drafts: DraftsMap; serverCorrections: CorrectionsMap; updateDraft: (k: FieldKey, v: string) => void; saveChanges: (fields: FieldKey[]) => Promise<void>; markDirty: (k: FieldKey) => void }
export function useCorrections(options: UseCorrectionOptions): UseCorrectionsReturn
export function useCorrections(
  optionsOrResultId: string | UseCorrectionOptions
): any {
  if (typeof optionsOrResultId === 'string') {
    // Simple signature: useCorrections(resultId) - returns the new simplified API
    return useCorrectionsCore(optionsOrResultId)
  } else {
    // Complex signature: useCorrections({ jobId, resultData, ... }) - returns legacy API
    const options = optionsOrResultId
    const { jobId, resultData, extractedTextData, autosave = true } = options

    console.log('🔍 useCorrections legacy mode called with:', {
      jobId,
      hasResultData: !!resultData,
      hasExtractedTextData: !!extractedTextData,
      autosave
    })

    if (!jobId) {
      // Return empty state for invalid jobId
      console.log('❌ useCorrections: No jobId provided, returning stub functions')
      return {
        fieldStates: {},
        isDirty: false,
        isLoading: false,
        isSaving: false,
        error: null,
        saveStatus: 'idle' as const,
        updateField: () => {},
        resetField: () => {},
        saveAll: async () => {},
        resetAll: () => {},
        data: resultData,
        corrections: {},
        drafts: {},
        setDraft: () => {},
        saveChanges: async () => {},
        saveField: async () => {},
        resetField_generic: () => {},
        fieldStatus: () => ({ dirty: false, saving: false, saved: false }),
        saveSection: async () => {},
        resetSection: () => {},
        getValue: () => undefined,
      }
    }

    // Use the new core hook internally but adapt the API
    const { drafts, serverCorrections, updateDraft, saveChanges, markDirty } = useCorrectionsCore(jobId)

    console.log('🔍 useCorrectionsCore returned:', {
      jobId,
      draftsKeys: Object.keys(drafts),
      serverCorrectionsKeys: Object.keys(serverCorrections),
      hasSaveChanges: typeof saveChanges === 'function',
      hasUpdateDraft: typeof updateDraft === 'function'
    })

    // Create legacy-compatible API
    const fieldStates: Record<string, any> = {}
    Object.keys(drafts).forEach(key => {
      const serverValue = serverCorrections[key]?.value
      const currentValue = drafts[key]
      fieldStates[key] = {
        current: currentValue,
        original: serverValue,
        state: currentValue !== serverValue ? 'corrected' : 'extracted'
      }
    })

    const getValue = useCallback((path: string) => {
      return drafts[path] ?? serverCorrections[path]?.value ?? undefined
    }, [drafts, serverCorrections])

    const setDraft = useCallback((path: string, value: any) => {
      updateDraft(path, String(value ?? ''))
    }, [updateDraft])

    const fieldStatus = useCallback((path: string) => {
      const isDirty = drafts[path] !== (serverCorrections[path]?.value ?? '')
      return {
        dirty: isDirty,
        saving: false, // TODO: could track saving state if needed
        saved: false,
        error: null
      }
    }, [drafts, serverCorrections])

    return {
      fieldStates,
      isDirty: Object.keys(drafts).some(k => fieldStatus(k).dirty),
      isLoading: false,
      isSaving: false,
      error: null,
      saveStatus: 'idle' as const,
      updateField: (fieldKey: string, value: any) => updateDraft(fieldKey, String(value ?? '')),
      resetField: (fieldKey: string) => {
        const originalValue = serverCorrections[fieldKey]?.value ?? ''
        updateDraft(fieldKey, originalValue)
      },
      saveAll: () => saveChanges(Object.keys(drafts).filter(k => fieldStatus(k).dirty)),
      resetAll: () => {
        Object.keys(drafts).forEach(k => {
          const originalValue = serverCorrections[k]?.value ?? ''
          updateDraft(k, originalValue)
        })
      },
      data: resultData,
      corrections: serverCorrections,
      drafts,
      setDraft,
      saveChanges,
      saveField: (path: string) => saveChanges([path]),
      resetField_generic: (path: string) => {
        const originalValue = serverCorrections[path]?.value ?? ''
        updateDraft(path, originalValue)
      },
      fieldStatus,
      saveSection: (paths: string[]) => saveChanges(paths),
      resetSection: (paths: string[]) => {
        paths.forEach(path => {
          const originalValue = serverCorrections[path]?.value ?? ''
          updateDraft(path, originalValue)
        })
      },
      getValue,
    }
  }
}
