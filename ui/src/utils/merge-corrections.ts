/**
 * Utility functions for merging extracted data with corrections
 */

import type { FieldValue, ReviewFieldState, CorrectionItem } from '@/types/review-fields'
import { getValueByPath, getCorrectionPath } from '@/lib/field-definitions'
import { valuesEqual } from './formatters'

/**
 * Merge extracted data with corrections to produce effective values
 * @param extractedData - The original extracted document data
 * @param corrections - Array of correction items
 * @param fieldStates - Current field states for UI
 * @returns Updated field states with effective values
 */
export function mergeCorrections(
  extractedData: any,
  corrections: CorrectionItem[],
  fieldStates: ReviewFieldState
): ReviewFieldState {
  const updated = { ...fieldStates }

  // Build correction lookup by path
  const correctionMap = new Map<string, any>()
  corrections.forEach(correction => {
    if (correction.op === 'set' && correction.path) {
      correctionMap.set(correction.path, correction.value)
    } else if (correction.op === 'unset' && correction.path) {
      correctionMap.set(correction.path, null)
    }
  })

  // Update field states with corrections
  Object.keys(updated).forEach(fieldKey => {
    const fieldState = updated[fieldKey]
    if (!fieldState) return

    const correctionPath = getCorrectionPath(fieldKey)
    const correctionValue = correctionMap.get(correctionPath)

    if (correctionValue !== undefined) {
      // Apply correction
      updated[fieldKey] = {
        ...fieldState,
        current: correctionValue,
        state: 'corrected'
      }
    } else {
      // Use extracted value
      const extractedValue = getValueByPath(extractedData, fieldState.sourceLine || '')
      updated[fieldKey] = {
        ...fieldState,
        current: extractedValue,
        state: extractedValue !== null && extractedValue !== undefined ? 'extracted' : 'empty'
      }
    }
  })

  return updated
}

/**
 * Create a correction item from a field change
 * @param fieldKey - The field key that changed
 * @param newValue - The new field value
 * @param originalValue - The original extracted value
 * @returns Correction item or null if no correction needed
 */
export function createCorrectionItem(
  fieldKey: string,
  newValue: any,
  originalValue: any
): CorrectionItem | null {
  const correctionPath = getCorrectionPath(fieldKey)

  // Don't create correction if values are equivalent
  if (valuesEqual(newValue, originalValue)) {
    return null
  }

  // Determine operation
  const isEmpty = newValue === null || newValue === undefined || newValue === ''
  const hadOriginalValue = originalValue !== null && originalValue !== undefined && originalValue !== ''

  if (isEmpty && hadOriginalValue) {
    // Remove the field if it's being cleared
    return {
      op: 'unset',
      path: correctionPath
    }
  } else if (!isEmpty) {
    // Set the field value
    return {
      op: 'set',
      path: correctionPath,
      value: newValue
    }
  }

  return null
}

/**
 * Generate corrections payload for API submission
 * @param pendingChanges - Map of field keys to new values
 * @param fieldStates - Current field states
 * @returns Corrections payload ready for API
 */
export function generateCorrectionsPayload(
  pendingChanges: Record<string, any>,
  fieldStates: ReviewFieldState
): { items: CorrectionItem[], schema_version: number } {
  const items: CorrectionItem[] = []

  Object.entries(pendingChanges).forEach(([fieldKey, newValue]) => {
    const fieldState = fieldStates[fieldKey]
    if (!fieldState) return

    const correctionItem = createCorrectionItem(fieldKey, newValue, fieldState.original)
    if (correctionItem) {
      items.push(correctionItem)
    }
  })

  return {
    items,
    schema_version: 1
  }
}

/**
 * Check if a field has been modified from its original value
 * @param fieldState - The field state to check
 * @returns True if the field has been modified
 */
export function isFieldModified(fieldState: FieldValue): boolean {
  return !valuesEqual(fieldState.current, fieldState.original)
}

/**
 * Count the number of modified fields in a field state collection
 * @param fieldStates - Collection of field states
 * @returns Number of modified fields
 */
export function countModifiedFields(fieldStates: ReviewFieldState): number {
  return Object.values(fieldStates).filter(isFieldModified).length
}