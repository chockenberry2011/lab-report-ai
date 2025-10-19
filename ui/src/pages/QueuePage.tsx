import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import {
  Eye,
  Edit3,
  RefreshCw,
  X,
  Clock,
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileText,
} from 'lucide-react'
import { jobApi, pollJobStatus } from '@/services/api'
import { ensureViewerId, normalizeResultId } from '@/lib/normalizeIds'
import { buildResultPath } from '@/lib/routeParsing'
import {
  formatRelativeTime,
  formatDuration,
  cn,
} from '@/utils'
import type { JobRegistryEntry } from '@/types'

interface JobRowProps {
  job: JobRegistryEntry
  onCancel: (jobId: string) => void
  onView: (jobId: string) => void
}

function JobRow({ job, onCancel, onView }: JobRowProps) {
  const [isPolling, setIsPolling] = useState(false)

  // Auto-poll for active jobs - simplified since registry has less detailed progress
  useEffect(() => {
    if (['queued', 'processing'].includes(job.status) && !isPolling) {
      setIsPolling(true)
      
      // We can still poll individual job status for detailed progress
      pollJobStatus(
        job.id,
        () => {}, // Updates handled by query refetch
        {
          interval: 3000,
          maxAttempts: 100,
          shouldStop: (detailedJob) => !['queued', 'processing'].includes(detailedJob.status),
        }
      ).finally(() => {
        setIsPolling(false)
      })
    }
  }, [job.id, job.status, isPolling])

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'queued':
        return <Clock size={14} />
      case 'processing':
        return <Play size={14} />
      case 'done':
        return <CheckCircle2 size={14} />
      case 'failed':
        return <XCircle size={14} />
      default:
        return <AlertCircle size={14} />
    }
  }

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'queued':
        return 'badge-secondary'
      case 'processing':
        return 'badge-primary'
      case 'done':
        return 'badge-success'
      case 'failed':
        return 'badge-error'
      default:
        return 'badge-secondary'
    }
  }

  const getDuration = () => {
    const created = new Date(job.created_at)
    const updated = new Date(job.updated_at)
    
    if (job.status === 'done' || job.status === 'failed') {
      return formatDuration((updated.getTime() - created.getTime()) / 1000)
    } else if (job.status === 'processing') {
      const now = new Date()
      return formatDuration((now.getTime() - created.getTime()) / 1000)
    }
    return null
  }

  return (
    <div className="card p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Job ID and filename */}
          <div className="flex items-center space-x-3 mb-2">
            <div className="flex items-center space-x-2">
              <FileText size={16} className="text-gray-400" />
              <span className="font-mono text-sm text-gray-600">
                {job.id.slice(0, 8)}...
              </span>
            </div>
            
            {job.filename && (
              <span className="text-sm text-gray-700 truncate max-w-md">
                {job.filename}
              </span>
            )}
          </div>

          {/* Status and timing */}
          <div className="flex items-center space-x-4 mb-2">
            <span className={cn('badge', getStatusBadgeClass(job.status))}>
              {getStatusIcon(job.status)} {job.status === 'done' ? 'completed' : job.status}
            </span>
            
            <span className="text-xs text-gray-500">
              Created {formatRelativeTime(job.created_at)}
            </span>
            
            <span className="text-xs text-gray-500">
              Updated {formatRelativeTime(job.updated_at)}
            </span>
            
            {getDuration() && (
              <span className="text-xs text-gray-500">
                Duration: {getDuration()}
              </span>
            )}
          </div>

          {/* Error message */}
          {job.error && (
            <div className="mt-2 p-2 bg-error-50 border border-error-200 rounded text-sm text-error-700">
              <AlertCircle size={14} className="inline mr-1" />
              {job.error}
            </div>
          )}

          {/* Processing indicator */}
          {job.status === 'processing' && (
            <div className="mt-2">
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-primary-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-600">Processing...</span>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2 ml-4">
          {job.result_path && (
            <>
              <button
                onClick={() => navigate(buildResultPath('viewer', job.id))}
                className="btn-ghost p-2"
                title={`View results for ${job.filename || job.id}`}
                aria-label={`View results for ${job.filename || job.id}`}
              >
                <Eye size={16} />
              </button>
              <button
                onClick={() => onView(job.id)}
                className="btn-primary flex items-center space-x-1 px-3 py-1.5 text-sm"
                title={`Review and edit ${job.filename || job.id}`}
                aria-label={`Review and edit ${job.filename || job.id}`}
              >
                <Edit3 size={14} />
                <span className="hidden sm:inline">Review & Edit</span>
              </button>
            </>
          )}

          {['queued', 'processing'].includes(job.status) && (
            <button
              onClick={() => onCancel(job.id)}
              className="btn-ghost p-2 text-error-600 hover:text-error-700"
              title="Cancel job"
            >
              <X size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function QueuePage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Fetch jobs using new API
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: () => jobApi.getJobs({
      status: statusFilter === 'all' ? undefined : statusFilter,
      per_page: 50,
    }),
    refetchInterval: 3000, // 3 second polling as requested
  })

  const jobs = data?.jobs || []

  // Cancel job mutation
  const cancelMutation = useMutation({
    mutationFn: jobApi.cancel,
    onSuccess: () => {
      toast.success('Job cancelled successfully')
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error) => {
      toast.error(`Failed to cancel job: ${error.message}`)
    },
  })

  const handleCancel = (jobId: string) => {
    if (window.confirm('Are you sure you want to cancel this job?')) {
      cancelMutation.mutate(jobId)
    }
  }

  const handleView = (jobId: string) => {
    navigate(`/review/${jobId}`)
  }

  const statusCounts = jobs.reduce((acc: Record<string, number>, job: JobRegistryEntry) => {
    acc[job.status] = (acc[job.status] || 0) + 1
    return acc
  }, {})

  const statusOptions = [
    { value: 'all', label: 'All Jobs', count: jobs.length },
    { value: 'queued', label: 'Queued', count: statusCounts.queued || 0 },
    { value: 'processing', label: 'Processing', count: statusCounts.processing || 0 },
    { value: 'done', label: 'Completed', count: statusCounts.done || 0 },
    { value: 'failed', label: 'Failed', count: statusCounts.failed || 0 },
  ]

  if (error) {
    const isApiError = error.message.includes('Method not allowed') || error.message.includes('Resource not found')
    
    return (
      <div className="text-center py-12">
        <XCircle size={48} className="mx-auto text-error-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          {isApiError ? 'API Endpoint Changed' : 'Failed to Load Jobs'}
        </h2>
        <p className="text-gray-600 mb-4">
          {isApiError 
            ? 'The jobs endpoint may have been updated. Please refresh the page to try again.'
            : (error.message || 'An error occurred while fetching jobs')
          }
        </p>
        <div className="flex items-center justify-center space-x-3">
          <button onClick={() => refetch()} className="btn-primary">
            <RefreshCw size={16} className="mr-2" />
            Retry
          </button>
          {isApiError && (
            <button 
              onClick={() => window.location.reload()} 
              className="btn-secondary"
            >
              <RefreshCw size={16} className="mr-2" />
              Refresh Page
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with stats */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Processing Queue</h1>
          <p className="text-gray-600">
            Monitor job status and progress
          </p>
        </div>
        
        <button
          onClick={() => refetch()}
          disabled={isLoading}
          className="btn-ghost flex items-center space-x-2"
        >
          <RefreshCw size={16} className={cn(isLoading && 'animate-spin')} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Status filter tabs */}
      <div className="flex space-x-1 bg-gray-100 rounded-lg p-1">
        {statusOptions.map((option) => (
          <button
            key={option.value}
            onClick={() => setStatusFilter(option.value)}
            className={cn(
              'flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors',
              statusFilter === option.value
                ? 'bg-white text-primary-700 shadow-sm'
                : 'text-gray-700 hover:text-gray-900'
            )}
          >
            <span>{option.label}</span>
            {option.count > 0 && (
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded-full',
                statusFilter === option.value
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-200 text-gray-600'
              )}>
                {option.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Jobs list */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="spinner w-8 h-8 mx-auto mb-4" />
          <p className="text-gray-600">Loading jobs...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-12">
          <Clock size={48} className="mx-auto text-gray-400 mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            No Jobs Found
          </h2>
          <p className="text-gray-600 mb-4">
            {statusFilter === 'all' 
              ? 'Jobs are created when you upload PDFs. Processed outputs are under the \'Processed\' tab.'
              : `No jobs with status "${statusFilter}"`
            }
          </p>
          <button
            onClick={() => navigate('/inbox')}
            className="btn-primary"
          >
            Submit New Job
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job: JobRegistryEntry) => (
            <JobRow
              key={job.id}
              job={job}
              onCancel={handleCancel}
              onView={handleView}
            />
          ))}
        </div>
      )}

      {/* Footer with summary */}
      {jobs.length > 0 && (
        <div className="border-t border-gray-200 pt-4">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>
              Showing {jobs.length} job{jobs.length !== 1 ? 's' : ''}
              {statusFilter !== 'all' && ` with status "${statusFilter}"`}
            </span>
            
            <div className="flex items-center space-x-4">
              {statusCounts.processing > 0 && (
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" />
                  <span>{statusCounts.processing} processing</span>
                </div>
              )}
              
              {statusCounts.queued > 0 && (
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full" />
                  <span>{statusCounts.queued} queued</span>
                </div>
              )}
              
              {statusCounts.done > 0 && (
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full" />
                  <span>{statusCounts.done} completed</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
