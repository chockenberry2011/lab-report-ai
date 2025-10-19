import { useState, useEffect, useMemo } from 'react'
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
import { normalizeResultId, ensureViewerId } from '@/lib/normalizeIds'
import { getJSON } from '@/lib/http'
import { NotFoundError, HttpError } from '@/lib/errors'
import { parseResultIds, getReviewUrl } from '@/utils/ids'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { EmptyState } from '@/components/EmptyState'
import {
  formatConfidence,
  getConfidenceTextClass,
  getConfidenceBadgeClass,
  analyzeFieldConfidence,
  cn,
} from '@/utils'
import type { LabResult, TestRow, Panel, RefRange } from '@/types'
import { normalizeFlag as normalizeFlagShared, formatReferenceRange as formatReferenceRangeShared } from '@/utils/labFormatters'
import { getFlagBadgeClass } from '@/lib/flag-helpers'
import { jsonTheme } from '@/lib/json-theme'
import HeaderCards from '@/components/HeaderCards'
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
  const abnormalCount = labResult.lab_panels.reduce((count, panel) =>
    count + panel.test_rows.filter(test => {
      const flag = normalizeFlagShared(test.flag) || (test.flags && test.flags.length ? normalizeFlagShared(test.flags[0]) : null)
      return flag && ['H', 'HIGH', 'L', 'LOW', 'CRIT', 'ABN'].includes(flag.toUpperCase())
    }).length, 0
  )

  const totalTests = labResult.lab_panels.reduce((count, panel) => count + panel.test_rows.length, 0)

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
              <span className="font-medium">{labResult.lab_panels.length}</span>
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
        {labResult.lab_panels.map((panel, panelIndex) => (
          <div key={panel.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            {/* Panel Header */}
            <div className="bg-gray-50 px-6 py-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{panel.name}</h2>
                  <div className="text-sm text-gray-600 mt-1">
                    {panel.test_rows.length} test{panel.test_rows.length !== 1 ? 's' : ''}
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
                  {panel.test_rows.map((testRow, testIndex) => {
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
                              reference_range_text: testRow.reference_range_text ?? (typeof testRow.reference_range === 'object' ? (testRow.reference_range as any).text ?? null : null),
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
  const { fullId, baseId } = useMemo(() => {
    return parseResultIds(paramId)
  }, [paramId])
          <div>
            <h5 className={cn(
              'font-medium',
              shouldHighlight && isLowConfidence ? 'text-warning-900' : 'text-gray-900'
            )}>
              {testRow.test_name || 'Unknown Test'}
            </h5>
            {testRow.result_value && (
              <div className="text-sm text-gray-600 mt-1">
                <span className="font-medium">{testRow.result_value}</span>
                {testRow.units && <span className="ml-1">{testRow.units}</span>}
                {(testRow.reference_range || testRow.reference_range_text || (testRow.reference_range_low != null && testRow.reference_range_high != null)) && (
                  <span className="ml-2 text-gray-500">
                    {(() => {
                      const ref = formatReferenceRangeShared({
                        reference_range_low: testRow.reference_range_low,
                        reference_range_high: testRow.reference_range_high,
                        reference_range_text: testRow.reference_range_text ?? (typeof testRow.reference_range === 'object' ? (testRow.reference_range as any).text ?? null : null),
                        reference_range: typeof testRow.reference_range === 'string' ? testRow.reference_range : null,
                        units: testRow.units || null,
                      })
                      return ref ? `(Ref: ${ref})` : ''
                    })()}
                  </span>
                )}
                {(() => {
                  const flag = normalizeFlagShared(testRow.flag) || (testRow.flags && testRow.flags.length ? normalizeFlagShared(testRow.flags[0]) : null)
                  return flag ? (
                    <span className={`ml-2 ${getFlagBadgeClass(flag)}`}>{flag}</span>
                  ) : null
                })()}
              </div>
            )}
          </div>
          
          <div className="flex items-center space-x-2">
            <span className={cn('badge', getConfidenceBadgeClass(testRow.confidence))}>
              {formatConfidence(testRow.confidence)}
            </span>
          </div>
        </div>

        {showLowConfidence && analysis && (
          <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-gray-600">Value:</span>
                <span className={cn('ml-1', getConfidenceBadgeClass(testRow.field_confidences.value_parse))}>
                  {formatConfidence(testRow.field_confidences.value_parse)}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Unit:</span>
                <span className={cn('ml-1', getConfidenceBadgeClass(testRow.field_confidences.unit_validity))}>
                  {formatConfidence(testRow.field_confidences.unit_validity)}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Range:</span>
                <span className={cn('ml-1', getConfidenceBadgeClass(testRow.field_confidences.reference_range))}>
                  {formatConfidence(testRow.field_confidences.reference_range)}
                </span>
              </div>
              <div>
                <span className="text-gray-600">Name:</span>
                <span className={cn('ml-1', getConfidenceBadgeClass(testRow.field_confidences.test_name_clarity))}>
                  {formatConfidence(testRow.field_confidences.test_name_clarity)}
                </span>
              </div>
            </div>
            {analysis.issues.length > 0 && (
              <div className="mt-2 text-warning-700">
                <AlertTriangle size={12} className="inline mr-1" />
                {analysis.issues.join(', ')}
              </div>
            )}
          </div>
        )}

        <div className="mt-2 text-xs text-gray-500">
          Page {testRow.page}, Line {testRow.line_number}
        </div>
      </div>
    )
  }

  const renderPanel = (panel: Panel) => {
    const isSelected = selectedPanel === panel.id
    const isLowConfidence = panel.panel_score !== undefined && panel.panel_score < 0.7
    const shouldHighlight = showLowConfidence && (panel.needs_review || isLowConfidence)

    return (
      <div key={panel.id} className="mb-6">
        <div
          className={cn(
            'flex items-center justify-between p-3 border rounded-lg cursor-pointer',
            isSelected ? 'border-primary-500 bg-primary-50' : 'border-gray-200',
            shouldHighlight && 'border-warning-300 bg-warning-50',
            'hover:shadow-sm transition-all'
          )}
          onClick={() => onPanelSelect(panel.id)}
        >
          <div>
            <h4 className={cn(
              'font-medium',
              isSelected ? 'text-primary-900' : 'text-gray-900',
              shouldHighlight && 'text-warning-900'
            )}>
              {panel.name}
            </h4>
            <div className="text-sm text-gray-600 mt-1">
              {panel.test_rows.length} test{panel.test_rows.length !== 1 ? 's' : ''}
              {panel.panel_score !== undefined && (
                <span className="ml-2">
                  Score: {formatConfidence(panel.panel_score)}
                </span>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            {panel.needs_review && (
              <span className="badge-warning flex items-center space-x-1">
                <AlertTriangle size={12} />
                <span>Review</span>
              </span>
            )}
            {panel.panel_score !== undefined && (
              <span className={cn('badge', getConfidenceBadgeClass(panel.panel_score))}>
                {formatConfidence(panel.panel_score)}
              </span>
            )}
          </div>
        </div>

        {isSelected && (
          <div className="mt-4 space-y-3">
            {panel.test_rows.map((testRow, index) => renderTestRow(testRow, index))}
            
            {panel.review_reasons && panel.review_reasons.length > 0 && (
              <div className="p-3 bg-warning-50 border border-warning-200 rounded-lg">
                <h6 className="font-medium text-warning-900 mb-2">Review Issues:</h6>
                <ul className="text-sm text-warning-800 list-disc list-inside">
                  {panel.review_reasons.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  if (showBusinessView) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex-1 p-4 overflow-y-auto scrollbar-thin">
          <div className="space-y-6">
            {/* Header Cards with enhanced document info */}
            {(() => {
              const info = labResult.document_info as EnhancedDocumentInfo | undefined
              const hasEnhanced = info && (
                !!info.patient ||
                !!info.specimen ||
                !!info.performing_lab ||
                !!info.vendor ||
                !!info.ordering ||
                !!info.report
              )
              return hasEnhanced ? (
                <HeaderCards documentInfo={info} className="mb-6" />
              ) : (
                <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <div className="text-center text-blue-800">
                    <h3 className="font-medium">Lab Report Viewer</h3>
                    <p className="text-sm mt-1">Enhanced patient and lab information will appear here when available</p>
                  </div>
                </div>
              )
            })()}

            {/* Document Summary */}
            <div>
              <button
                onClick={() => toggleSection('summary')}
                className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <h3 className="text-lg font-medium text-gray-900">Report Summary</h3>
                <ChevronRight
                  size={16}
                  className={cn(
                    'transform transition-transform',
                    expandedSections.has('summary') && 'rotate-90'
                  )}
                />
              </button>

              {expandedSections.has('summary') && (
                <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="text-center p-3 bg-blue-50 rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">{labResult.lab_panels.length}</div>
                      <div className="text-blue-800">Panel{labResult.lab_panels.length !== 1 ? 's' : ''}</div>
                    </div>
                    <div className="text-center p-3 bg-green-50 rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {labResult.lab_panels.reduce((sum, panel) => sum + panel.test_rows.length, 0)}
                      </div>
                      <div className="text-green-800">Total Tests</div>
                    </div>
                    {isDocumentInfo(labResult.document_info) && (
                      <>
                        <div className="text-center p-3 bg-purple-50 rounded-lg">
                          <div className={cn('text-2xl font-bold', getConfidenceBadgeClass(labResult.document_info.document_score).replace('badge', 'text'))}>
                            {formatConfidence(labResult.document_info.document_score)}
                          </div>
                          <div className="text-purple-800">Confidence</div>
                        </div>
                        <div className="text-center p-3 bg-amber-50 rounded-lg">
                          <div className={cn('text-2xl font-bold', labResult.document_info.needs_review ? 'text-amber-600' : 'text-green-600')}>
                            {labResult.document_info.needs_review ? 'Review' : 'Ready'}
                          </div>
                          <div className="text-amber-800">Status</div>
                        </div>
                      </>
                    )}
                  </div>

                  {isDocumentInfo(labResult.document_info) && labResult.document_info.review_reasons && labResult.document_info.review_reasons.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <h5 className="font-medium text-amber-900 mb-2 flex items-center">
                        <AlertTriangle size={16} className="mr-2" />
                        Items Needing Review:
                      </h5>
                      <ul className="text-sm text-amber-800 list-disc list-inside space-y-1">
                        {labResult.document_info.review_reasons.map((reason, index) => (
                          <li key={index}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Lab Results by Panel */}
            <div>
              <button
                onClick={() => toggleSection('results')}
                className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <h3 className="text-lg font-medium text-gray-900">Lab Results</h3>
                <ChevronRight
                  size={16}
                  className={cn(
                    'transform transition-transform',
                    expandedSections.has('results') && 'rotate-90'
                  )}
                />
              </button>

              {expandedSections.has('results') && (
                <div className="mt-3 space-y-4">
                  {labResult.lab_panels.map((panel, panelIndex) => (
                    <div
                      key={panel.id}
                      className={cn(
                        'border rounded-lg bg-white',
                        selectedPanel === panel.id ? 'border-primary-300 shadow-sm' : 'border-gray-200'
                      )}
                    >
                      {/* Panel Header */}
                      <button
                        onClick={() => onPanelSelect(panel.id)}
                        className="w-full p-4 text-left hover:bg-gray-50 transition-colors rounded-t-lg"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-medium text-gray-900">{panel.name}</h4>
                            <div className="text-sm text-gray-600 mt-1">
                              {panel.test_rows.length} test{panel.test_rows.length !== 1 ? 's' : ''}
                              {panel.panel_score !== undefined && (
                                <span className="ml-2">
                                  • Score: {formatConfidence(panel.panel_score)}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            {panel.needs_review && (
                              <span className="badge-warning flex items-center space-x-1">
                                <AlertTriangle size={12} />
                                <span>Review</span>
                              </span>
                            )}
                            <ChevronRight
                              size={16}
                              className={cn(
                                'transform transition-transform text-gray-400',
                                selectedPanel === panel.id && 'rotate-90'
                              )}
                            />
                          </div>
                        </div>
                      </button>

                      {/* Panel Tests */}
                      {selectedPanel === panel.id && (
                        <div className="border-t border-gray-200">
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead className="bg-gray-50">
                                <tr>
                                  <th className="px-4 py-2 text-left font-medium text-gray-700">Test</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-700">Result</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-700">Units</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-700">Reference Range</th>
                                  <th className="px-4 py-2 text-left font-medium text-gray-700">Flag</th>
                                  {showLowConfidence && (
                                    <th className="px-4 py-2 text-left font-medium text-gray-700">Confidence</th>
                                  )}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-200">
                                {panel.test_rows.map((testRow, testIndex) => {
                                  const isLowConfidence = testRow.confidence < 0.7
                                  const shouldHighlight = showLowConfidence && isLowConfidence
                                  const flag = normalizeFlagShared(testRow.flag) || (testRow.flags && testRow.flags.length ? normalizeFlagShared(testRow.flags[0]) : null)

                                  return (
                                    <tr
                                      key={testIndex}
                                      className={cn(
                                        'hover:bg-gray-50',
                                        shouldHighlight && 'bg-warning-50'
                                      )}
                                    >
                                      <td className="px-4 py-3 font-medium text-gray-900">
                                        {testRow.test_name || '—'}
                                      </td>
                                      <td className="px-4 py-3">
                                        {testRow.result_value || '—'}
                                      </td>
                                      <td className="px-4 py-3">
                                        {testRow.units || '—'}
                                      </td>
                                      <td className="px-4 py-3 text-gray-600">
                                        {(() => {
                                          const ref = formatReferenceRangeShared({
                                            reference_range_low: testRow.reference_range_low,
                                            reference_range_high: testRow.reference_range_high,
                                            reference_range_text: testRow.reference_range_text ?? (typeof testRow.reference_range === 'object' ? (testRow.reference_range as any).text ?? null : null),
                                            reference_range: typeof testRow.reference_range === 'string' ? testRow.reference_range : null,
                                            units: testRow.units || null,
                                          })
                                          return ref || '—'
                                        })()}
                                      </td>
                                      <td className="px-4 py-3">
                                        {flag ? (
                                          <span className={getFlagBadgeClass(flag)} title={`Flag: ${flag}`}>
                                            {flag}
                                          </span>
                                        ) : (
                                          '—'
                                        )}
                                      </td>
                                      {showLowConfidence && (
                                        <td className="px-4 py-3">
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

                          {panel.review_reasons && panel.review_reasons.length > 0 && (
                            <div className="p-4 bg-warning-50 border-t border-warning-200">
                              <h6 className="font-medium text-warning-900 mb-2 flex items-center">
                                <AlertTriangle size={14} className="mr-2" />
                                Panel Review Issues:
                              </h6>
                              <ul className="text-sm text-warning-800 list-disc list-inside space-y-1">
                                {panel.review_reasons.map((reason, index) => (
                                  <li key={index}>{reason}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Technical/Raw View (existing implementation)
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 p-4 overflow-y-auto scrollbar-thin">
        <div className="space-y-6">
          {/* Document Info */}
          <div>
            <button
              onClick={() => toggleSection('document')}
              className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <h3 className="text-lg font-medium text-gray-900">Document Information</h3>
              <ChevronRight
                size={16}
                className={cn(
                  'transform transition-transform',
                  expandedSections.has('document') && 'rotate-90'
                )}
              />
            </button>

            {expandedSections.has('document') && (
              <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg">
                {isDocumentInfo(labResult.document_info) ? (
                  <>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600">Document Score:</span>
                        <span className={cn('ml-2 badge', getConfidenceBadgeClass(labResult.document_info.document_score))}>
                          {formatConfidence(labResult.document_info.document_score)}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Needs Review:</span>
                        <span className="ml-2">
                          {labResult.document_info.needs_review ?
                            <span className="badge-warning">Yes</span> :
                            <span className="badge-success">No</span>
                          }
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Total Panels:</span>
                        <span className="ml-2 font-medium">{labResult.document_info.total_panels}</span>
                      </div>
                      <div>
                        <span className="text-gray-600">Total Tests:</span>
                        <span className="ml-2 font-medium">{labResult.document_info.total_tests}</span>
                      </div>
                    </div>

                    {isDocumentInfo(labResult.document_info) && labResult.document_info.confidence_distribution && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <h5 className="font-medium text-gray-900 mb-2">Confidence Distribution</h5>
                        <div className="grid grid-cols-3 gap-4 text-sm">
                          <div>Mean: {formatConfidence(labResult.document_info.confidence_distribution.mean)}</div>
                          <div>Min: {formatConfidence(labResult.document_info.confidence_distribution.min)}</div>
                          <div>Max: {formatConfidence(labResult.document_info.confidence_distribution.max)}</div>
                        </div>
                      </div>
                    )}

                    {isDocumentInfo(labResult.document_info) && labResult.document_info.review_reasons && labResult.document_info.review_reasons.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-200">
                        <h5 className="font-medium text-warning-900 mb-2">Review Reasons:</h5>
                        <ul className="text-sm text-warning-800 list-disc list-inside">
                          {labResult.document_info.review_reasons.map((reason, index) => (
                            <li key={index}>{reason}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>Enhanced document information is available but not displayed in this format.</p>
                    <p className="text-sm mt-1">Use the Raw JSON section below to view all document details.</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Lab Panels */}
          <div>
            <button
              onClick={() => toggleSection('panels')}
              className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <h3 className="text-lg font-medium text-gray-900">Lab Panels</h3>
              <ChevronRight
                size={16}
                className={cn(
                  'transform transition-transform',
                  expandedSections.has('panels') && 'rotate-90'
                )}
              />
            </button>

            {expandedSections.has('panels') && (
              <div className="mt-3">
                {labResult.lab_panels.map(renderPanel)}
              </div>
            )}
          </div>

          {/* Raw JSON */}
          <div>
            <button
              onClick={() => toggleSection('json')}
              className="flex items-center justify-between w-full p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <h3 className="text-lg font-medium text-gray-900">Raw JSON</h3>
              <ChevronRight
                size={16}
                className={cn(
                  'transform transition-transform',
                  expandedSections.has('json') && 'rotate-90'
                )}
              />
            </button>

            {expandedSections.has('json') && (
              <div className="mt-3 p-4 bg-white border border-gray-200 rounded-lg overflow-auto">
                <JSONTree
                  data={labResult}
                  theme={jsonTheme}
                  invertTheme={false}
                  hideRoot={true}
                  shouldExpandNodeInitially={(keyPath, data, level) => level < 2}
                />
              </div>
            )}
          </div>
        </div>
      </div>
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
  const { fullId, baseId } = useMemo(() => {
    return parseResultIds(paramId)
  }, [paramId])
  const jobId = baseId // Use baseId for API calls that expect the normalized ID

  // Manual extracted text fetching with resilient error handling
  const [extractedText, setExtractedText] = useState<any>(null)
  const [extractedTextLoading, setExtractedTextLoading] = useState(true)
  const [extractedTextNotFound, setExtractedTextNotFound] = useState(false)
  const [extractedTextError, setExtractedTextError] = useState<string | null>(null)

  // Fetch lab result data
  const { data: baseLabResult, isLoading, error } = useQuery({
    queryKey: ['lab-result', jobId],
    queryFn: () => Api.getResult(jobId!),
    enabled: !!jobId,
  })

  // Client-side overlay of corrections to ensure immediate reflection
  const { data: correctionsData } = useQuery({
    queryKey: ['corrections', jobId],
    queryFn: async () => {
      const res = await fetch(`/api/results/${encodeURIComponent(jobId!)}/corrections`, { headers: { 'Cache-Control': 'no-store' } })
      if (!res.ok) return [] as any[]
      const raw = await res.json()
      return Array.isArray(raw) ? raw : (Array.isArray(raw?.corrections) ? raw.corrections : (Array.isArray(raw?.items) ? raw.items : []))
    },
    enabled: !!jobId,
  })

  const labResult = useMemo(() => {
    try {
      if (!baseLabResult) return baseLabResult
      const list = Array.isArray(correctionsData) ? correctionsData : []
      if (list.length === 0) return baseLabResult
      // Convert any new_value form into op/path/value if missing
      const normalized = list.map((c: any) => {
        if (c?.path) return { op: (c.op || 'replace'), path: c.path, value: (c.value ?? c.new_value) }
        if (c?.field) return { op: 'replace', path: c.field, value: (c.value ?? c.new_value) }
        return c
      })
      const merged = applyCorrections(baseLabResult, normalized)
      return merged
    } catch {
      return baseLabResult
    }
  }, [baseLabResult, correctionsData])

  // Listen for corrections result refetch events to invalidate and refresh the viewer data
  useEffect(() => {
    const handler = (e: any) => {
      const rid = e?.detail?.rid
      if (!rid || rid !== jobId) return
      queryClient.invalidateQueries({ queryKey: ['lab-result', jobId] })
      queryClient.refetchQueries({ queryKey: ['lab-result', jobId] })
    }
    try { window.addEventListener('corrections:result-refetch', handler) } catch {}
    return () => { try { window.removeEventListener('corrections:result-refetch', handler) } catch {} }
  }, [jobId, queryClient])

  // Fetch extracted text with fallback handling
  useEffect(() => {
    if (!jobId) return

    const fetchExtractedText = async () => {
      setExtractedTextLoading(true)
      setExtractedTextNotFound(false)
      setExtractedTextError(null)

      try {
        // First try with fullId for files API
        console.debug('Trying extracted text with fullId:', fullId)
        const data = await getJSON<any>(`/api/files/${encodeURIComponent(fullId)}/extracted-text`)
        console.debug('Success with fullId:', fullId)
        setExtractedText(data)
      } catch (firstError) {
        // If fullId === baseId and first call failed, try fallback
        if (fullId === baseId && firstError instanceof NotFoundError) {
          console.debug('FullId failed, trying compose fallback')
          try {
            const fallbackId = `${baseId}.03_compose.debug`
            const data = await getJSON<any>(`/api/files/${encodeURIComponent(fallbackId)}/extracted-text`)
            console.debug('Success with fallback:', fallbackId)
            setExtractedText(data)
          } catch (secondError) {
            if (secondError instanceof NotFoundError) {
              console.debug('Both attempts failed with 404')
              setExtractedTextNotFound(true)
            } else {
              console.error('Fallback attempt failed:', secondError)
              setExtractedTextError(secondError instanceof Error ? secondError.message : 'Unknown error')
            }
          }
        } else {
          if (firstError instanceof NotFoundError) {
            setExtractedTextNotFound(true)
          } else {
            console.error('First attempt failed:', firstError)
            setExtractedTextError(firstError instanceof Error ? firstError.message : 'Unknown error')
          }
        }
      } finally {
        setExtractedTextLoading(false)
      }
    }

    fetchExtractedText()
  }, [jobId, fullId, baseId])

  // Set initial selected panel
  const firstPanel = labResult?.lab_panels?.[0]
  if (firstPanel && !selectedPanel) {
    setSelectedPanel(firstPanel.id)
  }

  const handleDownload = async () => {
    if (!jobId) return

    try {
      const blob = await resultsApi.downloadResult(jobId)
      downloadFile(blob, `lab_results_${jobId.slice(0, 8)}.json`)
      toast.success('Result downloaded successfully')
    } catch (error) {
      toast.error('Failed to download result')
    }
  }

  const retryExtractedText = () => {
    const viewerId = ensureViewerId(fullId)
    if (!jobId || !viewerId || !baseId) return

    const fetchExtractedText = async () => {
      setExtractedTextLoading(true)
      setExtractedTextNotFound(false)
      setExtractedTextError(null)

      try {
        console.debug('Retrying extracted text with viewerId:', viewerId)
        const data = await getJSON<any>(`/api/files/${viewerId}/extracted-text`)
        console.debug('Retry success with viewerId:', viewerId)
        setExtractedText(data)
      } catch (firstError) {
        if (firstError instanceof NotFoundError) {
          console.debug('Retry viewerId failed, trying baseId:', baseId)
          try {
            const data = await getJSON<any>(`/api/files/${baseId}/extracted-text`)
            console.debug('Retry success with baseId:', baseId)
            setExtractedText(data)
          } catch (secondError) {
            if (secondError instanceof NotFoundError) {
              console.debug('Both retry URLs failed with 404')
              setExtractedTextNotFound(true)
            } else {
              console.error('Second retry attempt failed:', secondError)
              setExtractedTextError(secondError instanceof Error ? secondError.message : 'Unknown error')
            }
          }
        } else {
          console.error('First retry attempt failed:', firstError)
          setExtractedTextError(firstError instanceof Error ? firstError.message : 'Unknown error')
        }
      } finally {
        setExtractedTextLoading(false)
      }
    }

    fetchExtractedText()
  }

  // Manual refresh button: force re-fetch of structured result and extracted text
  const refreshResult = async () => {
    if (!jobId) return
    try {
      const t = Date.now()
      const res = await fetch(`/api/results/${encodeURIComponent(jobId)}?t=${t}`, {
        headers: { 'Cache-Control': 'no-store' }
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      queryClient.setQueryData(['lab-result', jobId], data)
      toast.success('Result refreshed')
    } catch (e) {
      toast.error('Failed to refresh result')
    }
    // Also refresh extracted text in case the refresh impacts view
    try { retryExtractedText() } catch {}
  }

  if (!jobId) {
    return (
      <EmptyState
        title="Invalid job ID"
        description="Please check the URL and try again."
        actionText="Go to Processed"
        onAction={() => navigate('/processed')}
      />
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertTriangle size={48} className="mx-auto text-error-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Failed to Load Result
        </h2>
        <p className="text-gray-600 mb-4">
          {error.message || 'An error occurred while loading the result'}
        </p>
        <button onClick={() => navigate('/processed')} className="btn-primary">
          Back to Results
        </button>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center justify-center flex-1">
          <div className="spinner w-8 h-8" />
        </div>
      </div>
    )
  }

  // Guard for missing job data
  const job = labResult ?? null;
  if (!job) {
    return <div className="p-4 text-amber-600 text-sm">No job found.</div>;
  }

  // Show not found state for extracted text
  if (extractedTextNotFound && !labResult) {
    return (
      <EmptyState
        title="Result not found"
        description="The file may have been deleted or is still processing."
        actionText="Go to Processed"
        onAction={() => navigate('/processed')}
      />
    )
  }

  return (
    <ErrorBoundary>
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 p-4 bg-white">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/processed')}
              className="btn-ghost p-2"
              title="Back to processed results"
              aria-label="Back to processed results"
            >
              <ArrowLeft size={16} />
            </button>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Lab Result Viewer
              </h1>
              <p className="text-sm text-gray-600">
                Job ID: {jobId.slice(0, 8)}...
                {fullId !== baseId && <span className="text-xs text-amber-600 ml-2">(normalized from: {fullId.slice(0, 20)}...)</span>}
                {labResult?.document_info && isDocumentInfo(labResult.document_info) && (
                  <span className="ml-4">
                    Score: {formatConfidence(labResult.document_info.document_score)}
                    {labResult.document_info.needs_review && (
                      <span className="ml-2 badge-warning">Needs Review</span>
                    )}
                  </span>
                )}
              </p>
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
                showBusinessView && 'bg-blue-50 text-blue-700'
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

        {/* Extracted text error banner */}
        {extractedTextError && (
          <div className="bg-red-50 border-b border-red-200 px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <AlertTriangle size={16} className="text-red-600 mr-2" />
                <span className="text-red-800 text-sm">
                  Failed to load extracted text: {extractedTextError}
                </span>
              </div>
              <button
                onClick={retryExtractedText}
                className="text-red-600 hover:text-red-700 text-sm underline"
                disabled={extractedTextLoading}
              >
                {extractedTextLoading ? 'Retrying...' : 'Retry'}
              </button>
            </div>
          </div>
        )}

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
