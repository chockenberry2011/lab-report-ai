import { useState, useEffect, useCallback, useRef } from 'react'

type FieldKey = string
type ServerState = Record<FieldKey, any>
type DraftState = Record<FieldKey, any>
type TouchedFields = Set<FieldKey>

export interface ServerUpdateInfo {
  field: FieldKey
  oldValue: any
  newValue: any
}

export interface UseDraftStateReturn {
  // State
  draftState: DraftState
  serverUpdates: ServerUpdateInfo[]

  // Actions
  updateDraft: (field: FieldKey, value: any) => void
  commitServerUpdate: (field: FieldKey) => void
  dismissServerUpdate: (field: FieldKey) => void
  resetField: (field: FieldKey) => void

  // Getters
  isDirty: (field: FieldKey) => boolean
  getValue: (field: FieldKey) => any
}

/**
 * Manages local draft state with server update detection
 * Prevents input resets during background fetches by buffering edits locally
 */
export function useDraftState(serverState: ServerState): UseDraftStateReturn {
  const [draftState, setDraftState] = useState<DraftState>({})
  const [serverUpdates, setServerUpdates] = useState<ServerUpdateInfo[]>([])
  const touchedFields = useRef<TouchedFields>(new Set())
  const prevServerState = useRef<ServerState>({})

  // Initialize draft state from server state
  useEffect(() => {
    if (!serverState || Object.keys(serverState).length === 0) return

    setDraftState(prevDraft => {
      const newDraft = { ...prevDraft }

      // Check for server updates in fields we haven't touched
      const newUpdates: ServerUpdateInfo[] = []

      for (const [field, serverValue] of Object.entries(serverState)) {
        const prevServerValue = prevServerState.current[field]
        const hasServerValueChanged = prevServerValue !== undefined && prevServerValue !== serverValue
        const fieldIsTouched = touchedFields.current.has(field)

        if (!fieldIsTouched) {
          // Field not touched by user, sync server value to draft
          newDraft[field] = serverValue
        } else if (hasServerValueChanged) {
          // Field touched by user but server value changed - notify about conflict
          newUpdates.push({
            field,
            oldValue: prevServerValue,
            newValue: serverValue
          })
        }
      }

      // Add new server updates
      if (newUpdates.length > 0) {
        setServerUpdates(prev => [
          ...prev.filter(update => !newUpdates.some(nu => nu.field === update.field)),
          ...newUpdates
        ])
      }

      return newDraft
    })

    prevServerState.current = { ...serverState }
  }, [serverState])

  const updateDraft = useCallback((field: FieldKey, value: any) => {
    touchedFields.current.add(field)
    setDraftState(prev => ({ ...prev, [field]: value }))
  }, [])

  const commitServerUpdate = useCallback((field: FieldKey) => {
    const update = serverUpdates.find(u => u.field === field)
    if (update) {
      // Apply server value to draft
      setDraftState(prev => ({ ...prev, [field]: update.newValue }))
      // Remove from updates
      setServerUpdates(prev => prev.filter(u => u.field !== field))
    }
  }, [serverUpdates])

  const dismissServerUpdate = useCallback((field: FieldKey) => {
    setServerUpdates(prev => prev.filter(u => u.field !== field))
  }, [])

  const resetField = useCallback((field: FieldKey) => {
    const serverValue = serverState[field]
    setDraftState(prev => ({ ...prev, [field]: serverValue }))
    touchedFields.current.delete(field)
    // Remove any server updates for this field
    setServerUpdates(prev => prev.filter(u => u.field !== field))
  }, [serverState])

  const isDirty = useCallback((field: FieldKey) => {
    return touchedFields.current.has(field) && draftState[field] !== serverState[field]
  }, [draftState, serverState])

  const getValue = useCallback((field: FieldKey) => {
    return draftState[field] ?? serverState[field] ?? ''
  }, [draftState, serverState])

  return {
    draftState,
    serverUpdates,
    updateDraft,
    commitServerUpdate,
    dismissServerUpdate,
    resetField,
    isDirty,
    getValue
  }
}