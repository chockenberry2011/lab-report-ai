// utils/formatters.ts
import type { TestRow } from '@/types'

/**
 * Format reference range with structured approach
 * Priority: low-high + units > reference_range_text > reference_range (legacy)
 */
export function formatReferenceRange(
  input: TestRow | string | { text?: string | null } | null | undefined
): string {
  // Helper to normalize stray markers like sample indices
  const clean = (s: string | null | undefined) => {
    if (!s) return ''
    return String(s).replace(/\s+0\d+\b/g, '').trim()
  }

  // Handle direct string or {text}
  if (typeof input === 'string') {
    const s = clean(input)
    return s || '—'
  }
  if (input && typeof input === 'object' && 'text' in input && typeof (input as any).text === 'string') {
    const s = clean((input as any).text)
    return s || '—'
  }

  // Handle TestRow-like object
  const row = input as Partial<TestRow> | undefined | null
  if (row && typeof row === 'object') {
    const low = (row as any).reference_range_low
    const high = (row as any).reference_range_high
    const units = clean((row as any).units)

    if (low != null && high != null) {
      const range = `${low}–${high}${units ? ` ${units}` : ''}`.trim()
      return range || '—'
    }

    const text = clean((row as any).reference_range_text)
    if (text) return text

    const legacy = (row as any).reference_range
    if (typeof legacy === 'string') {
      const s = clean(legacy)
      return s || '—'
    }
    if (legacy && typeof legacy === 'object' && typeof legacy.text === 'string') {
      const s = clean(legacy.text)
      return s || '—'
    }
  }

  return '—'
}

/**
 * Normalize flag to standard format
 * Returns normalized short flag (H/L/CRIT/ABN) or null
 */
export function normalizeFlag(flag?: string | null): string | null {
  if (!flag) return null
  
  const flagUpper = flag.trim().toUpperCase()
  
  // Standard mappings
  if (['H', 'HIGH', 'HI'].includes(flagUpper)) return 'H'
  if (['L', 'LOW', 'LO'].includes(flagUpper)) return 'L'
  if (['CRIT', 'CRITICAL', 'PANIC'].includes(flagUpper)) return 'CRIT'
  if (['ABN', 'ABNORMAL', 'A'].includes(flagUpper)) return 'ABN'
  
  // Return first 10 chars for unknown flags
  return flagUpper.slice(0, 10) || null
}

/**
 * Get CSS class for flag type
 */
export function getFlagClass(flag: string | null): string {
  if (!flag) return ''
  
  switch (flag.toUpperCase()) {
    case 'H':
    case 'HIGH':
      return 'flag-high'
    case 'L': 
    case 'LOW':
      return 'flag-low'
    case 'CRIT':
    case 'CRITICAL':
      return 'flag-critical'
    case 'ABN':
    case 'ABNORMAL':
      return 'flag-abnormal'
    default:
      return 'flag-default'
  }
}

/**
 * Format address into single string
 */
export function formatAddress(address?: {
  street?: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
} | null): string {
  if (!address) return '—'
  
  const parts = [
    address.street,
    address.city,
    address.state,
    address.zip
  ].filter(Boolean)
  
  return parts.length > 0 ? parts.join(', ') : '—'
}

/**
 * Format patient name
 */
export function formatPatientName(patient?: {
  first_name?: string | null
  last_name?: string | null
  middle?: string | null
} | null): string {
  if (!patient) return '—'
  
  const parts = [
    patient.first_name,
    patient.middle,
    patient.last_name
  ].filter(Boolean)
  
  return parts.length > 0 ? parts.join(' ') : '—'
}

/**
 * Format date string to readable format
 */
export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return '—'
  
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return dateStr
  }
}

/**
 * Format datetime string to readable format
 */
export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return '—'
  
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text?: string | null, maxLength: number = 100): string {
  if (!text) return '—'

  return text.length <= maxLength
    ? text
    : `${text.slice(0, maxLength).trim()}...`
}

/**
 * Format a phone number to a consistent format
 * @param phone - Raw phone number string
 * @returns Formatted phone number or original if invalid
 */
export function formatPhoneNumber(phone: string | null | undefined): string {
  if (!phone) return ''

  // Remove all non-digit characters
  const digits = phone.replace(/\D/g, '')

  // Handle different phone number lengths
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
  } else if (digits.length === 11 && digits[0] === '1') {
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`
  }

  // Return original if we can't format it
  return phone
}

/**
 * Validate and normalize a field value based on its type
 * @param value - Raw field value
 * @param type - Field type from field definition
 * @returns Normalized value
 */
export function normalizeFieldValue(
  value: any,
  type: 'text' | 'date' | 'phone' | 'number' | 'select'
): any {
  if (value === null || value === undefined || value === '') {
    return null
  }

  switch (type) {
    case 'phone':
      return formatPhoneNumber(String(value))
    case 'date':
      return formatDate(value)
    case 'number':
      const num = Number(value)
      return isNaN(num) ? value : num
    case 'text':
    case 'select':
    default:
      return String(value).trim() || null
  }
}

/**
 * Check if two values are effectively equal (handles null/undefined/empty string equivalence)
 * @param a - First value
 * @param b - Second value
 * @returns True if values are equivalent
 */
export function valuesEqual(a: any, b: any): boolean {
  // Normalize null/undefined/empty string to null for comparison
  const normalizeEmpty = (val: any) => {
    if (val === null || val === undefined || val === '') return null
    return val
  }

  const normalizedA = normalizeEmpty(a)
  const normalizedB = normalizeEmpty(b)

  return normalizedA === normalizedB
}
