import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ConfidenceLevel, FieldConfidence } from '@/types'

// Tailwind class name utility
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Confidence level utilities
export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.6) return 'medium'
  return 'low'
}

export function getConfidenceBadgeClass(confidence: number): string {
  const level = getConfidenceLevel(confidence)
  switch (level) {
    case 'high':
      return 'badge-success'
    case 'medium':
      return 'badge-warning'
    case 'low':
      return 'badge-error'
    default:
      return 'badge-gray'
  }
}

export function getConfidenceTextClass(confidence: number): string {
  const level = getConfidenceLevel(confidence)
  switch (level) {
    case 'high':
      return 'high-confidence'
    case 'medium':
      return 'medium-confidence'
    case 'low':
      return 'low-confidence'
    default:
      return ''
  }
}

// Status utilities
export function getStatusBadgeClass(status: string): string {
  switch (status) {
    case 'completed':
      return 'badge-success'
    case 'processing':
      return 'badge-primary'
    case 'queued':
      return 'badge-gray'
    case 'failed':
      return 'badge-error'
    case 'cancelled':
      return 'badge-warning'
    default:
      return 'badge-gray'
  }
}

export function getStatusIcon(status: string): string {
  switch (status) {
    case 'completed':
      return '✅'
    case 'processing':
      return '⏳'
    case 'queued':
      return '📋'
    case 'failed':
      return '❌'
    case 'cancelled':
      return '⏹️'
    default:
      return '❓'
  }
}

// Time formatting utilities
export function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const time = new Date(timestamp)
  const diff = now.getTime() - time.getTime()
  
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (days > 0) {
    return `${days}d ago`
  } else if (hours > 0) {
    return `${hours}h ago`
  } else if (minutes > 0) {
    return `${minutes}m ago`
  } else if (seconds > 0) {
    return `${seconds}s ago`
  } else {
    return 'Just now'
  }
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`
  } else if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }
}

export function formatTimestamp(timestamp: string, includeTime: boolean = true): string {
  const date = new Date(timestamp)
  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }
  
  if (includeTime) {
    options.hour = '2-digit'
    options.minute = '2-digit'
  }
  
  return date.toLocaleDateString('en-US', options)
}

// Number formatting utilities
export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

export function formatFileSize(bytes: number): string {
  const sizes = ['B', 'KB', 'MB', 'GB']
  if (bytes === 0) return '0 B'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${Math.round(bytes / Math.pow(1024, i) * 100) / 100} ${sizes[i]}`
}

// Field confidence analysis
export function analyzeFieldConfidence(fieldConfidence: FieldConfidence): {
  weakestField: string
  strongestField: string
  overallLevel: ConfidenceLevel
  issues: string[]
} {
  const fields = {
    'Value Parsing': fieldConfidence.value_parse,
    'Unit Validity': fieldConfidence.unit_validity,
    'Reference Range': fieldConfidence.reference_range,
    'Test Name Clarity': fieldConfidence.test_name_clarity,
    'Classifier Confidence': fieldConfidence.classifier_proba,
  }
  
  const entries = Object.entries(fields)
  const weakest = entries.reduce((a, b) => (a[1] < b[1] ? a : b))
  const strongest = entries.reduce((a, b) => (a[1] > b[1] ? a : b))
  
  const issues: string[] = []
  if (fieldConfidence.value_parse < 0.6) {
    issues.push('Poor value parsing')
  }
  if (fieldConfidence.unit_validity < 0.6) {
    issues.push('Invalid or unclear units')
  }
  if (fieldConfidence.reference_range < 0.5) {
    issues.push('Malformed reference range')
  }
  if (fieldConfidence.test_name_clarity < 0.4) {
    issues.push('Unclear test name')
  }
  if (fieldConfidence.classifier_proba < 0.7) {
    issues.push('Uncertain role classification')
  }
  
  return {
    weakestField: weakest[0],
    strongestField: strongest[0],
    overallLevel: getConfidenceLevel(fieldConfidence.overall),
    issues,
  }
}

// Search and filter utilities
export function searchInText(text: string, query: string): boolean {
  if (!query.trim()) return true
  return text.toLowerCase().includes(query.toLowerCase())
}

export function highlightText(text: string, query: string): string {
  if (!query.trim()) return text
  
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200">$1</mark>')
}

// Validation utilities
export function validatePdfFile(file: File): { valid: boolean; error?: string } {
  if (!file) {
    return { valid: false, error: 'No file selected' }
  }
  
  if (file.type !== 'application/pdf') {
    return { valid: false, error: 'File must be a PDF' }
  }
  
  // 50MB limit
  if (file.size > 50 * 1024 * 1024) {
    return { valid: false, error: 'File size must be less than 50MB' }
  }
  
  return { valid: true }
}

export function validateUrl(url: string): { valid: boolean; error?: string } {
  if (!url.trim()) {
    return { valid: false, error: 'URL is required' }
  }
  
  try {
    const urlObj = new URL(url)
    if (!['http:', 'https:'].includes(urlObj.protocol)) {
      return { valid: false, error: 'URL must use HTTP or HTTPS protocol' }
    }
    return { valid: true }
  } catch {
    return { valid: false, error: 'Invalid URL format' }
  }
}

// Local storage utilities
export function saveToStorage<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch (error) {
    console.warn('Failed to save to localStorage:', error)
  }
}

export function loadFromStorage<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : defaultValue
  } catch (error) {
    console.warn('Failed to load from localStorage:', error)
    return defaultValue
  }
}

export function removeFromStorage(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch (error) {
    console.warn('Failed to remove from localStorage:', error)
  }
}

// Debounce utility
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null
  
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

// Export lazy loading utilities
export { lazyWithReport } from './lazyWithReport';

// Copy to clipboard utility
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (error) {
    // Fallback for older browsers
    try {
      const textArea = document.createElement('textarea')
      textArea.value = text
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      return true
    } catch (fallbackError) {
      console.error('Failed to copy to clipboard:', fallbackError)
      return false
    }
  }
}

// Generate unique IDs
export function generateId(): string {
  return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
}

// Error handling utilities
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  } else if (typeof error === 'string') {
    return error
  } else {
    return 'An unknown error occurred'
  }
}

// JSON formatting utility
export function formatJson(obj: any, indent: number = 2): string {
  return JSON.stringify(obj, null, indent)
}

// Download utilities
export function downloadJson(data: any, filename: string): void {
  const json = formatJson(data)
  const blob = new Blob([json], { type: 'application/json' })
  const url = window.URL.createObjectURL(blob)
  
  const a = document.createElement('a')
  a.href = url
  a.download = filename.endsWith('.json') ? filename : `${filename}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  
  window.URL.revokeObjectURL(url)
}