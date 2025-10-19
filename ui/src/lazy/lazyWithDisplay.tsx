import React from 'react';

export function lazyWithDisplay<T extends React.ComponentType<any>>(
  loader: () => Promise<{ default: T }>,
  name = 'LazyChunk'
) {
  return React.lazy(() =>
    loader().catch((e) => {
      // Make the real cause visible on screen and console
      const msg = (e && (e.stack || e.message || String(e))) || 'unknown error';
      (window as any).__lastLazyError = e;
      console.error(`[${name}] dynamic import failed:`, e);
      // Re-throw so our ErrorBoundary renders
      throw e;
    })
  );
}