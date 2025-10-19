import React, { lazy } from 'react';

declare global {
  interface Window { __lastLazyError?: unknown }
}

export function lazyWithReport<T extends React.ComponentType<any>>(
  importer: () => Promise<{ default: T }>,
  label: string
) {
  return lazy(async () => {
    try {
      return await importer();
    } catch (err) {
      if (typeof window !== 'undefined') {
        (window as any).__lastLazyError = { label, err };
        // eslint-disable-next-line no-console
        console.error(`[lazyWithReport] failed to load ${label}`, err);
      }
      throw err;
    }
  });
}