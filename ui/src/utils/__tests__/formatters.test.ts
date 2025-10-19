import { formatReferenceRange } from '@/utils/formatters'

describe('formatReferenceRange (defensive)', () => {
  it('handles structured low/high/units', () => {
    const row: any = { reference_range_low: 70, reference_range_high: 100, units: 'mg/dL' }
    expect(formatReferenceRange(row)).toBe('70–100 mg/dL')
  })

  it('handles reference_range_text', () => {
    const row: any = { reference_range_text: '70-100 mg/dL' }
    expect(formatReferenceRange(row)).toBe('70-100 mg/dL')
  })

  it('handles legacy string reference_range', () => {
    expect(formatReferenceRange('70-100')).toBe('70-100')
  })

  it('handles legacy object with text', () => {
    expect(formatReferenceRange({ text: '4.0 - 5.0' } as any)).toBe('4.0 - 5.0')
  })

  it('returns em dash for null/undefined or empty', () => {
    expect(formatReferenceRange(null as any)).toBe('—')
    expect(formatReferenceRange(undefined as any)).toBe('—')
    expect(formatReferenceRange({ text: '' } as any)).toBe('—')
  })
})

