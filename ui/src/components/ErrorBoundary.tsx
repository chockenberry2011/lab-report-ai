import React from 'react';
import { NotFoundError, HttpError } from '@/lib/errors'

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  copied?: boolean;
  showDev?: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    // Do not render fallback for known 404s from server
    if (error instanceof NotFoundError) return { hasError: false } as State
    if (error instanceof HttpError && (error as HttpError).status === 404) return { hasError: false } as State
    // Some libs wrap status codes on the error object
    const anyErr: any = error as any
    if (anyErr?.status === 404 || anyErr?.response?.status === 404) return { hasError: false } as State
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    try {
      // Log with requested signature
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary]', { path: window.location?.pathname, error, stack: error?.stack })
    } catch {}
  }

  render() {
    if (this.state.hasError) {
      const path = typeof window !== 'undefined' ? window.location?.pathname : ''
      const stack = this.state.error?.stack || ''
      const stackLines = stack.split('\n').slice(0, 5).join('\n')
      const details = `Path: ${path}\nMessage: ${this.state.error?.message}\nStack:\n${stackLines}`

      const onCopy = async () => {
        try {
          await navigator.clipboard.writeText(details)
          this.setState({ copied: true })
          setTimeout(() => this.setState({ copied: false }), 1500)
        } catch (e) {
          // Fallback: log to console so user can copy
          // eslint-disable-next-line no-console
          console.error('Copy failed, details:', details)
        }
      }
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Something went wrong</h2>
            <p className="text-gray-600 mb-4">
              We're sorry, but something unexpected happened. Please try going back and trying again.
            </p>
            <div className="text-xs text-gray-700 mb-3">
              <div className="mb-1"><span className="font-medium">Path:</span> <code>{path}</code></div>
              {this.state.error?.message && (
                <div className="mb-1"><span className="font-medium">Message:</span> {this.state.error.message}</div>
              )}
              {stackLines && (
                <div>
                  <div className="font-medium">Stack (top):</div>
                  <pre className="text-[11px] bg-gray-100 p-2 rounded overflow-auto max-h-40 whitespace-pre-wrap break-words">{stackLines}</pre>
                </div>
              )}
              {process.env.NODE_ENV !== 'production' && this.state.error?.stack && (
                <div className="mt-2">
                  <button
                    onClick={() => this.setState({ showDev: !this.state.showDev })}
                    className="text-xs text-gray-600 underline"
                  >
                    {this.state.showDev ? 'Hide developer details' : 'Show developer details'}
                  </button>
                  {this.state.showDev && (
                    <pre className="mt-2 text-[11px] bg-gray-100 p-2 rounded overflow-auto max-h-64 whitespace-pre-wrap break-words">
                      {this.state.error.stack}
                    </pre>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={onCopy}
                className="flex-1 bg-gray-100 text-gray-800 py-2 px-4 rounded hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-300"
              >
                {this.state.copied ? 'Copied!' : 'Copy details'}
              </button>
            <button
              onClick={() => window.history.back()}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Go back
            </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
