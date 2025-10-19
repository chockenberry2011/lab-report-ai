import * as React from 'react';

export default function ReviewEditorPage() {
  const [Core, setCore] = React.useState<null | React.ComponentType>(null);
  const [err, setErr]   = React.useState<any>(null);

  React.useEffect(() => {
    let mounted = true;
    import('./ReviewEditorCore')
      .then(m => { if (mounted) setCore(() => m.default); })
      .catch(e => {
        if (typeof window !== 'undefined') {
          (window as any).__lastLazyError = e;
        }
        if (mounted) setErr(e);
      });
    return () => { mounted = false; };
  }, []);

  if (err) {
    return <div style={{padding:16}}>Module failed to load: {String(err)}.</div>;
  }
  if (!Core) return <div style={{padding:16}}>Loading editor…</div>;
  return <Core />;
}

