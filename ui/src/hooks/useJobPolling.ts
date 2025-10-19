import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { jobApi } from '@/services/api'
import type { Job } from '@/types'

interface UseJobPollingOptions {
  jobId: string
  onStatusChange?: (job: Job) => void
  enabled?: boolean
  interval?: number
  maxAttempts?: number
}

export function useJobPolling({
  jobId,
  onStatusChange,
  enabled = true,
  interval = 3000,
  maxAttempts = 100,
}: UseJobPollingOptions) {
  const queryClient = useQueryClient()
  const attemptCount = useRef(0)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!enabled || !jobId) return

    const poll = async () => {
      try {
        const job = await jobApi.getStatus(jobId)
        
        // Update the query cache
        queryClient.setQueryData(['jobs'], (oldData: any) => {
          if (!oldData?.jobs) return oldData
          
          return {
            ...oldData,
            jobs: oldData.jobs.map((j: Job) => j.job_id === jobId ? job : j)
          }
        })

        // Call status change callback
        if (onStatusChange) {
          onStatusChange(job)
        }

        // Stop polling if job is complete or max attempts reached
        if (
          ['completed', 'failed', 'cancelled'].includes(job.status) ||
          attemptCount.current >= maxAttempts
        ) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          return
        }

        attemptCount.current++
      } catch (error) {
        console.error('Polling error:', error)
        
        // Stop polling on error
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    }

    // Start polling
    intervalRef.current = setInterval(poll, interval)

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [jobId, enabled, interval, maxAttempts, onStatusChange, queryClient])

  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  const startPolling = () => {
    if (!intervalRef.current && enabled) {
      attemptCount.current = 0
      // The useEffect will handle starting the interval
    }
  }

  return { stopPolling, startPolling, isPolling: intervalRef.current !== null }
}