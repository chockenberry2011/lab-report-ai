import { Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Layout } from '@/components/Layout'
import InboxPage from '@/pages/InboxPage'
import QueuePage from '@/pages/QueuePage'
import ProcessedPage from '@/pages/ProcessedPage'
import ComparePage from '@/pages/ComparePage'
import NotFoundPage from '@/pages/NotFoundPage'

import { systemApi } from '@/services/api'
import { GlobalErrorBoundary } from '@/app/ErrorBoundary'
import RouteErrorBoundary from '@/components/RouteErrorBoundary'
import { lazyWithReport } from '@/utils/lazyWithReport'

// Lazy-load page components that benefit from code splitting
// Eager import ViewerPage to avoid flaky dynamic chunk loads in some environments
import ViewerPage from '@/pages/ViewerPage'
const ReviewEditorPage = lazyWithReport(
  () => import('@/pages/review/ReviewEditorPage'),
  'ReviewEditorPage'
)

function App() {
  const Spinner = () => (
    <div className="h-full w-full flex items-center justify-center p-6">
      <div className="spinner w-6 h-6" />
    </div>
  )
  // Check system health on app load
  const { isError } = useQuery({
    queryKey: ['health'],
    queryFn: systemApi.health,
    retry: 3,
    staleTime: 60000, // 1 minute
  })

  return (
    <GlobalErrorBoundary>
      <div className="min-h-screen bg-gray-50">
        <Layout>
        {isError && (
          <div className="mb-4 rounded-lg bg-error-50 border border-error-200 p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <span className="text-error-600 text-xl">⚠️</span>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-error-800">
                  System Connection Issues
                </h3>
                <div className="mt-2 text-sm text-error-700">
                  <p>
                    Unable to connect to the Lab AI backend. Please check that the API server is running.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        <Routes>
          <Route path="/" element={<Navigate to="/inbox" replace />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/queue" element={<QueuePage />} />
          <Route path="/processed" element={<ProcessedPage />} />
          <Route
            path="/review/:resultId"
            element={
              <RouteErrorBoundary>
                <Suspense fallback={<Spinner />}>
                  <ReviewEditorPage />
                </Suspense>
              </RouteErrorBoundary>
            }
          />
          <Route
            path="/viewer/:resultId"
            element={
              <RouteErrorBoundary>
                <Suspense fallback={<Spinner />}>
                  <ViewerPage />
                </Suspense>
              </RouteErrorBoundary>
            }
          />
          <Route path="/compare/:jobId" element={<ComparePage />} />
          {/* Fallback route */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </Layout>
      </div>
    </GlobalErrorBoundary>
  )
}

export default App
