import React, { useState, useCallback, useRef } from 'react'

interface UndoRedoState<T> {
  past: T[]
  present: T
  future: T[]
}

interface UndoRedoActions {
  canUndo: boolean
  canRedo: boolean
  undo: () => void
  redo: () => void
  clear: () => void
  addSnapshot: (description?: string) => void
}

interface UndoRedoItem<T> {
  state: T
  description?: string
  timestamp: Date
}

export function useUndoRedo<T>(
  initialState: T,
  maxHistorySize: number = 50
): [T, (newState: T) => void, UndoRedoActions] {
  const [state, setState] = useState<UndoRedoState<UndoRedoItem<T>>>({
    past: [],
    present: {
      state: initialState,
      timestamp: new Date()
    },
    future: []
  })

  const lastSnapshot = useRef<T>(initialState)

  const canUndo = state.past.length > 0
  const canRedo = state.future.length > 0

  const undo = useCallback(() => {
    setState(currentState => {
      if (currentState.past.length === 0) return currentState

      const previous = currentState.past[currentState.past.length - 1]
      const newPast = currentState.past.slice(0, -1)

      return {
        past: newPast,
        present: previous,
        future: [currentState.present, ...currentState.future]
      }
    })
  }, [])

  const redo = useCallback(() => {
    setState(currentState => {
      if (currentState.future.length === 0) return currentState

      const next = currentState.future[0]
      const newFuture = currentState.future.slice(1)

      return {
        past: [...currentState.past, currentState.present],
        present: next,
        future: newFuture
      }
    })
  }, [])

  const clear = useCallback(() => {
    setState(currentState => ({
      past: [],
      present: currentState.present,
      future: []
    }))
  }, [])

  const addSnapshot = useCallback((description?: string) => {
    const currentValue = state.present.state

    // Only add snapshot if state has actually changed
    if (JSON.stringify(currentValue) === JSON.stringify(lastSnapshot.current)) {
      return
    }

    setState(currentState => {
      const newSnapshot: UndoRedoItem<T> = {
        state: lastSnapshot.current,
        description,
        timestamp: new Date()
      }

      const newPast = [...currentState.past, newSnapshot]

      // Limit history size
      const trimmedPast = newPast.length > maxHistorySize
        ? newPast.slice(-maxHistorySize)
        : newPast

      return {
        past: trimmedPast,
        present: {
          state: currentValue,
          timestamp: new Date(),
          description: description || 'Change'
        },
        future: [] // Clear future when new action is performed
      }
    })

    lastSnapshot.current = currentValue
  }, [state.present.state, maxHistorySize])

  const setValue = useCallback((newValue: T) => {
    setState(currentState => ({
      ...currentState,
      present: {
        state: newValue,
        timestamp: new Date()
      }
    }))
  }, [])

  return [
    state.present.state,
    setValue,
    {
      canUndo,
      canRedo,
      undo,
      redo,
      clear,
      addSnapshot
    }
  ]
}

// Keyboard shortcut hook for undo/redo
export function useUndoRedoKeyboard(undoRedoActions: UndoRedoActions) {
  const { undo, redo, canUndo, canRedo } = undoRedoActions

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey) {
        if (e.key === 'z' && canUndo) {
          e.preventDefault()
          undo()
        }
      }

      if ((e.metaKey || e.ctrlKey) && e.shiftKey && !e.altKey) {
        if (e.key === 'Z' && canRedo) {
          e.preventDefault()
          redo()
        }
      }

      // Alternative: Ctrl/Cmd + Y for redo
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey) {
        if (e.key === 'y' && canRedo) {
          e.preventDefault()
          redo()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [undo, redo, canUndo, canRedo])
}