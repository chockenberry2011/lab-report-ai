// Field schema configuration for lab report forms

export type FieldPath = string
export type InputKind = 'text' | 'textarea' | 'number' | 'date' | 'datetime' | 'phone' | 'select' | 'clia' | 'address' | 'loinc' | 'cpt'

export interface FieldDef {
  path: FieldPath              // e.g., 'vendor.name'
  label: string                // e.g., 'Lab / Vendor Name'
  placeholder?: string
  description?: string         // shown under label as help text
  required?: boolean
  input: InputKind
  options?: { value: string; label: string }[]  // for select
  mask?: string                // optional input mask (e.g., '(999) 999-9999')
  validate?: (v: unknown) => string | null      // return error message or null
  group?: string               // Section grouping key, e.g., 'A', 'B', 'C'...
  width?: 'full' | 'half' | 'third'
}

export interface SectionDef {
  key: string                  // 'A','B','C','D','E'
  title: string
  subtitle?: string
  description?: string
  fields: FieldPath[]
}

// Validation helpers
const validateZip = (v: unknown): string | null => {
  if (!v || typeof v !== 'string') return null
  if (!/^\d{5}(-\d{4})?$/.test(v)) return 'Invalid ZIP code format (12345 or 12345-6789)'
  return null
}

const validatePhone = (v: unknown): string | null => {
  if (!v || typeof v !== 'string') return null
  const digits = v.replace(/\D/g, '')
  if (digits.length !== 10) return 'Phone number must be 10 digits'
  return null
}

const validateCLIA = (v: unknown): string | null => {
  if (!v || typeof v !== 'string') return null
  if (!/^[A-Za-z0-9]{10}$/.test(v)) return 'CLIA number must be exactly 10 alphanumeric characters'
  return null
}

const validateNPI = (v: unknown): string | null => {
  if (!v || typeof v !== 'string') return null
  if (!/^\d{10}$/.test(v)) return 'NPI must be exactly 10 digits'
  return null
}

// Field definitions
export const FIELDS: Record<FieldPath, FieldDef> = {
  // A. Lab / Vendor Envelope
  'vendor.name': {
    path: 'vendor.name',
    label: 'Lab / Vendor Name',
    placeholder: 'Enter lab name',
    required: true,
    input: 'text',
    group: 'A',
    width: 'full'
  },
  'vendor.account_number': {
    path: 'vendor.account_number',
    label: 'Account Number',
    placeholder: 'Enter account number',
    input: 'text',
    group: 'A',
    width: 'half'
  },
  'vendor.address.street': {
    path: 'vendor.address.street',
    label: 'Street Address',
    placeholder: 'Enter street address',
    input: 'address',
    group: 'A',
    width: 'full'
  },
  'vendor.address.city': {
    path: 'vendor.address.city',
    label: 'City',
    placeholder: 'Enter city',
    input: 'address',
    group: 'A',
    width: 'third'
  },
  'vendor.address.state': {
    path: 'vendor.address.state',
    label: 'State',
    placeholder: 'State',
    input: 'address',
    group: 'A',
    width: 'third'
  },
  'vendor.address.zip': {
    path: 'vendor.address.zip',
    label: 'ZIP Code',
    placeholder: '12345 or 12345-6789',
    input: 'address',
    validate: validateZip,
    group: 'A',
    width: 'third'
  },
  'vendor.phone': {
    path: 'vendor.phone',
    label: 'Phone',
    placeholder: '(555) 123-4567',
    input: 'phone',
    mask: '(999) 999-9999',
    validate: validatePhone,
    group: 'A',
    width: 'half'
  },
  'vendor.fax': {
    path: 'vendor.fax',
    label: 'Fax',
    placeholder: '(555) 123-4567',
    input: 'phone',
    mask: '(999) 999-9999',
    validate: validatePhone,
    group: 'A',
    width: 'half'
  },
  'report.id': {
    path: 'report.id',
    label: 'Report ID',
    placeholder: 'Enter report ID',
    required: true,
    input: 'text',
    group: 'A',
    width: 'third'
  },
  'report.page': {
    path: 'report.page',
    label: 'Page',
    placeholder: '1',
    input: 'number',
    group: 'A',
    width: 'third'
  },
  'report.page_count': {
    path: 'report.page_count',
    label: 'Total Pages',
    placeholder: '1',
    input: 'number',
    group: 'A',
    width: 'third'
  },
  'performing_lab.name': {
    path: 'performing_lab.name',
    label: 'Performing Lab Name',
    placeholder: 'Enter performing lab name',
    input: 'text',
    group: 'A',
    width: 'full'
  },
  'performing_lab.clia': {
    path: 'performing_lab.clia',
    label: 'CLIA Number',
    placeholder: 'Enter 10-character CLIA number',
    input: 'clia',
    validate: validateCLIA,
    group: 'A',
    width: 'half'
  },
  'performing_lab.director': {
    path: 'performing_lab.director',
    label: 'Lab Director',
    placeholder: 'Enter lab director name',
    input: 'text',
    group: 'A',
    width: 'half'
  },
  'performing_lab.address.street': {
    path: 'performing_lab.address.street',
    label: 'Lab Street Address',
    placeholder: 'Enter street address',
    input: 'address',
    group: 'A',
    width: 'full'
  },
  'performing_lab.address.city': {
    path: 'performing_lab.address.city',
    label: 'Lab City',
    placeholder: 'Enter city',
    input: 'address',
    group: 'A',
    width: 'third'
  },
  'performing_lab.address.state': {
    path: 'performing_lab.address.state',
    label: 'Lab State',
    placeholder: 'State',
    input: 'address',
    group: 'A',
    width: 'third'
  },
  'performing_lab.address.zip': {
    path: 'performing_lab.address.zip',
    label: 'Lab ZIP Code',
    placeholder: '12345 or 12345-6789',
    input: 'address',
    validate: validateZip,
    group: 'A',
    width: 'third'
  },

  // B. Patient
  'patient.last_name': {
    path: 'patient.last_name',
    label: 'Last Name',
    placeholder: 'Enter last name',
    required: true,
    input: 'text',
    group: 'B',
    width: 'third'
  },
  'patient.first_name': {
    path: 'patient.first_name',
    label: 'First Name',
    placeholder: 'Enter first name',
    required: true,
    input: 'text',
    group: 'B',
    width: 'third'
  },
  'patient.middle': {
    path: 'patient.middle',
    label: 'Middle Name/Initial',
    placeholder: 'Enter middle name',
    input: 'text',
    group: 'B',
    width: 'third'
  },
  'patient.dob': {
    path: 'patient.dob',
    label: 'Date of Birth',
    placeholder: 'MM/DD/YYYY',
    input: 'date',
    group: 'B',
    width: 'third'
  },
  'patient.sex': {
    path: 'patient.sex',
    label: 'Sex',
    input: 'select',
    options: [
      { value: '', label: 'Select...' },
      { value: 'Male', label: 'Male' },
      { value: 'Female', label: 'Female' },
      { value: 'Other', label: 'Other' },
      { value: 'Unknown', label: 'Unknown' }
    ],
    group: 'B',
    width: 'third'
  },
  'patient.mrn': {
    path: 'patient.mrn',
    label: 'Medical Record Number',
    placeholder: 'Enter MRN',
    input: 'text',
    group: 'B',
    width: 'third'
  },
  'patient.phone': {
    path: 'patient.phone',
    label: 'Phone',
    placeholder: '(555) 123-4567',
    input: 'phone',
    mask: '(999) 999-9999',
    validate: validatePhone,
    group: 'B',
    width: 'half'
  },
  'patient.address.street': {
    path: 'patient.address.street',
    label: 'Street Address',
    placeholder: 'Enter street address',
    input: 'address',
    group: 'B',
    width: 'full'
  },
  'patient.address.city': {
    path: 'patient.address.city',
    label: 'City',
    placeholder: 'Enter city',
    input: 'address',
    group: 'B',
    width: 'third'
  },
  'patient.address.state': {
    path: 'patient.address.state',
    label: 'State',
    placeholder: 'State',
    input: 'address',
    group: 'B',
    width: 'third'
  },
  'patient.address.zip': {
    path: 'patient.address.zip',
    label: 'ZIP Code',
    placeholder: '12345 or 12345-6789',
    input: 'address',
    validate: validateZip,
    group: 'B',
    width: 'third'
  },
  'patient.age_at_collection': {
    path: 'patient.age_at_collection',
    label: 'Age at Collection',
    placeholder: 'Enter age',
    input: 'number',
    group: 'B',
    width: 'half'
  },

  // C. Ordering / Provider
  'ordering.provider_name': {
    path: 'ordering.provider_name',
    label: 'Provider Name',
    placeholder: 'Enter provider name',
    input: 'text',
    group: 'C',
    width: 'half'
  },
  'ordering.npi': {
    path: 'ordering.npi',
    label: 'NPI',
    placeholder: 'Enter 10-digit NPI',
    input: 'text',
    validate: validateNPI,
    group: 'C',
    width: 'half'
  },
  'ordering.location.name': {
    path: 'ordering.location.name',
    label: 'Location Name',
    placeholder: 'Enter location name',
    input: 'text',
    group: 'C',
    width: 'full'
  },
  'ordering.location.address.street': {
    path: 'ordering.location.address.street',
    label: 'Street Address',
    placeholder: 'Enter street address',
    input: 'address',
    group: 'C',
    width: 'full'
  },
  'ordering.location.address.city': {
    path: 'ordering.location.address.city',
    label: 'City',
    placeholder: 'Enter city',
    input: 'address',
    group: 'C',
    width: 'third'
  },
  'ordering.location.address.state': {
    path: 'ordering.location.address.state',
    label: 'State',
    placeholder: 'State',
    input: 'address',
    group: 'C',
    width: 'third'
  },
  'ordering.location.address.zip': {
    path: 'ordering.location.address.zip',
    label: 'ZIP Code',
    placeholder: '12345 or 12345-6789',
    input: 'address',
    validate: validateZip,
    group: 'C',
    width: 'third'
  },

  // D. Specimen
  'specimen.id': {
    path: 'specimen.id',
    label: 'Specimen ID',
    placeholder: 'Enter specimen ID',
    required: true,
    input: 'text',
    group: 'D',
    width: 'half'
  },
  'specimen.control_id': {
    path: 'specimen.control_id',
    label: 'Control ID',
    placeholder: 'Enter control ID',
    input: 'text',
    group: 'D',
    width: 'half'
  },
  'specimen.type': {
    path: 'specimen.type',
    label: 'Specimen Type',
    placeholder: 'e.g., Serum, Plasma, Urine',
    input: 'text',
    group: 'D',
    width: 'half'
  },
  'specimen.collected_at': {
    path: 'specimen.collected_at',
    label: 'Collected Date/Time',
    placeholder: 'MM/DD/YYYY HH:MM AM/PM',
    input: 'datetime',
    group: 'D',
    width: 'half'
  },
  'specimen.received_at': {
    path: 'specimen.received_at',
    label: 'Received Date/Time',
    placeholder: 'MM/DD/YYYY HH:MM AM/PM',
    input: 'datetime',
    group: 'D',
    width: 'half'
  },
  'specimen.entered_at': {
    path: 'specimen.entered_at',
    label: 'Entered Date/Time',
    placeholder: 'MM/DD/YYYY HH:MM AM/PM',
    input: 'datetime',
    group: 'D',
    width: 'half'
  },
  'specimen.reported_at': {
    path: 'specimen.reported_at',
    label: 'Reported Date/Time',
    placeholder: 'MM/DD/YYYY HH:MM AM/PM',
    input: 'datetime',
    group: 'D',
    width: 'half'
  },

  // E. Report Meta
  'report.clinical_info': {
    path: 'report.clinical_info',
    label: 'Clinical Information',
    placeholder: 'Enter clinical information',
    description: 'Additional clinical context or notes',
    input: 'textarea',
    group: 'E',
    width: 'full'
  },
  'report.comments': {
    path: 'report.comments',
    label: 'Comments',
    placeholder: 'Enter comments',
    description: 'General comments or notes about the report',
    input: 'textarea',
    group: 'E',
    width: 'full'
  },
  'report.ordered_items': {
    path: 'report.ordered_items',
    label: 'Ordered Items',
    placeholder: 'Enter ordered items',
    description: 'Comma-separated if a list',
    input: 'textarea',
    group: 'E',
    width: 'full'
  }
}

// Section definitions
export const SECTIONS: SectionDef[] = [
  {
    key: 'A',
    title: 'Lab / Vendor Envelope',
    subtitle: 'Laboratory and vendor information',
    description: 'Basic information about the laboratory and report metadata',
    fields: [
      'vendor.name',
      'vendor.account_number',
      'vendor.address.street',
      'vendor.address.city',
      'vendor.address.state',
      'vendor.address.zip',
      'vendor.phone',
      'vendor.fax',
      'report.id',
      'report.page',
      'report.page_count',
      'performing_lab.name',
      'performing_lab.clia',
      'performing_lab.director',
      'performing_lab.address.street',
      'performing_lab.address.city',
      'performing_lab.address.state',
      'performing_lab.address.zip'
    ]
  },
  {
    key: 'B',
    title: 'Patient',
    subtitle: 'Patient demographics and contact information',
    description: 'Patient identification and demographic data',
    fields: [
      'patient.last_name',
      'patient.first_name',
      'patient.middle',
      'patient.dob',
      'patient.sex',
      'patient.mrn',
      'patient.phone',
      'patient.address.street',
      'patient.address.city',
      'patient.address.state',
      'patient.address.zip',
      'patient.age_at_collection'
    ]
  },
  {
    key: 'C',
    title: 'Ordering / Provider',
    subtitle: 'Healthcare provider and ordering information',
    description: 'Information about the ordering provider and location',
    fields: [
      'ordering.provider_name',
      'ordering.npi',
      'ordering.location.name',
      'ordering.location.address.street',
      'ordering.location.address.city',
      'ordering.location.address.state',
      'ordering.location.address.zip'
    ]
  },
  {
    key: 'D',
    title: 'Specimen',
    subtitle: 'Specimen collection and processing information',
    description: 'Details about specimen collection, handling, and processing times',
    fields: [
      'specimen.id',
      'specimen.control_id',
      'specimen.type',
      'specimen.collected_at',
      'specimen.received_at',
      'specimen.entered_at',
      'specimen.reported_at'
    ]
  },
  {
    key: 'E',
    title: 'Report Meta',
    subtitle: 'Additional report information',
    description: 'Clinical context, comments, and ordered items',
    fields: [
      'report.clinical_info',
      'report.comments',
      'report.ordered_items'
    ]
  }
]

// Helper constants and functions
export const SECTION_ORDER = ['A', 'B', 'C', 'D', 'E']

export function fieldsForSection(key: string): FieldDef[] {
  const section = SECTIONS.find(s => s.key === key)
  if (!section) return []

  return section.fields.map(fieldPath => FIELDS[fieldPath]).filter(Boolean)
}