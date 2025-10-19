import axios from 'axios'
import { toast } from 'react-hot-toast'
import { resultsApi as resultsApiClient, reviewApi as reviewApiClient, resultsBlob, genericApi } from '@/lib/apiClient'
import { ensureViewerId } from '@/lib/resultId'
import { normalizeResultId } from '@/lib/normalizeIds'
import type {
  Job,
  JobSubmissionResponse,
  JobListResponse,
  JobRegistryEntry,
  LabResult,
  SystemStats,
  ProcessingConfig,
  TrainingAnnotation,
  FlexibleTrainingAnnotation,
  Correction,
} from '@/types'

// Get API base URL from environment variable with fallback
const getApiBaseUrl = () => {
  const envApiBase = import.meta.env.VITE_API_BASE
  if (envApiBase) {
    return envApiBase
  }
  
  // Fallback to same-origin if no env var is set
  return '/api'
}

// Configure axios defaults
const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error)
    
    if (error.response?.status === 404) {
      const msg = error.response?.data?.detail || 'Resource not found'
      const url = error.config?.url || 'unknown endpoint'
      const method = error.config?.method?.toUpperCase() || 'UNKNOWN'
      
      // Show toast for debugging
      toast.error(`${method} ${url}: ${msg}`, { duration: 5000 })
      
      throw new Error(`${msg}. Check server routes at /debug/routes. Request URL: ${url}`)
    } else if (error.response?.status === 405) {
      const url = error.config?.url || 'unknown endpoint'
      const method = error.config?.method?.toUpperCase() || 'UNKNOWN'
      
      // Show toast for debugging
      toast.error(`${method} ${url}: Method not allowed`, { duration: 5000 })
      
      throw new Error('Method not allowed - API endpoint may have changed')
    } else if (error.response?.status >= 500) {
      throw new Error('Server error occurred')
    } else if (error.code === 'ECONNABORTED') {
      throw new Error('Request timed out')
    } else if (!error.response) {
      throw new Error('Network error - unable to reach server')
    }
    
    throw error
  }
)

// Job Management API
export const jobApi = {
  // Submit job with file upload
  submitFile: async (file: File, config?: ProcessingConfig): Promise<JobSubmissionResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('config', JSON.stringify(config || {}))
    
    const { data } = await api.post('/jobs', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    
    return data
  },
  
  // Submit job with URL
  submitUrl: async (pdfUrl: string, config?: ProcessingConfig): Promise<JobSubmissionResponse> => {
    const formData = new FormData()
    formData.append('pdf_url', pdfUrl)
    formData.append('config', JSON.stringify(config || {}))
    
    const { data } = await api.post('/jobs', formData)
    return data
  },
  
  // Get job status
  getStatus: async (jobId: string): Promise<Job> => {
    const { data } = await api.get(`/jobs/${jobId}`)
    return data
  },
  
  // Get job logs
  getLogs: async (jobId: string): Promise<{ job_id: string; logs: any[] }> => {
    const { data } = await api.get(`/jobs/${jobId}/logs`)
    return data
  },
  
  // Cancel job
  cancel: async (jobId: string): Promise<{ message: string }> => {
    const { data } = await api.delete(`/jobs/${jobId}`)
    return data
  },
  
  // Get all jobs (with pagination) - Updated for new API
  getJobs: async (params?: {
    status?: string
    page?: number
    per_page?: number
    q?: string
  }): Promise<JobListResponse> => {
    const { data } = await api.get('/jobs', { 
      params: {
        page: params?.page || 1,
        per_page: params?.per_page || 50,
        status: params?.status,
        q: params?.q,
      }
    })
    return data
  },

  // Legacy getJobs method for backward compatibility  
  getJobsLegacy: async (params?: {
    status?: string
    limit?: number
    offset?: number
  }): Promise<{ jobs: Job[]; total: number }> => {
    const { data } = await api.get('/jobs', { 
      params: {
        page: Math.floor((params?.offset || 0) / (params?.limit || 50)) + 1,
        per_page: params?.limit || 50,
        status: params?.status,
      }
    })
    
    // Transform JobRegistryEntry[] to Job[] for backward compatibility
    const transformedJobs: Job[] = data.jobs.map((entry: JobRegistryEntry) => ({
      job_id: entry.id,
      status: entry.status === 'done' ? 'completed' : entry.status,
      created_at: entry.created_at,
      started_at: undefined,
      completed_at: undefined,
      progress: {},
      result_url: entry.result_path ? `/results/${entry.id}` : undefined,
      error: entry.error,
      filename: entry.filename,
    }))
    
    return {
      jobs: transformedJobs,
      total: data.total
    }
  },
}

// Results API
export const resultsApi = {
  // Get result data
  getResult: async (jobId: string): Promise<LabResult> => {
    return await resultsApiClient(jobId, '')
  },
  
  // Download result file
  downloadResult: async (jobId: string): Promise<Blob> => {
    return await resultsBlob(jobId, '')
  },
  
  // Get results list with filtering
  getResultsList: async (filters?: {
    needs_review?: boolean
    confidence_range?: [number, number]
    date_range?: [string, string]
    search?: string
  }): Promise<{
    results: Array<{
      job_id: string
      filename?: string
      processed_at: string
      document_score: number
      needs_review: boolean
      total_tests: number
      total_panels: number
    }>
    total: number
  }> => {
    const { data } = await api.get('/results', { params: filters })
    return data
  },
  
  // Get extracted text for a job
  getExtractedText: async (jobId: string): Promise<{
    pages: Array<{
      page: number
      lines: Array<{
        text: string
        bbox: [number, number, number, number]
        confidence?: number
        role?: string
      }>
    }>
  }> => {
    const viewerId = ensureViewerId(jobId)
    const baseId = normalizeResultId(jobId)

    try {
      // Try the viewer-friendly URL first
      const { data } = await api.get(`/results/${viewerId}/extracted-text`)
      return data
    } catch (error) {
      try {
        // Fallback to base ID
        const { data } = await api.get(`/results/${baseId}/extracted-text`)
        return data
      } catch (fallbackError) {
        // Return empty structure if not available
        return { pages: [] }
      }
    }
  },
}

// Manual Review API
export const reviewApi = {
  // Save corrections
  saveCorrection: async (
    jobId: string,
    corrections: Correction[] | { items: any[], schema_version?: number }
  ): Promise<{ message: string }> => {
    try {
      let payload: any

      // Handle both new format and legacy format
      if (Array.isArray(corrections)) {
        // Array format: wrap in envelope
        payload = { corrections }
      } else if (corrections && 'items' in corrections) {
        // Legacy format: convert items to corrections
        const correctionItems = corrections.items.map((item: any) => ({
          field: item.path || item.field,
          new_value: item.op === "unset" ? undefined : item.value,
          old_value: undefined,
          note: item.op === "unset" ? "Field unset" : undefined,
          source: "review-api"
        }))
        payload = { corrections: correctionItems }
      } else {
        // Fallback
        payload = { corrections: [] }
      }

      return await resultsApiClient(jobId, '/corrections', {
        method: "POST",
        body: JSON.stringify(payload),
      })
    } catch (error) {
      console.error("Save corrections failed", error)
      throw new Error(`Failed to save corrections: ${error.message}`)
    }
  },
  
  // Add to training data
  addToTraining: async (
    jobId: string,
    annotations: FlexibleTrainingAnnotation[],
    includeManual = false
  ): Promise<{ message: string }> => {
    try {
      const payload = {
        include_manual_corrections: includeManual ?? false,
        annotations: annotations ?? [],
      }

      return await reviewApiClient(jobId, '/training', {
        method: "POST",
        body: JSON.stringify(payload),
      })
    } catch (error) {
      console.error("Save training failed", error)
      throw new Error(`Failed to save training: ${error.message}`)
    }
  },
  
  // Get existing corrections with cache bypass
  getCorrections: async (jobId: string): Promise<Record<string, any>> => {
    try {
      const normId = normalizeResultId(jobId)
      const response = await fetch(`/api/results/${normId}/corrections`, {
        headers: { "Cache-Control": "no-store" }
      })

      if (!response.ok) {
        if (response.status === 404) {
          return { corrections: [] }
        }
        throw new Error(`HTTP ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      // Return empty corrections if none exist
      if (error.message.includes('404')) {
        return { corrections: [] }
      }
      throw error
    }
  },
  
  // Get training data for a job
  getTrainingData: async (jobId: string): Promise<FlexibleTrainingAnnotation[]> => {
    try {
      return await reviewApiClient(jobId, '/training')
    } catch (error) {
      if (error.message.includes('404')) {
        return []
      }
      throw error
    }
  },
}

// System API
export const systemApi = {
  // Health check
  health: async (): Promise<{
    status: string
    timestamp: string
    redis: string
    celery: string
    data_dirs: Record<string, string>
  }> => {
    const { data } = await api.get('/health')
    return data
  },
  
  // Get system statistics
  getStats: async (): Promise<SystemStats> => {
    try {
      const data = await genericApi<any>('/api/stats')
      if (!data || typeof data !== 'object') throw new Error('stats invalid')

      const DEFAULT_STATS = { status_counts: { queued: 0, processing: 0, failed: 0, completed: 0 } }
      return { ...DEFAULT_STATS, ...data, status_counts: { ...DEFAULT_STATS.status_counts, ...(data.status_counts || {}) } }
    } catch (error) {
      throw new Error(`stats error: ${error.message}`)
    }
  },
}

// File Management API (for additional endpoints we might need)
export const fileApi = {
  // Get original PDF file for PDF viewer
  getOriginalPdf: async (jobId: string): Promise<string> => {
    const baseId = normalizeResultId(jobId)
    return `${getApiBaseUrl()}/files/${baseId}/original-pdf`
  },

  // Get page thumbnails for a job
  getThumbnails: async (jobId: string): Promise<Array<{
    page_number: number
    thumbnail_url: string
    width: number
    height: number
  }>> => {
    try {
      const viewerId = ensureViewerId(jobId)
      const { data } = await api.get(`/files/${viewerId}/thumbnails`)
      return data
    } catch (error) {
      // Return empty array if thumbnails not available
      return []
    }
  },
  
  // Get extracted text for a job
  getExtractedText: async (jobId: string): Promise<{
    pages: Array<{
      page: number
      lines: Array<{
        text: string
        bbox: [number, number, number, number]
        confidence?: number
        role?: string
      }>
    }>
  }> => {
    const viewerId = ensureViewerId(jobId)
    const baseId = normalizeResultId(jobId)

    try {
      // Try the viewer-friendly URL first
      const { data } = await api.get(`/files/${viewerId}/extracted-text`)
      return data
    } catch (error) {
      try {
        // Fallback to base ID
        const { data } = await api.get(`/files/${baseId}/extracted-text`)
        return data
      } catch (fallbackError) {
        // Return empty structure if not available
        return { pages: [] }
      }
    }
  },
}

// Utility function to handle file downloads
export const downloadFile = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

// Polling utility for job status
export const pollJobStatus = async (
  jobId: string,
  onUpdate: (job: Job) => void,
  options: {
    interval?: number
    maxAttempts?: number
    shouldStop?: (job: Job) => boolean
  } = {}
): Promise<Job> => {
  const {
    interval = 2000,
    maxAttempts = 150, // 5 minutes with 2s interval
    shouldStop = (job) => ['completed', 'failed', 'cancelled'].includes(job.status),
  } = options
  
  let attempts = 0
  
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const job = await jobApi.getStatus(jobId)
        onUpdate(job)
        
        if (shouldStop(job) || attempts >= maxAttempts) {
          resolve(job)
          return
        }
        
        attempts++
        setTimeout(poll, interval)
      } catch (error) {
        reject(error)
      }
    }
    
    poll()
  })
}

export default api