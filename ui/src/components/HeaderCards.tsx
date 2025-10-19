// components/HeaderCards.tsx
import { 
  User, 
  Building2, 
  Stethoscope, 
  FlaskConical, 
  UserCheck, 
  FileText,
  Calendar,
  Phone,
  MapPin
} from 'lucide-react'
import type { 
  Patient, 
  Vendor, 
  PerformingLab, 
  Specimen, 
  Ordering, 
  Report,
  EnhancedDocumentInfo
} from '@/types'
import {
  formatAddress,
  formatPatientName,
  formatDate,
  formatDateTime,
  truncateText
} from '@/utils/formatters'
import { cn } from '@/utils'

interface HeaderCardsProps {
  documentInfo?: EnhancedDocumentInfo | null
  className?: string
}

interface CardFieldProps {
  label: string
  value?: string | number | null
  className?: string
}

function CardField({ label, value, className }: CardFieldProps) {
  const isEmpty = value === null || value === undefined || value === ''
  const displayValue = isEmpty ? '—' : value!.toString()
  
  return (
    <div className={cn('header-card-field', className)}>
      <span className="header-card-label">{label}:</span>
      <span className="header-card-value" title={isEmpty ? 'Not provided on report' : displayValue}>
        {displayValue}
      </span>
    </div>
  )
}

function PatientCard({ patient }: { patient?: Patient | null }) {
  if (!patient) return null
  
  const patientName = formatPatientName(patient)
  if (patientName === '—' && !patient.dob && !patient.mrn) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <User size={16} className="mr-2 text-blue-600" />
        Patient Information
      </div>
      
      <CardField label="Name" value={patientName} />
      <CardField label="DOB" value={formatDate(patient.dob)} />
      <CardField label="Sex" value={patient.sex} />
      <CardField label="MRN" value={patient.mrn} />
      {patient.phone && (
        <CardField label="Phone" value={patient.phone} />
      )}
      {patient.address && formatAddress(patient.address) !== '—' && (
        <CardField 
          label="Address" 
          value={formatAddress(patient.address)}
          className="items-start"
        />
      )}
    </div>
  )
}

function VendorCard({ vendor }: { vendor?: Vendor | null }) {
  if (!vendor) return null
  
  const hasData = vendor.name || vendor.account_number || vendor.phone
  if (!hasData) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <Building2 size={16} className="mr-2 text-green-600" />
        Vendor/Lab
      </div>
      
      <CardField label="Name" value={vendor.name} />
      <CardField label="Account" value={vendor.account_number} />
      {vendor.phone && (
        <CardField label="Phone" value={vendor.phone} />
      )}
      {vendor.fax && (
        <CardField label="Fax" value={vendor.fax} />
      )}
      {vendor.address && formatAddress(vendor.address) !== '—' && (
        <CardField 
          label="Address" 
          value={formatAddress(vendor.address)}
          className="items-start"
        />
      )}
    </div>
  )
}

function PerformingLabCard({ performingLab }: { performingLab?: PerformingLab | null }) {
  if (!performingLab) return null
  
  const hasData = performingLab.name || performingLab.clia || performingLab.director
  if (!hasData) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <Stethoscope size={16} className="mr-2 text-purple-600" />
        Performing Laboratory
      </div>
      
      <CardField label="Name" value={performingLab.name} />
      <CardField label="CLIA" value={performingLab.clia} />
      <CardField label="Director" value={performingLab.director} />
      {performingLab.address && formatAddress(performingLab.address) !== '—' && (
        <CardField 
          label="Address" 
          value={formatAddress(performingLab.address)}
          className="items-start"
        />
      )}
    </div>
  )
}

function SpecimenCard({ specimen }: { specimen?: Specimen | null }) {
  if (!specimen) return null
  
  const hasData = specimen.id || specimen.type || specimen.collected_at
  if (!hasData) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <FlaskConical size={16} className="mr-2 text-orange-600" />
        Specimen Information
      </div>
      
      <CardField label="ID" value={specimen.id} />
      <CardField label="Control ID" value={specimen.control_id} />
      <CardField label="Type" value={specimen.type} />
      <CardField label="Collected" value={formatDateTime(specimen.collected_at)} />
      <CardField label="Received" value={formatDateTime(specimen.received_at)} />
      <CardField label="Reported" value={formatDateTime(specimen.reported_at)} />
    </div>
  )
}

function OrderingCard({ ordering }: { ordering?: Ordering | null }) {
  if (!ordering) return null
  
  const hasData = ordering.provider_name || ordering.npi || ordering.location
  if (!hasData) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <UserCheck size={16} className="mr-2 text-indigo-600" />
        Ordering Provider
      </div>
      
      <CardField label="Provider" value={ordering.provider_name} />
      <CardField label="NPI" value={ordering.npi} />
      {ordering.location && (
        <>
          <CardField label="Location" value={ordering.location.name} />
          {ordering.location.address && formatAddress(ordering.location.address) !== '—' && (
            <CardField 
              label="Address" 
              value={formatAddress(ordering.location.address)}
              className="items-start"
            />
          )}
        </>
      )}
    </div>
  )
}

function ReportCard({ report }: { report?: Report | null }) {
  if (!report) return null
  
  const hasData = report.id || report.page_count || report.clinical_info || report.comments
  if (!hasData) return null
  
  return (
    <div className="header-card">
      <div className="header-card-title">
        <FileText size={16} className="mr-2 text-gray-600" />
        Report Information
      </div>
      
      <CardField label="Report ID" value={report.id} />
      <CardField label="Pages" value={report.page_count} />
      {report.clinical_info && (
        <CardField 
          label="Clinical Info" 
          value={truncateText(report.clinical_info, 60)}
          className="items-start"
        />
      )}
      {report.comments && (
        <CardField 
          label="Comments" 
          value={truncateText(report.comments, 60)}
          className="items-start"
        />
      )}
      {report.ordered_items && report.ordered_items.length > 0 && (
        <CardField 
          label="Ordered Items" 
          value={report.ordered_items.slice(0, 3).join(', ') + (report.ordered_items.length > 3 ? '...' : '')}
          className="items-start"
        />
      )}
    </div>
  )
}

export default function HeaderCards({ documentInfo, className }: HeaderCardsProps) {
  if (!documentInfo) return null
  
  // Check if we have any data to display
  const hasAnyData = [
    documentInfo.patient,
    documentInfo.vendor, 
    documentInfo.performing_lab,
    documentInfo.specimen,
    documentInfo.ordering,
    documentInfo.report
  ].some(Boolean)
  
  if (!hasAnyData) return null
  
  return (
    <div className={cn('mb-6', className)}>
      <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
        <FileText size={20} className="mr-2" />
        Document Information
      </h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <PatientCard patient={documentInfo.patient} />
        <VendorCard vendor={documentInfo.vendor} />
        <PerformingLabCard performingLab={documentInfo.performing_lab} />
        <SpecimenCard specimen={documentInfo.specimen} />
        <OrderingCard ordering={documentInfo.ordering} />
        <ReportCard report={documentInfo.report} />
      </div>
    </div>
  )
}
