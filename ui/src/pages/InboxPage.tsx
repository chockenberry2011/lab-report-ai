import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useMutation } from '@tanstack/react-query'
import { toast } from 'react-hot-toast'
import {
  Upload,
  FileText,
  Link as LinkIcon,
  Settings,
  Zap,
  Shield,
  Clock,
  X,
} from 'lucide-react'
import { jobApi } from '@/services/api'
import { validatePdfFile, validateUrl, cn } from '@/utils'
import type { ProcessingConfig } from '@/types'
import { configPresets } from '@/config/processing-presets'

export default function InboxPage() {
  const navigate = useNavigate()
  const [submitMode, setSubmitMode] = useState<'file' | 'url'>('file')
  const [pdfUrl, setPdfUrl] = useState('')
  const [selectedPreset, setSelectedPreset] = useState('default')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [customConfig, setCustomConfig] = useState<ProcessingConfig>({})
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

  // File upload mutation
  const fileUploadMutation = useMutation({
    mutationFn: ({ file, config }: { file: File; config: ProcessingConfig }) =>
      jobApi.submitFile(file, config),
    onSuccess: (result) => {
      toast.success(`Job submitted successfully! ID: ${result.job_id.slice(0, 8)}...`)
      navigate(`/queue`)
      setSelectedFiles([])
    },
    onError: (error) => {
      toast.error(`Upload failed: ${error.message}`)
    },
  })

  // URL submission mutation
  const urlSubmissionMutation = useMutation({
    mutationFn: ({ url, config }: { url: string; config: ProcessingConfig }) =>
      jobApi.submitUrl(url, config),
    onSuccess: (result) => {
      toast.success(`Job submitted successfully! ID: ${result.job_id.slice(0, 8)}...`)
      navigate(`/queue`)
      setPdfUrl('')
    },
    onError: (error) => {
      toast.error(`Submission failed: ${error.message}`)
    },
  })

  // Dropzone configuration
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 5,
    maxSize: 50 * 1024 * 1024, // 50MB
    onDrop: (acceptedFiles) => {
      setSelectedFiles(acceptedFiles)
    },
    onDropRejected: (rejectedFiles) => {
      rejectedFiles.forEach(({ errors }) => {
        errors.forEach(error => {
          toast.error(error.message)
        })
      })
    },
  })

  const getConfig = (): ProcessingConfig => {
    if (showAdvanced) {
      return { ...configPresets[selectedPreset].config, ...customConfig }
    }
    return configPresets[selectedPreset].config
  }

  const handleFileSubmit = async () => {
    if (selectedFiles.length === 0) {
      toast.error('Please select at least one file')
      return
    }

    // Submit each file as a separate job
    for (const file of selectedFiles) {
      const validation = validatePdfFile(file)
      if (!validation.valid) {
        toast.error(`${file.name}: ${validation.error}`)
        continue
      }

      fileUploadMutation.mutate({ file, config: getConfig() })
    }
  }

  const handleUrlSubmit = async () => {
    const validation = validateUrl(pdfUrl)
    if (!validation.valid) {
      toast.error(validation.error!)
      return
    }

    urlSubmissionMutation.mutate({ url: pdfUrl, config: getConfig() })
  }

  const removeFile = (index: number) => {
    setSelectedFiles(files => files.filter((_, i) => i !== index))
  }

  const isSubmitting = fileUploadMutation.isPending || urlSubmissionMutation.isPending

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Submit Lab Reports for Processing
        </h1>
        <p className="text-gray-600">
          Upload PDF files or provide URLs to process lab reports with AI-powered data extraction
        </p>
      </div>

      {/* Submission mode tabs */}
      <div className="flex justify-center">
        <div className="flex bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setSubmitMode('file')}
            className={cn(
              'px-4 py-2 rounded-md text-sm font-medium transition-colors',
              submitMode === 'file'
                ? 'bg-white text-primary-700 shadow-sm'
                : 'text-gray-700 hover:text-gray-900'
            )}
          >
            <Upload size={16} className="inline mr-2" />
            Upload Files
          </button>
          <button
            onClick={() => setSubmitMode('url')}
            className={cn(
              'px-4 py-2 rounded-md text-sm font-medium transition-colors',
              submitMode === 'url'
                ? 'bg-white text-primary-700 shadow-sm'
                : 'text-gray-700 hover:text-gray-900'
            )}
          >
            <LinkIcon size={16} className="inline mr-2" />
            From URL
          </button>
        </div>
      </div>

      {/* File Upload Mode */}
      {submitMode === 'file' && (
        <div className="space-y-4">
          {/* Dropzone */}
          <div
            {...getRootProps()}
            className={cn(
              'dropzone',
              isDragActive && !isDragReject && 'active',
              isDragReject && 'reject'
            )}
          >
            <input {...getInputProps()} />
            <div className="text-center">
              <Upload size={48} className="mx-auto text-gray-400 mb-4" />
              {isDragActive ? (
                <p className="text-lg font-medium text-primary-600">
                  Drop the files here...
                </p>
              ) : (
                <>
                  <p className="text-lg font-medium text-gray-900 mb-2">
                    Drop PDF files here, or click to select
                  </p>
                  <p className="text-sm text-gray-500">
                    Up to 5 files, max 50MB each. Only PDF files are supported.
                  </p>
                </>
              )}
            </div>
          </div>

          {/* Selected files */}
          {selectedFiles.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-3">
                Selected Files ({selectedFiles.length})
              </h3>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FileText size={20} className="text-red-500" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">{file.name}</div>
                        <div className="text-xs text-gray-500">
                          {(file.size / 1024 / 1024).toFixed(1)} MB
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* URL Submission Mode */}
      {submitMode === 'url' && (
        <div className="card p-6">
          <div className="space-y-4">
            <div>
              <label className="label">PDF URL</label>
              <input
                type="url"
                value={pdfUrl}
                onChange={(e) => setPdfUrl(e.target.value)}
                placeholder="https://example.com/lab-report.pdf"
                className="input"
                disabled={isSubmitting}
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter the URL of a publicly accessible PDF file
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Processing Configuration */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">Processing Configuration</h3>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="btn-ghost flex items-center space-x-2"
          >
            <Settings size={16} />
            <span>Advanced</span>
          </button>
        </div>

        {/* Preset Selection */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {Object.entries(configPresets).map(([key, preset]) => (
            <button
              key={key}
              onClick={() => setSelectedPreset(key)}
              className={cn(
                'p-4 rounded-lg border-2 transition-all text-left',
                selectedPreset === key
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              )}
            >
              <div className="flex items-center space-x-2 mb-2">
                {key === 'high_quality' && <Shield size={16} className="text-primary-600" />}
                {key === 'fast' && <Zap size={16} className="text-primary-600" />}
                {key === 'default' && <Clock size={16} className="text-primary-600" />}
                <span className="font-medium text-gray-900">{preset.name}</span>
              </div>
              <p className="text-sm text-gray-600">{preset.description}</p>
            </button>
          ))}
        </div>

        {/* Advanced Configuration */}
        {showAdvanced && (
          <div className="border-t border-gray-200 pt-4 space-y-4">
            <h4 className="text-sm font-medium text-gray-900">Advanced Settings</h4>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Extraction DPI</label>
                <input
                  type="number"
                  min={72}
                  max={300}
                  value={customConfig.extraction?.dpi || configPresets[selectedPreset].config.extraction?.dpi}
                  onChange={(e) => setCustomConfig({
                    ...customConfig,
                    extraction: {
                      ...customConfig.extraction,
                      dpi: parseInt(e.target.value),
                    },
                  })}
                  className="input"
                />
              </div>
              
              <div>
                <label className="label">Document Score Threshold</label>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={customConfig.composition?.scoring?.document_score_threshold || configPresets[selectedPreset].config.composition?.scoring?.document_score_threshold}
                  onChange={(e) => setCustomConfig({
                    ...customConfig,
                    composition: {
                      ...customConfig.composition,
                      scoring: {
                        ...customConfig.composition?.scoring,
                        document_score_threshold: parseFloat(e.target.value),
                      },
                    },
                  })}
                  className="input"
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="extract_images"
                checked={customConfig.extraction?.extract_images !== undefined 
                  ? customConfig.extraction.extract_images 
                  : configPresets[selectedPreset].config.extraction?.extract_images || false}
                onChange={(e) => setCustomConfig({
                  ...customConfig,
                  extraction: {
                    ...customConfig.extraction,
                    extract_images: e.target.checked,
                  },
                })}
                className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <label htmlFor="extract_images" className="text-sm text-gray-700">
                Extract images from PDF
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Submit Button */}
      <div className="flex justify-center">
        <button
          onClick={submitMode === 'file' ? handleFileSubmit : handleUrlSubmit}
          disabled={isSubmitting || (submitMode === 'file' && selectedFiles.length === 0) || (submitMode === 'url' && !pdfUrl.trim())}
          className="btn-primary px-8 py-3 text-lg"
        >
          {isSubmitting ? (
            <>
              <div className="spinner w-5 h-5 mr-2" />
              Submitting...
            </>
          ) : (
            <>
              {submitMode === 'file' ? <Upload size={20} className="mr-2" /> : <LinkIcon size={20} className="mr-2" />}
              Submit for Processing
            </>
          )}
        </button>
      </div>

      {/* Help Text */}
      <div className="text-center text-sm text-gray-500">
        <p>
          Processing typically takes 2-5 minutes depending on document complexity.
          You'll be able to monitor progress on the Queue page.
        </p>
      </div>
    </div>
  )
}