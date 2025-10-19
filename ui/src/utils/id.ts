/**
 * Utility functions for normalizing slug/ID parameters used in routes
 * Separates full slugs (with suffixes like .03_compose.debug) from base IDs
 */

export interface NormalizedIds {
  slugFull: string   // Original param with potential suffix
  baseId: string     // Base ID for /api/results calls (without suffix)
}

/**
 * Convert route param into normalized IDs for API calls
 * @param routeParam - The param from useParams (may include .03_compose.debug suffix)
 * @returns Object with slugFull (for /api/files calls) and baseId (for /api/results calls)
 */
export function normalizeSlugParam(routeParam: string): NormalizedIds {
  const slugFull = routeParam // Keep original for /api/files calls

  // Extract baseId by finding the first dot and taking everything before it
  // Examples:
  // - "debcc2f1-1234.03_compose.debug" -> "debcc2f1-1234"
  // - "simple-id" -> "simple-id" (no change)
  const dotIndex = routeParam.indexOf('.')
  const baseId = dotIndex >= 0 ? routeParam.substring(0, dotIndex) : routeParam

  return {
    slugFull,
    baseId
  }
}