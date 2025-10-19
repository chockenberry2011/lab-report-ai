// Lightweight lab-specific formatters shared across views

export type NormalizedFlag = 'H' | 'L' | 'CRIT' | 'ABN'

// Normalize flag strings to canonical short codes
export function normalizeFlag(raw?: string | null): NormalizedFlag | null {
  if (!raw) return null
  const s = raw.trim().toUpperCase()
  if (!s) return null

  if (s === 'H' || s === 'HIGH' || s === 'HI') return 'H'
  if (s === 'L' || s === 'LOW' || s === 'LO') return 'L'
  if (s === 'CRIT' || s === 'CRITICAL' || s === 'PANIC') return 'CRIT'
  if (s === 'ABN' || s === 'ABNORMAL' || s === 'A') return 'ABN'
  return null
}

// Format reference range using structured fields when available
export function formatReferenceRange(t: {
  reference_range_low?: number | null,
  reference_range_high?: number | null,
  reference_range_text?: string | null,
  reference_range?: string | null,
  units?: string | null
}): string | null {
  const low = t.reference_range_low
  const high = t.reference_range_high
  const units = t.units?.trim()

  if (low != null && high != null && units) {
    return `${low}–${high} ${units}`.trim()
  }

  const stripMarkers = (s: string) => s.replace(/\s0\d\b/g, '').trim()

  if (t.reference_range_text && t.reference_range_text.trim()) {
    return stripMarkers(t.reference_range_text)
  }

  if (t.reference_range && t.reference_range.trim()) {
    return stripMarkers(t.reference_range)
  }

  return null
}

// Format address to a single line
export function formatAddress(a?: {
  street?: string
  city?: string
  state?: string
  zip?: string
} | null): string {
  if (!a) return '—'
  const parts = [a.street, a.city, a.state, a.zip].filter(Boolean)
  return parts.length ? parts.join(', ') : '—'
}

// Safely stringify values with a default fallback for empty values
export function safe(v: any, fallback: string = '—'): string {
  if (v === null || v === undefined) return fallback
  if (typeof v === 'string') {
    const s = v.trim()
    return s.length ? s : fallback
  }
  if (typeof v === 'number' || typeof v === 'boolean') return String(v)
  try {
    const s = JSON.stringify(v)
    return s && s !== '{}' && s !== '[]' ? s : fallback
  } catch {
    return fallback
  }
}

