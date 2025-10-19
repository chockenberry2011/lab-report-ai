import React from 'react'
import { SECTION_ORDER, fieldsForSection } from '@/config/fieldSchema'
import { FALLBACK_SECTIONS, FALLBACK_FIELDS } from '@/config/fallbackSchema'
import { SectionCard } from '@/components/editor/SectionCard'
import { FieldRow } from '@/components/editor/FieldRow'
import { ServerUpdatePill } from '@/components/ServerUpdatePill'

interface EditorPaneProps {
  sections: Array<{
    key: string
    title: string
    defs: Array<{
      path: string
      label: string
      input: string
      width?: 'full' | 'half' | 'third'
    }>
  }>
  serverState: Record<string, any>
  serverUpdates: Array<{ field: string; newValue: any; oldValue: any }>
  onFieldChange: (path: string, value: any) => void
  onFieldSave: (path: string) => void
  onFieldReset: (path: string) => void
  onCommitServerUpdate: (field: string) => void
  onDismissServerUpdate: (field: string) => void
  getDraftValue: (path: string) => any
  isDraftDirty: (path: string) => boolean
  showMeta: boolean
}

export function EditorPane({
  sections,
  serverState,
  serverUpdates,
  onFieldChange,
  onFieldSave,
  onFieldReset,
  onCommitServerUpdate,
  onDismissServerUpdate,
  getDraftValue,
  isDraftDirty,
  showMeta
}: EditorPaneProps) {
  return (
    <div className="space-y-6">
      {sections.map(({ key, defs, title }) => {
        if (!defs?.length) {
          return (
            <SectionCard key={key} title={title || `Section ${key}`} subtitle="" description="">
              <div className="text-sm text-gray-500">Nothing to show here yet. You can still add values manually.</div>
            </SectionCard>
          )
        }

        const dirty = defs.some(d => isDraftDirty(d.path))

        return (
          <SectionCard
            key={key}
            title={title || sectionTitleFromKey(key)}
            subtitle={sectionSubtitleFromKey(key)}
            description={sectionDescFromKey(key)}
            dirty={dirty}
            onSaveAll={() => {
              const dirtyPaths = defs.filter(d => isDraftDirty(d.path)).map(d => d.path)
              if (dirtyPaths.length > 0) {
                // This would need to be passed in as a prop if we need save functionality
                console.log('Save all:', dirtyPaths)
              }
            }}
            onResetAll={() => {
              defs.forEach(d => onFieldReset(d.path))
            }}
          >
            <div className="grid grid-cols-12 gap-4">
              {defs.map(def => {
                const serverValue = serverState[def.path] ?? ''
                const draftValue = getDraftValue(def.path)
                const fieldUpdate = serverUpdates.find(u => u.field === def.path)

                return (
                  <div key={def.path} className={widthToCols(def.width)}>
                    <div className="space-y-2">
                      <FieldRow
                        def={def}
                        value={serverValue}
                        draft={draftValue}
                        error={undefined}
                        saving={false}
                        saved={false}
                        onChange={(v) => onFieldChange(def.path, v)}
                        onSave={() => onFieldSave(def.path)}
                        onReset={() => onFieldReset(def.path)}
                        source={showMeta ? undefined : undefined}
                        confidence={showMeta ? undefined : undefined}
                      />

                      {fieldUpdate && (
                        <ServerUpdatePill
                          update={fieldUpdate}
                          onCommit={() => onCommitServerUpdate(def.path)}
                          onDismiss={() => onDismissServerUpdate(def.path)}
                        />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </SectionCard>
        )
      })}
    </div>
  )
}

function widthToCols(w?: 'full' | 'half' | 'third') {
  switch (w) {
    case 'third': return 'col-span-12 md:col-span-4'
    case 'half': return 'col-span-12 md:col-span-6'
    default: return 'col-span-12'
  }
}

function sectionTitleFromKey(k: string) {
  return ({
    A: 'Lab / Vendor Envelope',
    B: 'Patient',
    C: 'Ordering / Provider',
    D: 'Specimen',
    E: 'Report Meta'
  } as any)[k] ?? `Section ${k}`
}

function sectionSubtitleFromKey(_k: string) { return '' }
function sectionDescFromKey(_k: string) { return '' }