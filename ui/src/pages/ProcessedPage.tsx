// ui/src/pages/ProcessedPage.tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Api } from '../lib/api';
import { normalizeResultId } from '@/lib/normalizeIds';
import { buildResultPath } from '@/lib/routeParsing';
import { Edit3, Eye } from 'lucide-react';
import React from 'react'
import type { LabResult } from '@/types'
type Row = {
  job_id: string
  filename: string
  size: number
  modified: number
  needsReview?: boolean
  summary?: any
  rid?: string
  has_canonical?: boolean
  canonical_path?: string | null
  debug_paths?: string[]
};

type Group = {
  rid: string
  latest?: Row
  hasCanonical: boolean
  canonicalPath?: string | null
  debugStages: string[]
  files: Row[]
}

export default function ProcessedPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState<string>(() => {
    try {
      return localStorage.getItem('labai.processed.query') || ''
    } catch { return '' }
  });
  useEffect(() => {
    try { localStorage.setItem('labai.processed.query', query) } catch {}
  }, [query])
  const [needsFirst, setNeedsFirst] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem('labai.processed.needsFirst')
      return v === null ? true : v === 'true'
    } catch { return true }
  })
  useEffect(() => { try { localStorage.setItem('labai.processed.needsFirst', String(needsFirst)) } catch {} }, [needsFirst])

  useEffect(() => {
    (async () => {
      try {
        const data = await Api.listResults(1, 100);
        setRows(data.results);
      } catch (e: any) {
        setError(e?.message || 'Failed to load results');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <div className="p-6">Loading…</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!rows.length) return <div className="p-6">No results yet.</div>;

  // Group artifacts by RID
  const groupsMap = new Map<string, Group>()
  for (const r of rows) {
    const rid = r.rid || normalizeResultId(r.job_id)
    const g = groupsMap.get(rid) || { rid, hasCanonical: !!r.has_canonical, canonicalPath: r.canonical_path, debugStages: [], files: [] }
    g.files.push(r)
    g.latest = (!g.latest || r.modified > g.latest.modified) ? r : g.latest
    g.hasCanonical = g.hasCanonical || !!r.has_canonical
    g.canonicalPath = g.canonicalPath || r.canonical_path
    // Derive debug stages from filenames
    const name = r.filename
    const stageMatch = name.match(/\.(01a?_lines_merged|01_lines|02_roles|03_compose)\.debug\.json$/)
    if (stageMatch) {
      const token = stageMatch[1]
      const normalized = token === '01a_lines_merged' ? '01a_lines_merged' : token
      if (!g.debugStages.includes(normalized)) g.debugStages.push(normalized)
    }
    groupsMap.set(rid, g)
  }

  const groupsAllBase = Array.from(groupsMap.values())
  const groupsAll = (needsFirst
    ? groupsAllBase.sort((a, b) => (groupIsNeedsReview(b) ? 1 : 0) - (groupIsNeedsReview(a) ? 1 : 0) || ((b.latest?.modified||0) - (a.latest?.modified||0)))
    : groupsAllBase.sort((a, b) => ((b.latest?.modified||0) - (a.latest?.modified||0)))
  )

  const q = query.trim().toLowerCase();
  const groups = q
    ? groupsAll.filter(g => groupMatchesQuery(g, q))
    : groupsAll

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between gap-3 mb-2">
        <input
          type="search"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search (patient, vendor, report id, RID)"
          className="w-full md:w-96 border rounded px-3 py-2 text-sm"
        />
        <div className="flex items-center gap-3 text-sm text-gray-600 whitespace-nowrap">
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={needsFirst} onChange={e => setNeedsFirst(e.target.checked)} />
            <span>Needs review first</span>
          </label>
          <span>
            {groups.length} of {groupsAll.length}
          </span>
        </div>
      </div>

      {groups.map(g => (
        <ArtifactGroup key={g.rid} group={g} />
      ))}
    </div>
  )
}

function ArtifactGroup({ group }: { group: Group }) {
  const [showDebug, setShowDebug] = React.useState(false)
  const rid = group.rid
  const [friendlyTitle, setFriendlyTitle] = React.useState<string>(() => trimDebugSuffix(group.latest?.filename || rid))
  const [subtitle, setSubtitle] = React.useState<string>('')
  const [needsReview, setNeedsReview] = React.useState<boolean>(!!group.latest?.needsReview)
  const reviewHref = `/review/${rid}` // always route to base RID (no .debug suffix)

  // Compute a friendly title from the latest row summary first; fallback to fetching full result
  React.useEffect(() => {
    let alive = true

    const fromLocalSummary = () => {
      const row = group.latest
      if (!row) return false
      const sum: any = row.summary || {}
      // Try patient
      const p = sum?.document_info?.patient || sum?.patient
      const patientTitle = p?.last_name && p?.first_name ? `${p.last_name}, ${p.first_name}` : null
      // Try vendor / performing lab
      const vendorTitle = sum?.document_info?.vendor?.name || sum?.vendor?.name || sum?.document_info?.performing_lab?.name || sum?.performing_lab?.name || null
      // Try report id
      const reportId = sum?.document_info?.report?.id || sum?.report?.id || null
      // Try panels
      const panels = Array.isArray(sum?.lab_panels) ? sum.lab_panels : null
      const panelName = panels && panels.length > 0 ? panels[0]?.name : null

      const titleCandidate = patientTitle || vendorTitle || reportId || panelName
      if (titleCandidate) {
        const pretty = titleCandidate.toString().trim()
        if (alive && pretty) {
          setFriendlyTitle(pretty)
          const panelCount = panels ? panels.length : (sum?.panel_count || undefined)
          const testCount = panels ? panels.reduce((acc: number, p: any) => acc + (Array.isArray(p?.test_rows) ? p.test_rows.length : 0), 0) : (sum?.test_count || undefined)
          const when = group.latest ? new Date(group.latest.modified * 1000).toLocaleString() : ''
          const sizeStr = group.latest ? `${(group.latest.size/1024).toFixed(1)} KB` : ''
          const parts = [
            panelCount ? fmtCount(panelCount, 'panel') : undefined,
            typeof testCount === 'number' ? fmtCount(testCount, 'test') : undefined,
            sizeStr,
            when,
          ].filter(Boolean)
          setSubtitle(parts.join(' · '))
          // needs review flag if provided by summary
          if (typeof row.needsReview === 'boolean') setNeedsReview(!!row.needsReview)
          return true
        }
      }
      return false
    }

    const fetchAndCompute = async () => {
      try {
        const data = await Api.getResult(rid) as LabResult
        if (!alive || !data) return
        // EnhancedDocumentInfo path
        const di: any = (data as any).document_info || {}
        const patient = di?.patient || {}
        const vendor = di?.vendor || {}
        const lab = di?.performing_lab || {}
        const report = di?.report || {}

        const patientTitle = patient?.last_name && patient?.first_name ? `${patient.last_name}, ${patient.first_name}` : null
        const vendorTitle = vendor?.name || lab?.name || null
        const reportId = report?.id || null
        const panelName = Array.isArray(data.lab_panels) && data.lab_panels.length ? data.lab_panels[0]?.name : null
        const titleCandidate = patientTitle || vendorTitle || reportId || panelName || trimDebugSuffix(group.latest?.filename || rid)
        setFriendlyTitle(String(titleCandidate))

        const panelCount = Array.isArray(data.lab_panels) ? data.lab_panels.length : undefined
        const testCount = Array.isArray(data.lab_panels)
          ? data.lab_panels.reduce((acc: number, p: any) => acc + (Array.isArray(p?.test_rows) ? p.test_rows.length : 0), 0)
          : undefined
        const when = group.latest ? new Date(group.latest.modified * 1000).toLocaleString() : ''
        const sizeStr = group.latest ? `${(group.latest.size/1024).toFixed(1)} KB` : ''
        const parts = [
          panelCount ? fmtCount(panelCount, 'panel') : undefined,
          typeof testCount === 'number' ? fmtCount(testCount, 'test') : undefined,
          sizeStr,
          when,
        ].filter(Boolean)
        setSubtitle(parts.join(' · '))

        // needs review derived from panels if present
        try {
          const anyNeeds = Array.isArray((data as any).lab_panels) && (data as any).lab_panels.some((p: any) => !!p?.needs_review)
          setNeedsReview(anyNeeds)
        } catch {}
      } catch {
        // leave defaults
      }
    }

    if (!fromLocalSummary()) {
      void fetchAndCompute()
    }

    return () => { alive = false }
  }, [group.latest, rid])

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{friendlyTitle}</div>
          <div className="text-xs text-gray-500 mt-0.5"><code>{rid}</code></div>
          <div className="text-sm text-gray-500 mt-1">{subtitle || (group.latest ? `${(group.latest.size/1024).toFixed(1)} KB · ${new Date(group.latest.modified * 1000).toLocaleString()}` : '')}</div>
          {group.hasCanonical && (
            <div className="mt-1">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                Source of truth (editable via Manual Review)
              </span>
            </div>
          )}
          {needsReview && (
            <div className="mt-1">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                Needs Review
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <Link
            to={buildResultPath('viewer', rid)}
            className="btn-ghost p-2 flex items-center space-x-1"
            title={`View result ${rid}`}
            aria-label={`View result ${rid}`}
          >
            <Eye size={16} />
            <span className="hidden sm:inline">View</span>
          </Link>

          <Link
            to={reviewHref}
            className="btn-primary flex items-center space-x-2"
            title={`Review and edit ${rid}`}
            aria-label={`Review and edit ${rid}`}
          >
            <Edit3 size={16} />
            <span>Review & Edit</span>
          </Link>
        </div>
      </div>

      {/* Troubleshooting artifacts accordion */}
      <div className="mt-3">
        <button className="text-sm text-gray-700 underline" onClick={()=>setShowDebug(!showDebug)}>
          {showDebug ? 'Hide' : 'Show'} troubleshooting artifacts
        </button>
        {showDebug && (
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2">
            {group.debugStages.map(stage => (
              <Link
                key={stage}
                to={buildResultPath('viewer', rid, { stage, flags: ['debug'] })}
                className="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 inline-flex items-center"
              >
                {rid}.{stage}.debug.json
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Helpers
function trimDebugSuffix(name: string): string {
  if (!name) return ''
  // Remove common debug suffix fragments to reveal base RID-ish title
  return name
    .replace(/\.0[123]a?_.*?\.debug\.json$/i, '')
    .replace(/\.json$/i, '')
}

function groupMatchesQuery(g: Group, q: string): boolean {
  const rid = g.rid.toLowerCase()
  if (rid.includes(q)) return true
  const row = g.latest
  if (row) {
    const fname = (row.filename || '').toLowerCase()
    if (fname.includes(q)) return true
    const sum: any = row.summary || {}
    const di: any = sum.document_info || {}
    const parts: string[] = []
    const p = di.patient || sum.patient || {}
    if (p.last_name) parts.push(String(p.last_name))
    if (p.first_name) parts.push(String(p.first_name))
    const vendor = di.vendor || sum.vendor || {}
    if (vendor.name) parts.push(String(vendor.name))
    const lab = di.performing_lab || sum.performing_lab || {}
    if (lab.name) parts.push(String(lab.name))
    const report = di.report || sum.report || {}
    if (report.id) parts.push(String(report.id))
    const panels = Array.isArray(sum.lab_panels) ? sum.lab_panels : []
    for (let i = 0; i < Math.min(panels.length, 3); i++) {
      if (panels[i]?.name) parts.push(String(panels[i].name))
    }
    const hay = parts.join(' ').toLowerCase()
    if (hay.includes(q)) return true
  }
  return false
}

function groupIsNeedsReview(g: Group): boolean {
  try {
    // Prefer explicit flag on latest file if present
    if (typeof g.latest?.needsReview === 'boolean') return !!g.latest.needsReview
    // Otherwise scan files in the group
    for (const f of g.files || []) {
      if (typeof f.needsReview === 'boolean' && f.needsReview) return true
      const sum: any = f.summary || {}
      if (sum?.needsReview === true) return true
      if (Array.isArray(sum?.lab_panels) && sum.lab_panels.some((p: any) => !!p?.needs_review)) return true
    }
  } catch {}
  return false
}

function fmtCount(n: number, word: 'panel' | 'test'): string {
  const plural = n === 1 ? word : `${word}s`
  return `${n} ${plural}`
}
