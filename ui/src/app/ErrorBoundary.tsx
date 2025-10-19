import { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
  errorInfo?: ErrorInfo
}

export class GlobalErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Global Error Boundary caught an error:', error, errorInfo)
    this.setState({ error, errorInfo })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
          <div className="max-w-2xl w-full bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center space-x-3 mb-4">
              <AlertTriangle className="w-8 h-8 text-red-500" />
              <h1 className="text-xl font-semibold text-gray-900">
                Application Error
              </h1>
            </div>

            <div className="space-y-4">
              <p className="text-gray-600">
                Something went wrong. This is likely a TDZ (Temporal Dead Zone) error
                or undefined variable reference.
              </p>

              <div className="bg-red-50 border border-red-200 rounded p-4">
                <h3 className="font-medium text-red-900 mb-2">Error Details:</h3>
                <p className="text-red-800 font-mono text-sm">
                  {this.state.error?.message}
                </p>
              </div>

              {this.state.errorInfo && (
                <details className="bg-gray-50 border border-gray-200 rounded p-4">
                  <summary className="cursor-pointer font-medium text-gray-900 mb-2">
                    Stack Trace
                  </summary>
                  <pre className="text-xs text-gray-700 overflow-auto">
                    {this.state.errorInfo.componentStack}
                  </pre>
                </details>
              )}

              <div className="flex space-x-3">
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  Reload Page
                </button>
                <button
                  onClick={() => window.history.back()}
                  className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
                >
                  Go Back
                </button>
              </div>

              <div className="text-sm text-gray-500">
                <p>Current route: <code className="bg-gray-100 px-1 rounded">{window.location.pathname}</code></p>
                <p>If this error persists, check the browser console for more details.</p>
              </div>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}