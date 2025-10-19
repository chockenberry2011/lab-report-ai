import { useState } from "react";
import { saveCorrections } from "../lib/corrections";

type Props = {
  resultId: string;
  path: string;              // e.g. "patient.first_name"
  label: string;
  value: any;
  placeholder?: string;
  type?: "text" | "number" | "date" | "tel";
  onLocalChange?: (v:any)=>void; // optional optimistic update
};

export function EditableField({ resultId, path, label, value, placeholder, type="text", onLocalChange }: Props) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState(value ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string|undefined>();

  const save = async (next: any) => {
    setSaving(true); setErr(undefined);
    try {
      await saveCorrections(resultId, [{ path, value: next }]); // op defaults to "set"
      onLocalChange?.(next);
      setEditing(false);
    } catch(e:any) {
      setErr(e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const unset = async () => {
    setSaving(true); setErr(undefined);
    try {
      await saveCorrections(resultId, [{ op:"unset", path }]);
      onLocalChange?.(undefined);
      setEditing(false);
    } catch(e:any) {
      setErr(e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex items-start gap-2 py-2">
      <div className="w-56 text-sm text-gray-500">{label}</div>
      {!editing ? (
        <div className="flex-1 flex items-center gap-2">
          <div className="text-sm">{value ?? <span className="italic text-gray-400">{placeholder || "—"}</span>}</div>
          <button className="text-xs underline" onClick={()=>{ setLocal(value ?? ""); setEditing(true); }}>Edit</button>
        </div>
      ) : (
        <div className="flex-1 flex items-center gap-2">
          <input className="border rounded px-2 py-1 text-sm w-full"
                 type={type} value={local ?? ""} placeholder={placeholder}
                 onChange={(e)=>setLocal(e.target.value)} />
          <button className="text-xs px-2 py-1 border rounded" disabled={saving} onClick={()=>save(local)}>Save</button>
          <button className="text-xs px-2 py-1" disabled={saving} onClick={()=>setEditing(false)}>Cancel</button>
          <button className="text-xs text-red-600 underline" disabled={saving} onClick={unset}>Unset</button>
          {err && <div className="text-xs text-red-600">{err}</div>}
        </div>
      )}
    </div>
  );
}