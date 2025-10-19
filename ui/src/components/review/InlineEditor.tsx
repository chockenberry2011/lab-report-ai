import React, { useState, useRef, useEffect } from 'react'
import { Check, X } from 'lucide-react'
import type { InlineEditorProps } from '@/types/review-fields'
import { cn } from '@/utils'

export function InlineEditor({
  initialValue,
  type,
  options,
  onSave,
  onCancel
}: InlineEditorProps) {
  const [value, setValue] = useState(initialValue ?? '')
  const [error, setError] = useState<string>('')
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null)

  useEffect(() => {
    // Focus input when component mounts
    inputRef.current?.focus()
    
    // Select all text if it's a text input
    if (inputRef.current && 'select' in inputRef.current) {
      inputRef.current.select()
    }
  }, [])

  const validateAndSave = () => {
    setError('')
    
    // Basic validation
    if (type === 'number' && value !== '' && isNaN(Number(value))) {
      setError('Please enter a valid number')
      return
    }
    
    if (type === 'date' && value !== '') {
      const date = new Date(value)
      if (isNaN(date.getTime())) {
        setError('Please enter a valid date')
        return
      }
    }
    
    if (type === 'phone' && value !== '') {
      // Basic phone validation - just check for reasonable length and digits
      const digits = value.replace(/\D/g, '')
      if (digits.length < 10) {
        setError('Please enter a valid phone number')
        return
      }
    }

    onSave(value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      validateAndSave()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onCancel()
    }
  }

  const formatPhoneValue = (input: string) => {
    // Simple phone formatting: (XXX) XXX-XXXX
    const digits = input.replace(/\D/g, '').slice(0, 10)
    if (digits.length >= 6) {
      return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
    } else if (digits.length >= 3) {
      return `(${digits.slice(0, 3)}) ${digits.slice(3)}`
    }
    return digits
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    let newValue = e.target.value
    
    if (type === 'phone') {
      newValue = formatPhoneValue(newValue)
    }
    
    setValue(newValue)
    setError('') // Clear error on change
  }

  const getInputType = () => {
    switch (type) {
      case 'date': return 'date'
      case 'number': return 'number'
      case 'phone': return 'tel'
      default: return 'text'
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        {type === 'select' && options ? (
          <select
            ref={inputRef as React.RefObject<HTMLSelectElement>}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            className={cn(
              'flex-1 px-3 py-1.5 text-sm border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              error ? 'border-red-300' : 'border-gray-300'
            )}
          >
            <option value="">Select...</option>
            {options.map(option => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        ) : (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type={getInputType()}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            className={cn(
              'flex-1 px-3 py-1.5 text-sm border rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              error ? 'border-red-300' : 'border-gray-300'
            )}
            placeholder={`Enter ${type === 'phone' ? 'phone number' : type === 'date' ? 'date' : 'value'}...`}
          />
        )}
        
        <button
          onClick={validateAndSave}
          className="p-1.5 text-green-600 hover:text-green-700 hover:bg-green-50 rounded transition-colors"
          title="Save (Enter)"
        >
          <Check size={16} />
        </button>
        
        <button
          onClick={onCancel}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-50 rounded transition-colors"
          title="Cancel (Esc)"
        >
          <X size={16} />
        </button>
      </div>
      
      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
      
      <p className="text-xs text-gray-500">
        Press Enter to save, Esc to cancel
      </p>
    </div>
  )
}