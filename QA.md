# Manual QA — Editable Fields

## Prerequisites
- Backend API running with enhanced corrections system
- UI built and served (dev or production)
- At least one processed lab report available for testing

## Test Cases

### 🔍 **Field Editing - North Star Schema**

#### Patient Fields
- [ ] **patient.first_name** → Edit → Save → Reload page → Value persists
- [ ] **patient.last_name** → Edit → Save → Reload page → Value persists  
- [ ] **patient.dob** → Edit (date format) → Save → Reload → Value persists
- [ ] **patient.mrn** → Edit → Save → Reload → Value persists
- [ ] **patient.mrn** → Unset → Reload → Field is absent/empty

#### Vendor/Lab Fields
- [ ] **vendor.name** → Edit → Save → Reload → Value persists
- [ ] **vendor.address.city** → Edit → Save → Reload → Value persists
- [ ] **vendor.address.city** → Unset → Reload → Field is absent/empty
- [ ] **performing_lab.clia** → Edit → Save → Reload → Value persists

#### Specimen Fields  
- [ ] **specimen.collected_at** → Edit → Save → Reload → Value persists
- [ ] **specimen.type** → Edit → Save → Reload → Value persists
- [ ] **specimen.id** → Unset → Reload → Field is absent/empty

#### Provider Fields
- [ ] **ordering.provider_name** → Edit → Save → Reload → Value persists
- [ ] **ordering.npi** → Edit → Save → Reload → Value persists

#### Report Meta Fields
- [ ] **report.clinical_info** → Edit → Save → Reload → Value persists
- [ ] **report.comments** → Edit → Save → Reload → Value persists

### 🧪 **Legacy Panel/Test Editing (Backward Compatibility)**
- [ ] **panels[0].name** → Edit → Save → Reload → Value persists
- [ ] **panels[0].tests[0].test_name** → Edit → Save → Reload → Value persists
- [ ] **panels[0].tests[0].result_value** → Edit → Save → Reload → Value persists
- [ ] **panels[0].tests[0].units** → Edit → Save → Reload → Value persists
- [ ] **panels[0].tests[0].flag** → Edit → Save → Reload → Value persists

### 🔧 **UI Behavior**
- [ ] **Inline Editing**: Click field → Input appears → Can type
- [ ] **Save Action**: Save button works → Shows success feedback
- [ ] **Cancel Action**: Cancel button reverts changes without saving
- [ ] **Unset Action**: Unset button removes field value
- [ ] **Error Handling**: Network errors show appropriate error messages
- [ ] **Loading States**: Save operations show loading indicators
- [ ] **Optimistic Updates**: UI updates immediately before server confirmation

### 📡 **API Integration**

#### Corrections Storage
- [ ] **GET /api/results/{id}/corrections** returns saved corrections
- [ ] **New format**: Returns `{"items": [...], "schema_version": 1}`
- [ ] **Legacy format**: Still works for backward compatibility
- [ ] **Mixed corrections**: Both new path-based and legacy line-based corrections appear

#### Corrections Format Verification
- [ ] **New corrections** have `{"op": "set", "path": "...", "value": "..."}`
- [ ] **Unset corrections** have `{"op": "unset", "path": "..."}`
- [ ] **Legacy corrections** have `{"line_number": N, "field": "...", "new_value": "..."}`

#### Server-Side Application
- [ ] **Structured JSON route** (`/api/results/{id}`) returns merged values
- [ ] **Server applies corrections** before returning composed JSON
- [ ] **New corrections** properly merge into result structure
- [ ] **Legacy corrections** still apply to test rows correctly

### 🔄 **Cross-Browser Testing**
- [ ] **Chrome**: All functionality works
- [ ] **Firefox**: All functionality works  
- [ ] **Safari**: All functionality works
- [ ] **Edge**: All functionality works

### 📱 **Responsive Design**
- [ ] **Desktop**: Edit fields work properly in full layout
- [ ] **Tablet**: UI adapts and editing still functional
- [ ] **Mobile**: Touch interactions work for field editing

### ⚡ **Performance**
- [ ] **Page Load**: Review page loads quickly with many editable fields
- [ ] **Save Performance**: Corrections save within reasonable time (<2s)
- [ ] **Optimistic Updates**: UI feels responsive during saves

### 🛡️ **Error Scenarios**
- [ ] **Network Down**: Appropriate error when API unreachable
- [ ] **Invalid Data**: Proper validation for malformed input
- [ ] **Concurrent Edits**: Multiple field edits don't interfere
- [ ] **Session Timeout**: Graceful handling of auth issues

### 🔍 **Data Integrity**
- [ ] **No Data Loss**: Original values preserved when editing fails
- [ ] **Correct Persistence**: Saved values exactly match what was entered  
- [ ] **Type Safety**: Date fields enforce date format, numbers accept numeric input
- [ ] **Unicode Support**: Non-ASCII characters (accents, symbols) save correctly

## Regression Testing

### Existing Functionality
- [ ] **Old test row editing** still works exactly as before
- [ ] **Panel editing** functionality unchanged
- [ ] **Header field editing** continues to work
- [ ] **Save corrections button** saves both old and new style corrections
- [ ] **Training data** functionality unaffected

## Test Data Setup

### Sample Test Paths
```javascript
// Patient fields
"patient.first_name" → "Alice"
"patient.last_name" → "Johnson" 
"patient.dob" → "1985-03-15"
"patient.mrn" → "MRN123456"

// Vendor fields  
"vendor.name" → "Quest Diagnostics"
"vendor.address.city" → "San Francisco"
"vendor.phone" → "(555) 123-4567"

// Specimen fields
"specimen.collected_at" → "2024-09-01T08:30:00"
"specimen.type" → "Serum"
"specimen.id" → "ACC789123"

// Provider fields
"ordering.provider_name" → "Dr. Smith"
"ordering.npi" → "1234567890"
```

## Expected API Payloads

### New Format POST
```json
{
  "items": [
    {"op": "set", "path": "patient.first_name", "value": "Alice"},
    {"op": "unset", "path": "patient.mrn"},
    {"op": "set", "path": "specimen.collected_at", "value": "2024-09-01T08:30:00"}
  ]
}
```

### Legacy Format POST (still supported)
```json
{
  "corrections": [
    {"line_number": 5, "field": "test_name", "new_value": "Glucose", "old_value": "GLU"}
  ]
}
```

## Sign-off Checklist

- [ ] **Core editing** works for all field types
- [ ] **Persistence** confirmed across page reloads  
- [ ] **API integration** properly saves and retrieves
- [ ] **Backward compatibility** preserved for existing workflows
- [ ] **Error handling** graceful and user-friendly
- [ ] **Performance** acceptable for production use
- [ ] **Cross-browser** functionality verified

---
**QA Completed By**: ________________  
**Date**: ________________  
**Build/Version**: ________________  
**Notes**: ________________