import React, { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { FieldDef } from '@/config/fieldSchema'
import { normalizePhone, normalizeZip, normalizeCLIA, isValidNPI, isDateInFuture, isDateTimeInFuture } from '@/lib/format'

interface InputSwitchProps {
  def: FieldDef
  value: any
  onChange: (v: any) => void
  fieldId?: string
}

export function InputSwitch({ def, value, onChange, fieldId }: InputSwitchProps) {
  const [localValue, setLocalValue] = useState(value || '')
  const [validationWarning, setValidationWarning] = useState<string>('')
  const [isControlled, setIsControlled] = useState(false)

  // Only sync when value changes from external source (not user typing)
  useEffect(() => {
    if (!isControlled) {
      setLocalValue(value || '')
      setValidationWarning('')
    }
  }, [value, isControlled])

  const handleChange = (newValue: any) => {
    setIsControlled(true) // Prevent external updates while user is editing
    setLocalValue(newValue)
    onChange(newValue)
  }

  const handlePhoneBlur = () => {
    const formatted = normalizePhone(localValue)
    if (formatted !== localValue) {
      handleChange(formatted)
    }
  }

  const handleCLIAChange = (cliaValue: string) => {
    const processed = normalizeCLIA(cliaValue)
    handleChange(processed)
  }

  const handleZipBlur = () => {
    const formatted = normalizeZip(localValue)
    if (formatted !== localValue) {
      handleChange(formatted)
    }
  }

  const handleNPIValidation = (npiValue: string) => {
    if (npiValue && !isValidNPI(npiValue)) {
      setValidationWarning('NPI must be exactly 10 digits')
    } else {
      setValidationWarning('')
    }
  }

  const handleDateValidation = (dateValue: string, isDateTime = false) => {
    if (!dateValue) {
      setValidationWarning('')
      return
    }

    const isFuture = isDateTime ? isDateTimeInFuture(dateValue) : isDateInFuture(dateValue)

    // Check if this is a collection/specimen date that shouldn't be in future
    const isCollectionField = def.path.includes('collected_at') || def.path.includes('received_at') ||
                             def.path.includes('entered_at') || def.path.includes('reported_at')

    if (isFuture && isCollectionField) {
      setValidationWarning('Date cannot be in the future')
    } else {
      setValidationWarning('')
    }
  }

  // Handle address as a special case - render 4 stacked inputs
  if (def.input === 'address') {
    const addressLabels = {
      street: 'Street Address',
      city: 'City',
      state: 'State',
      zip: 'ZIP Code'
    }

    const addressKey = def.path.split('.').pop() as keyof typeof addressLabels
    const label = addressLabels[addressKey] || def.label
    const isZip = addressKey === 'zip'

    return (
      <div>
        <input
          id={fieldId}
          type="text"
          value={localValue}
          onChange={(e) => handleChange(e.target.value)}
          onBlur={isZip ? handleZipBlur : undefined}
          placeholder={def.placeholder}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
          aria-label={label}
        />
        {validationWarning && (
          <div className="mt-1 flex items-center text-xs text-amber-600">
            <AlertTriangle size={12} className="mr-1" />
            {validationWarning}
          </div>
        )}
      </div>
    )
  }

  const renderValidationWarning = () => {
    if (!validationWarning) return null
    return (
      <div className="mt-1 flex items-center text-xs text-amber-600">
        <AlertTriangle size={12} className="mr-1" />
        {validationWarning}
      </div>
    )
  }

  switch (def.input) {
    case 'textarea':
      return (
        <div>
          <textarea
            id={fieldId}
            value={localValue}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={def.placeholder}
            rows={3}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'number':
      return (
        <div>
          <input
            id={fieldId}
            type="number"
            value={localValue}
            onChange={(e) => handleChange(e.target.value ? parseInt(e.target.value) : '')}
            placeholder={def.placeholder}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'date':
      return (
        <div>
          <input
            id={fieldId}
            type="date"
            value={localValue}
            onChange={(e) => {
              handleChange(e.target.value)
              handleDateValidation(e.target.value, false)
            }}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'datetime':
      return (
        <div>
          <input
            id={fieldId}
            type="datetime-local"
            value={localValue}
            onChange={(e) => {
              handleChange(e.target.value)
              handleDateValidation(e.target.value, true)
            }}
            placeholder={def.placeholder}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'phone':
      return (
        <div>
          <input
            id={fieldId}
            type="tel"
            value={localValue}
            onChange={(e) => setLocalValue(e.target.value)}
            onBlur={handlePhoneBlur}
            placeholder={def.placeholder}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'select':
      return (
        <div>
          <select
            id={fieldId}
            value={localValue}
            onChange={(e) => handleChange(e.target.value)}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          >
            {def.options?.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {renderValidationWarning()}
        </div>
      )

    case 'clia':
      return (
        <div>
          <input
            id={fieldId}
            type="text"
            value={localValue}
            onChange={(e) => handleCLIAChange(e.target.value)}
            placeholder={def.placeholder}
            maxLength={10}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2 font-mono"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'loinc':
    case 'cpt':
      return (
        <div>
          <input
            id={fieldId}
            type="text"
            value={localValue}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={def.placeholder}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2 font-mono"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )

    case 'text':
    default:
      // Handle NPI validation for text fields with 'npi' in path
      const isNPI = def.path.includes('npi')

      return (
        <div>
          <input
            id={fieldId}
            type="text"
            value={localValue}
            onChange={(e) => {
              handleChange(e.target.value)
              if (isNPI) {
                handleNPIValidation(e.target.value)
              }
            }}
            placeholder={def.placeholder}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 focus:ring-2"
            aria-label={def.label}
          />
          {renderValidationWarning()}
        </div>
      )
  }
}