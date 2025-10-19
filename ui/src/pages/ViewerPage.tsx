import React, { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import { JSONTree } from 'react-json-tree'
import {
  ArrowLeft,
  Download,
  Edit3,
  Eye,
  EyeOff,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  FileText,
  AlertTriangle,
  RotateCcw,
  BookOpen,
  Code,
  User,
  Building2,
} from 'lucide-react'
import { Api } from '../lib/api'
import { applyCorrections } from '@/utils/applyCorrections'
import { resultsApi, fileApi, downloadFile } from '@/services/api'
import { normalizeAllIds } from '@/lib/normalizeIds'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { EmptyState } from '@/components/EmptyState'
import {
  formatConfidence,
  getConfidenceBadgeClass,
  getConfidenceTextClass,
  analyzeFieldConfidence,
  cn,
} from '@/utils'
import type { LabResult, TestRow, Panel, RefRange } from '@/types'
import { normalizeFlag as normalizeFlagShared, formatReferenceRange as formatReferenceRangeShared } from '@/utils/labFormatters'
import { getFlagBadgeClass } from '@/lib/flag-helpers'
import { jsonTheme } from '@/lib/json-theme'
import type { DocumentInfo, EnhancedDocumentInfo } from '@/types'

// Type guard to check if document_info is DocumentInfo type
function isDocumentInfo(documentInfo: DocumentInfo | EnhancedDocumentInfo): documentInfo is DocumentInfo {
  return 'document_score' in documentInfo && 'needs_review' in documentInfo && 'review_reasons' in documentInfo && 'confidence_distribution' in documentInfo
}

interface LabReportViewProps {
  labResult: LabResult
  selectedPanel?: string
  onPanelSelect: (panelId: string) => void
  showLowConfidence: boolean
  showTechnicalDetails: boolean
  extractedText?: any
  jobId?: string
}

function LabReportView({
  labResult,
  selectedPanel,
  onPanelSelect,
  showLowConfidence,
  showTechnicalDetails,
  extractedText,
  jobId,
}: LabReportViewProps) {
  const [expandedTechnical, setExpandedTechnical] = useState(false)

  // Extract actual patient/lab data from the result
  const patientInfo = {
    name: labResult.document_info?.patient?.first_name && labResult.document_info?.patient?.last_name
      ? `${labResult.document_info.patient.first_name} ${labResult.document_info.patient.last_name}`
      : null,
    dob: labResult.document_info?.patient?.dob || null,
    mrn: labResult.document_info?.patient?.mrn || null,
    sex: labResult.document_info?.patient?.sex || null,
  }

  const labInfo = {
    name: labResult.document_info?.performing_lab?.name || labResult.document_info?.vendor?.name || null,
    reportDate: labResult.document_info?.report?.completed_at || labResult.document_info?.report?.reported_at || null,
    collectionDate: labResult.document_info?.specimen?.collected_at || null,
    orderNumber: labResult.document_info?.specimen?.id || null,
  }

  // Count abnormal results
  const safePanels = Array.isArray(labResult?.lab_panels) ? labResult.lab_panels : []
  const abnormalCount = safePanels.reduce((count, panel) =>
    count + (Array.isArray(panel?.test_rows) ? panel.test_rows : []).filter(test => {
      const flag = normalizeFlagShared(test.flag) || (test.flags && test.flags.length ? normalizeFlagShared(test.flags[0]) : null)
      return flag && ['H', 'HIGH', 'L', 'LOW', 'CRIT', 'ABN'].includes(flag.toUpperCase())
    }).length, 0
  )
  const totalTests = safePanels.reduce((count, panel) => count + ((Array.isArray(panel?.test_rows) ? panel.test_rows : []).length), 0)

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header Cards Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Patient Info Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center mb-3">
            <User size={20} className="text-blue-600 mr-2" />
            <h3 className="font-medium text-gray-900">Patient</h3>
          </div>
          <div className="space-y-1 text-sm">
            <div>
              <span className="font-medium">{patientInfo.name || 'Not specified'}</span>
            </div>
            {patientInfo.dob && (
              <div className="text-gray-600">DOB: {patientInfo.dob}</div>
            )}
            {patientInfo.mrn && (
              <div className="text-gray-600">MRN: {patientInfo.mrn}</div>
            )}
            {patientInfo.sex && (
              <div className="text-gray-600">Sex: {patientInfo.sex}</div>
            )}
          </div>
        </div>

        {/* Lab Info Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center mb-3">
            <Building2 size={20} className="text-green-600 mr-2" />
            <h3 className="font-medium text-gray-900">Laboratory</h3>
          </div>
          <div className="space-y-1 text-sm">
            <div>
              <span className="font-medium">{labInfo.name || 'Not specified'}</span>
            </div>
            {labInfo.reportDate && (
              <div className="text-gray-600">Reported: {new Date(labInfo.reportDate).toLocaleDateString()}</div>
            )}
            {labInfo.collectionDate && (
              <div className="text-gray-600">Collected: {new Date(labInfo.collectionDate).toLocaleDateString()}</div>
            )}
            {labInfo.orderNumber && (
              <div className="text-gray-600">Order: {labInfo.orderNumber}</div>
            )}
          </div>
        </div>

        {/* Results Summary Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center mb-3">
            <FileText size={20} className="text-purple-600 mr-2" />
            <h3 className="font-medium text-gray-900">Results Summary</h3>
          </div>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span>Total Tests:</span>
              <span className="font-medium">{totalTests}</span>
            </div>
            <div className="flex justify-between">
              <span>Abnormal:</span>
              <span className={cn('font-medium', abnormalCount > 0 ? 'text-amber-600' : 'text-green-600')}>
                {abnormalCount}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Panels:</span>
              <span className="font-medium">{safePanels.length}</span>
            </div>
          </div>
        </div>

        {/* Status Card */}
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center mb-3">
            <AlertTriangle size={20} className="text-amber-600 mr-2" />
            <h3 className="font-medium text-gray-900">Status</h3>
          </div>
          <div className="space-y-1 text-sm">
            {isDocumentInfo(labResult.document_info) ? (
              <>
                <div className="flex justify-between">
                  <span>Review Needed:</span>
                  <span className={cn('font-medium', labResult.document_info.needs_review ? 'text-amber-600' : 'text-green-600')}>
                    {labResult.document_info.needs_review ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Confidence:</span>
                  <span className={cn('font-medium', getConfidenceBadgeClass(labResult.document_info.document_score).replace('badge', 'text'))}>
                    {formatConfidence(labResult.document_info.document_score)}
                  </span>
                </div>
              </>
            ) : (
              <div className="text-gray-500">Status information available</div>
            )}
          </div>
        </div>
      </div>

      {/* Lab Results Tables */}
      <div className="space-y-6">
        {safePanels.map((panel, panelIndex) => (
          <div key={panel.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {/* Panel Header */}
            <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{panel.name}</h2>
                  <div className="text-sm text-gray-600 mt-1">
                    {(Array.isArray(panel?.test_rows) ? panel.test_rows : []).length} test{((Array.isArray(panel?.test_rows) ? panel.test_rows : []).length) !== 1 ? 's' : ''}
                    {panel.panel_score !== undefined && (
                      <span className="ml-2">• Confidence: {formatConfidence(panel.panel_score)}</span>
                    )}
                  </div>
                </div>
                {panel.needs_review && (
                  <span className="badge-warning flex items-center space-x-1">
                    <AlertTriangle size={12} />
                    <span>Review Required</span>
                  </span>
                )}
              </div>
            </div>

            {/* Results Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Test Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Result
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Units
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Reference Range
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Flag
                    </th>
                    {showLowConfidence && (
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Confidence
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {(Array.isArray(panel?.test_rows) ? panel.test_rows : []).map((testRow, testIndex) => {
                    const flag = normalizeFlagShared(testRow.flag) || (testRow.flags && testRow.flags.length ? normalizeFlagShared(testRow.flags[0]) : null)
                    const isAbnormal = flag && ['H', 'HIGH', 'L', 'LOW', 'CRIT', 'ABN'].includes(flag.toUpperCase())
                    const isCritical = flag && ['CRIT'].includes(flag.toUpperCase())
                    const isLowConfidence = testRow.confidence < 0.7

                    return (
                      <tr
                        key={testIndex}
                        className={cn(
                          'hover:bg-gray-50',
                          isCritical && 'bg-red-50',
                          isAbnormal && !isCritical && 'bg-amber-50',
                          showLowConfidence && isLowConfidence && 'bg-blue-50'
                        )}
                      >
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="font-medium text-gray-900">
                            {testRow.test_name || '—'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className={cn(
                            'font-medium',
                            isCritical ? 'text-red-700' : isAbnormal ? 'text-amber-700' : 'text-gray-900'
                          )}>
                            {testRow.result_value || '—'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                          {testRow.units || '—'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-gray-600">
                          {(() => {
                            const ref = formatReferenceRangeShared({
                              reference_range_low: testRow.reference_range_low,
                              reference_range_high: testRow.reference_range_high,
                              reference_range_text: testRow.reference_range_text ?? ((testRow.reference_range && typeof testRow.reference_range === 'object') ? (testRow.reference_range as any).text ?? null : null),
                              reference_range: typeof testRow.reference_range === 'string' ? testRow.reference_range : null,
                              units: testRow.units || null,
                            })
                            return ref || '—'
                          })()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {flag ? (
                            <span className={cn(
                              'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                              isCritical ? 'bg-red-100 text-red-800' :
                              isAbnormal ? 'bg-amber-100 text-amber-800' :
                              'bg-gray-100 text-gray-800'
                            )}>
                              {flag}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        {showLowConfidence && (
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={cn('badge', getConfidenceBadgeClass(testRow.confidence))}>
                              {formatConfidence(testRow.confidence)}
                            </span>
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Panel Review Issues */}
            {panel.review_reasons && panel.review_reasons.length > 0 && (
              <div className="px-6 py-4 bg-amber-50 border-t border-amber-200">
                <h6 className="font-medium text-amber-900 mb-2 flex items-center">
                  <AlertTriangle size={14} className="mr-2" />
                  Issues Requiring Review:
                </h6>
                <ul className="text-sm text-amber-800 list-disc list-inside space-y-1">
                  {panel.review_reasons.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Technical Details - Collapsible */}
      {showTechnicalDetails && (
        <div className="bg-white border border-gray-200 rounded-lg">
          <button
            onClick={() => setExpandedTechnical(!expandedTechnical)}
            className="w-full px-6 py-4 text-left hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium text-gray-900">Technical Details</h3>
              <ChevronRight
                size={20}
                className={cn(
                  'transform transition-transform text-gray-400',
                  expandedTechnical && 'rotate-90'
                )}
              />
            </div>
          </button>

          {expandedTechnical && (
            <div className="border-t border-gray-200 p-6">
              <div className="space-y-6">
                {/* Raw JSON */}
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">Raw JSON Data</h4>
                  <div className="bg-gray-50 rounded-lg p-4 overflow-auto max-h-96">
                    <JSONTree
                      data={labResult}
                      theme={jsonTheme}
                      invertTheme={false}
                      hideRoot={true}
                      shouldExpandNodeInitially={(keyPath, data, level) => level < 2}
                    />
                  </div>
                </div>

                {/* Extracted Text */}
                {extractedText && (
                  <div>
                    <h4 className="font-medium text-gray-900 mb-3">Extracted Text</h4>
                    <div className="bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
                      {extractedText.pages?.map((page: any, pageIndex: number) => (
                        <div key={pageIndex} className="mb-4">
                          <h5 className="font-medium text-gray-700 mb-2">Page {page.page}</h5>
                          <div className="space-y-1 font-mono text-sm text-gray-600">
                            {page.lines?.map((line: any, lineIndex: number) => (
                              <div key={lineIndex} className="flex">
                                <span className="w-16 text-gray-400">{lineIndex + 1}:</span>
                                <span>{line.text}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ViewerPage() {
  const { resultId: paramId } = useParams<{ resultId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedPage, setSelectedPage] = useState(1)
  const [selectedPanel, setSelectedPanel] = useState<string>('')
  const [showLowConfidence, setShowLowConfidence] = useState(true)
  const [showBusinessView, setShowBusinessView] = useState(true)

  // Parse IDs for proper API endpoint routing
  const { slugFull, baseId } = useMemo(() => {
    return normalizeAllIds(paramId || '')
  }, [paramId])
  const jobId = baseId // Use baseId for API calls that expect the normalized ID

  // Manual extracted text fetching with resilient error handling
  const [extractedText, setExtractedText] = useState<any>(null)
  const [extractedTextLoading, setExtractedTextLoading] = useState(true)
  const [extractedTextNotFound, setExtractedTextNotFound] = useState(false)
  const [extractedTextError, setExtractedTextError] = useState<string | null>(null)

  // Function to handle extracted text fetching
  const fetchExtractedText = async (idToTry: string, isRetry = false) => {
    if (!isRetry) {
      setExtractedTextLoading(true)
      setExtractedTextNotFound(false)
      setExtractedTextError(null)
    }

    try {
      const result = await fileApi.getFile(idToTry, 'extracted-text')
      if (result?.pages?.length) {
        setExtractedText(result)
        setExtractedTextNotFound(false)
        setExtractedTextError(null)
        return true
      }
    } catch (error: any) {
      console.warn(`Failed to fetch extracted text for ${idToTry}:`, error)
      if (error?.status === 404) {
        setExtractedTextNotFound(true)
      } else {
        setExtractedTextError(error?.message || 'Failed to load extracted text')
      }
    }
    return false
  }

  // Retry function for extracted text
  const retryExtractedText = async () => {
    if (!jobId) return

    setExtractedTextLoading(true)
    setExtractedTextError(null)

    // Try multiple ID formats on retry
    const idsToTry = [
      jobId,
      slugFull,
      `${jobId}.03_compose.debug`,
      `${baseId}.03_compose.debug`
    ].filter(Boolean)

    for (const id of idsToTry) {
      const success = await fetchExtractedText(id, true)
      if (success) break
    }

    setExtractedTextLoading(false)
  }

  // Effect to load extracted text
  React.useEffect(() => {
    if (!jobId) return

    const loadExtractedText = async () => {
      // Try primary ID first
      let success = await fetchExtractedText(jobId)

      // If not found, try with .debug suffix
      if (!success && !extractedTextNotFound) {
        success = await fetchExtractedText(`${jobId}.03_compose.debug`)
      }

      setExtractedTextLoading(false)
    }

    loadExtractedText()
  }, [jobId, baseId, slugFull])

  // Lab result query - using jobId (baseId) which is correct for API
  const {
    data: labResult,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['lab-result', jobId],
    queryFn: () => resultsApi.getResult(jobId || ''),
    enabled: !!jobId,
    staleTime: 30000,
    retry: (failureCount, error: any) => {
      // Don't retry on 404 errors
      if (error?.status === 404) return false
      return failureCount < 3
    },
    meta: {
      errorMessage: `Failed to load result for ${jobId?.slice(0, 8)}...`
    }
  })

  // Download handler
  const handleDownload = async () => {
    if (!jobId) return

    try {
      await downloadFile(jobId, 'canonical', `lab-result-${jobId.slice(0, 8)}.json`)
      toast.success('Download started')
    } catch (error) {
      console.error('Download failed:', error)
      toast.error('Download failed')
    }
  }

  // Refresh handler
  const refreshResult = () => {
    if (jobId) {
      queryClient.invalidateQueries({ queryKey: ['lab-result', jobId] })
      refetch()
    }
  }

  // Set first panel as selected by default
  React.useEffect(() => {
    if (labResult?.lab_panels?.length > 0 && !selectedPanel) {
      setSelectedPanel(labResult.lab_panels[0].id)
    }
  }, [labResult, selectedPanel])

  if (error) {
    console.error('ViewerPage error:', error)
    return (
      <ErrorBoundary>
        <div className="flex items-center justify-center min-h-96">
          <EmptyState
            title="Failed to load result"
            description={`Could not load result for ID: ${paramId?.slice(0, 8)}...`}
            actionText="Try Again"
            onAction={refreshResult}
          />
        </div>
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="h-full flex flex-col bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/processed')}
                className="btn-ghost flex items-center space-x-2"
                aria-label="Back to processed results"
              >
                <ArrowLeft size={16} />
                <span>Back to Results</span>
              </button>

              <div className="flex items-center space-x-3">
                <h1 className="text-xl font-semibold text-gray-900">Lab Report Viewer</h1>
                {jobId && (
                  <span className="text-sm text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    {jobId.slice(0, 8)}...
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <button
                onClick={() => setShowLowConfidence(!showLowConfidence)}
                className={cn(
                  'btn-ghost flex items-center space-x-2',
                  showLowConfidence && 'bg-yellow-50 text-yellow-700'
                )}
              >
                {showLowConfidence ? <EyeOff size={16} /> : <Eye size={16} />}
                <span>Highlight Low Confidence</span>
              </button>

              <button
                onClick={() => setShowBusinessView(!showBusinessView)}
                className={cn(
                  'btn-ghost flex items-center space-x-2',
                  !showBusinessView && 'bg-blue-50 text-blue-700'
                )}
                title={showBusinessView ? 'Switch to technical view' : 'Switch to business view'}
              >
                {showBusinessView ? <Code size={16} /> : <BookOpen size={16} />}
                <span>{showBusinessView ? 'Technical' : 'Business'} View</span>
              </button>

              <button
                onClick={refreshResult}
                className="btn-ghost flex items-center space-x-2"
                title="Refresh structured result"
              >
                <RotateCcw size={16} />
                <span>Refresh</span>
              </button>

              <button
                onClick={handleDownload}
                disabled={isLoading}
                className="btn-ghost flex items-center space-x-2"
              >
                <Download size={16} />
                <span>Download</span>
              </button>

              <button
                onClick={() => {
                  // Always route Review to base ID (no .debug suffix)
                  navigate(`/review/${jobId}`)
                }}
                className="btn-primary flex items-center space-x-2"
                title={`Review and edit result ${jobId?.slice(0, 8)}...`}
                aria-label={`Review and edit result ${jobId?.slice(0, 8)}...`}
              >
                <Edit3 size={16} />
                <span>Review & Edit</span>
              </button>
            </div>
          </div>
        </div>

        {/* Main content - Full width lab report */}
        <div className="flex-1 overflow-y-auto">
          {labResult ? (
            <LabReportView
              labResult={labResult}
              selectedPanel={selectedPanel}
              onPanelSelect={setSelectedPanel}
              showLowConfidence={showLowConfidence}
              showTechnicalDetails={!showBusinessView}
              extractedText={extractedText}
              jobId={jobId}
            />
          ) : (
            <div className="flex items-center justify-center h-64">
              <div className="spinner w-8 h-8" />
            </div>
          )}
        </div>
      </div>
    </ErrorBoundary>
  )
}
