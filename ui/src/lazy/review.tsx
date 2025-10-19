import React from 'react';

export function lazyWithLog<T extends React.ComponentType<any>>(loader: () => Promise<{ default: T }>) {
  return React.lazy(() =>
    loader().catch((e) => {
      console.error('[Review lazy] Failed to load module:', e);
      throw e;
    })
  );
}