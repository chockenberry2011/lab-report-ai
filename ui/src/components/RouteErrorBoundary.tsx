import React from 'react';

// make sure this compiles even if window is undefined during SSR
declare global {
  interface Window { __lastLazyError?: unknown }
}

type Props = { children: React.ReactNode };
type State = { error: any | null };

export default class RouteErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: any) {
    return { error };
  }

  componentDidCatch(error: any, info: any) {
    // expose **exact** lazy error object for debugging
    if (typeof window !== 'undefined') {
      (window as any).__lastLazyError = error;
      // also log a structured snapshot
      // eslint-disable-next-line no-console
      console.error('[RouteErrorBoundary] lazy error snapshot:', {
        message: error?.message,
        name: error?.name,
        stack: error?.stack,
        cause: error?.cause,
        keys: error ? Object.keys(error) : [],
      }, '\ncomponentStack:', info?.componentStack);
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="p-6">
          <h1 className="text-xl font-semibold">Module failed to load</h1>
          <p className="mt-2 text-sm opacity-80">
            Open DevTools → Console and run <code>window.__lastLazyError</code>.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

// Also export as named export for compatibility
export { RouteErrorBoundary };