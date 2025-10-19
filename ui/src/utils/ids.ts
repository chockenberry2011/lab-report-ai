/**
 * Shared helper to parse IDs from route params.
 * Delegates to the robust token-based parser.
 */
import { parseResultRoute, buildResultPath } from '@/lib/routeParsing'

export function parseResultIds(rawId: string | undefined) {
  const parsed = parseResultRoute(rawId ?? '')
  return { fullId: parsed.raw, baseId: parsed.baseId }
}

/**
 * Generate the correct review URL for an ID using the builder.
 * If ID is base UUID only, append stage "03_compose" and flag "debug".
 */
export function getReviewUrl(rawId: string | undefined): string {
  const wasEmpty = !((rawId ?? '').trim())
  const parsed = parseResultRoute(rawId ?? '')
  const baseId = parsed.baseId
  if (!baseId) {
    // Preserve legacy behavior for truly empty input
    return wasEmpty ? '/review/.03_compose.debug' : buildResultPath('review', '')
  }

  // If a stage exists, preserve stage/flags (deduped). Otherwise use clean base ID
  if (parsed.stage) {
    return buildResultPath('review', baseId, {
      stage: parsed.stage,
      flags: Array.from(parsed.flags),
    })
  }
  return buildResultPath('review', baseId)
}
