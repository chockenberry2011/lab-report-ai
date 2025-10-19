export const FALLBACK_SECTIONS = [
  { key: 'A', title: 'Envelope', fields: ['vendor.name','report.id'] },
  { key: 'B', title: 'Patient', fields: ['patient.first_name','patient.last_name','patient.dob'] },
]

export const FALLBACK_FIELDS: Record<string, any> = {
  'vendor.name': { path:'vendor.name', label:'Vendor Name', input:'text' },
  'report.id': { path:'report.id', label:'Report ID', input:'text' },
  'patient.first_name': { path:'patient.first_name', label:'First Name', input:'text' },
  'patient.last_name': { path:'patient.last_name', label:'Last Name', input:'text' },
  'patient.dob': { path:'patient.dob', label:'DOB', input:'date' },
}