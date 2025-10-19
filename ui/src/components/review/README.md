# Review System - Adding New Fields

This document explains how to add new editable fields to the lab report review system.

## Overview

The review system allows manual editing of extracted lab report data with:
- **Autosave**: Changes are automatically saved 1.5 seconds after editing
- **Three-layer state**: Extracted → Corrections → Effective values
- **Reset functionality**: Reset individual fields to extracted values
- **Status indicators**: Visual feedback for save status
- **Edge case handling**: Fields can be set even if not in extracted data

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Extracted Data │    │   Corrections    │    │ Effective Value │
│                 │───▶│                  │───▶│                 │
│ (from pipeline) │    │ (user edits via  │    │ (what user sees)│
│                 │    │  POST /api/...)  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Adding a New Field

### 1. Add Field Definition

Edit `ui/src/lib/field-definitions.ts`:

```typescript
export const FIELD_DEFINITIONS: FieldDefinition[] = [
  // ... existing fields

  // Add your new field
  {
    key: 'new_field_key',           // Unique identifier
    label: 'Display Label',         // What users see
    type: 'text',                   // 'text' | 'date' | 'phone' | 'number' | 'select'
    section: 'patient',             // 'envelope' | 'patient' | 'provider' | 'specimen' | 'report'
    path: 'patient.new_field',      // JSON path in extracted data
    helperText: 'Optional help'     // Optional tooltip text
  },
]

// Add to path mapping for API
export const FIELD_PATH_MAP: Record<string, { path: string; jsonPointer: string; type: string }> = {
  // ... existing mappings

  new_field_key: {
    path: 'patient.new_field',
    jsonPointer: '/patient/new_field',  // JSON Pointer format for corrections API
    type: 'text'
  },
}
```

### 2. Field Types

Each field type has specific behavior:

- **`text`**: Basic string input with trim normalization
- **`phone`**: Formats as `(555) 123-4567`, validates 10+ digits
- **`date`**: Date picker input, validates and formats as `YYYY-MM-DD`
- **`number`**: Numeric input with validation
- **`select`**: Dropdown with predefined options (define in `FieldRow.tsx`)

### 3. Add Select Options (if needed)

If your field type is `select`, edit `ui/src/components/review/FieldRow.tsx`:

```typescript
const getSelectOptions = (): string[] | undefined => {
  if (definition.key === 'patient_sex') {
    return ['M', 'F', 'Male', 'Female', 'Other', 'Unknown']
  }
  if (definition.key === 'your_new_select_field') {
    return ['Option1', 'Option2', 'Option3']
  }
  return undefined
}
```

### 4. Update Section Rendering

The field will automatically appear in the appropriate section based on the `section` property. Sections are defined in `ReviewPage.tsx`:

- `envelope`: Lab and vendor information
- `patient`: Patient demographics
- `provider`: Ordering provider details
- `specimen`: Sample information
- `report`: Report metadata

## Path Format Examples

The `path` and `jsonPointer` should match your data structure:

```json
{
  "vendor": {
    "name": "Quest Diagnostics",
    "address": {
      "street": "123 Lab St"
    }
  },
  "patient": {
    "first_name": "John",
    "address": {
      "city": "Boston"
    }
  },
  "panels": [
    {
      "tests": [
        {
          "name": "Glucose",
          "value": "95"
        }
      ]
    }
  ]
}
```

Corresponding paths:
- `vendor.name` → `/vendor/name`
- `vendor.address.street` → `/vendor/address/street`
- `patient.first_name` → `/patient/first_name`
- `panels[0].tests[0].name` → `/panels/0/tests/0/name`

## API Format

When the user saves, corrections are sent to `POST /api/results/{id}/corrections` as:

```json
{
  "items": [
    {
      "op": "set",
      "path": "/patient/first_name",
      "value": "Jane"
    },
    {
      "op": "unset",
      "path": "/patient/middle"
    }
  ],
  "schema_version": 1
}
```

## Testing Your Field

1. **Load test data**: Ensure your field appears in the UI if it exists in extracted data
2. **Edit field**: Click to edit, verify autosave works (1.5s delay)
3. **Reset field**: Click reset button, verify it returns to extracted value
4. **Edge case**: Try setting a field that doesn't exist in extracted data
5. **Empty field**: Try clearing a field that had a value
6. **Validation**: For typed fields (phone, date, number), test validation

## Validation

Field validation happens in `InlineEditor.tsx`. Add custom validation if needed:

```typescript
const validateAndSave = () => {
  // ... existing validation

  if (definition.key === 'your_field' && value !== '') {
    // Add your custom validation
    if (!customValidation(value)) {
      setError('Custom validation failed')
      return
    }
  }

  onSave(value)
}
```

## Common Pitfalls

1. **Path mismatch**: Ensure `path` and `jsonPointer` match your data structure exactly
2. **Missing mapping**: Add both field definition AND path mapping
3. **Section typo**: Use exact section names: `envelope`, `patient`, `provider`, `specimen`, `report`
4. **Type validation**: Ensure field type matches expected input format
5. **Select options**: Don't forget to add options for `select` type fields

## File Summary

- `field-definitions.ts` - Add field definition and path mapping
- `FieldRow.tsx` - Add select options if needed
- `FieldSection.tsx` - Renders fields by section (no changes needed)
- `LabeledField.tsx` - Display component (no changes needed)
- `InlineEditor.tsx` - Edit component, add validation if needed
- `useCorrections.ts` - Handles save logic (no changes needed)
- `SaveStatusIndicator.tsx` - Status display (no changes needed)

The system is designed to be minimal - most new fields require only the field definition!