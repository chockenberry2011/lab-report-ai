import { parseResultIds, getReviewUrl } from '../ids'

describe('parseResultIds', () => {
  it('should parse fullId with .03_compose.debug suffix', () => {
    const result = parseResultIds('abc-uuid.03_compose.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.03_compose.debug',
      baseId: 'abc-uuid'
    })
  })

  it('should parse fullId with .02_roles.debug suffix', () => {
    const result = parseResultIds('abc-uuid.02_roles.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.02_roles.debug',
      baseId: 'abc-uuid'
    })
  })

  it('should parse fullId with .01_lines.debug suffix', () => {
    const result = parseResultIds('abc-uuid.01_lines.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.01_lines.debug',
      baseId: 'abc-uuid'
    })
  })

  it('should parse fullId with .01_lines_merged.debug suffix', () => {
    const result = parseResultIds('abc-uuid.01_lines_merged.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.01_lines_merged.debug',
      baseId: 'abc-uuid'
    })
  })

  it('should handle base UUID without suffix', () => {
    const result = parseResultIds('abc-uuid')
    expect(result).toEqual({
      fullId: 'abc-uuid',
      baseId: 'abc-uuid'
    })
  })

  it('should handle doubled suffix correctly', () => {
    const result = parseResultIds('abc-uuid.03_compose.debug.03_compose.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.03_compose.debug.03_compose.debug',
      baseId: 'abc-uuid'
    })
  })

  it('should handle undefined input', () => {
    const result = parseResultIds(undefined)
    expect(result).toEqual({
      fullId: '',
      baseId: ''
    })
  })

  it('should handle empty string input', () => {
    const result = parseResultIds('')
    expect(result).toEqual({
      fullId: '',
      baseId: ''
    })
  })

  it('should handle URL-encoded input', () => {
    const result = parseResultIds('abc%2Duuid.03_compose.debug')
    expect(result).toEqual({
      fullId: 'abc-uuid.03_compose.debug',
      baseId: 'abc-uuid'
    })
  })
})

describe('getReviewUrl', () => {
  it('should return URL with fullId when ID has suffix', () => {
    const url = getReviewUrl('abc-uuid.03_compose.debug')
    expect(url).toBe('/review/abc-uuid.03_compose.debug')
  })

  it('should append .03_compose.debug when ID is base UUID only', () => {
    const url = getReviewUrl('abc-uuid')
    expect(url).toBe('/review/abc-uuid.03_compose.debug')
  })

  it('should handle undefined input', () => {
    const url = getReviewUrl(undefined)
    expect(url).toBe('/review/.03_compose.debug')
  })

  it('should handle different suffixes by preserving them', () => {
    const url = getReviewUrl('abc-uuid.01_lines.debug')
    expect(url).toBe('/review/abc-uuid.01_lines.debug')
  })
})