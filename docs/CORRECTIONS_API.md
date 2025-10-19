# Corrections API Documentation

## Overview

The Corrections API provides a human-in-the-loop mechanism for refining ML extraction results. Users can submit manual corrections that are applied to the canonical document, enabling continuous model improvement through active learning.

## Core Concepts

### 1. **Corrections Log**
- Each result has a `corrections.jsonl` file
- Append-only log of all corrections
- Timestamped with actor and operation details

### 2. **Canonical Document**
- Result with corrections applied
- Stored as `canonical.json` or `{id}.03_compose.canonical.json`
- Always reflects the latest corrected state

### 3. **Path Formats**
Supports multiple path syntaxes for flexibility:
- **JSON Pointer**: `/lab_panels/0/test_rows/2/result_value`
- **Dot Notation**: `lab_panels[0].test_rows[2].result_value`
- **JSONPath**: `$.lab_panels[0].test_rows[2].result_value`

All paths are normalized to JSON Pointer internally.

## API Endpoint

### POST /results/{result_id}/corrections

Submit manual corrections for a result.

#### Request Format

```json
{
  "items": [
    {
      "path": "lab_panels[0].test_rows[2].result_value",
      "value": "95",
      "op": "replace",
      "note": "OCR misread 85 as 85"
    },
    {
      "path": "lab_panels[0].test_rows[2].flag",
      "value": "H"
    }
  ]
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items` | Array | Yes | List of correction operations |
| `items[].path` | String | Yes | JSONPath/pointer to field |
| `items[].value` | Any | Yes | New value to set |
| `items[].op` | String | No | Operation type (default: "replace") |
| `items[].note` | String | No | Human-readable explanation |

#### Response Format

**Success (200 OK)**:
```json
{
  "saved": 2,
  "bad": 0
}
```

**Validation Error (422 Unprocessable Entity)**:
```json
{
  "detail": "Invalid path: lab_panels[99].test_rows[0].value - index out of range"
}
```

## Supported Operations

### 1. **replace** (default)
Updates an existing field value.

```json
{
  "path": "/lab_panels/0/panel_name",
  "value": "COMPREHENSIVE METABOLIC PANEL",
  "op": "replace"
}
```

### 2. **add**
Adds a new field or array element.

```json
{
  "path": "/lab_panels/0/test_rows/-",
  "value": {
    "test_name": "Calcium",
    "result_value": "9.5",
    "units": "mg/dL"
  },
  "op": "add"
}
```

### 3. **remove**
Deletes a field or array element.

```json
{
  "path": "/lab_panels/0/test_rows/5",
  "op": "remove"
}
```

## Corrections File Format

### corrections.jsonl Structure

Each line is a JSON object representing one correction:

```json
{
  "ts": "2025-01-15T14:30:00.123456Z",
  "actor": "user",
  "op": "replace",
  "path": "/lab_panels/0/test_rows/2/result_value",
  "raw_path": "lab_panels[0].test_rows[2].result_value",
  "value": "95",
  "note": "OCR misread"
}
```

#### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `ts` | ISO 8601 | Timestamp when correction was made |
| `actor` | String | User or system that made the correction |
| `op` | String | Operation type (replace/add/remove) |
| `path` | String | Normalized JSON Pointer path |
| `raw_path` | String | Original path from request |
| `value` | Any | New value (omitted for remove ops) |
| `note` | String | Optional human explanation |

## Path Validation

The API validates paths before applying corrections:

1. **Path Syntax**: Must be valid JSON Pointer, JSONPath, or dot notation
2. **Path Existence**: Target location must exist in document
3. **Array Indices**: Must be within bounds (or use `-` for append)
4. **Type Safety**: Values should match expected field types

### Examples

**Valid Paths**:
```
✓ /lab_panels/0/test_rows/2/result_value
✓ lab_panels[0].test_rows[2].result_value
✓ $.lab_panels[0].test_rows[2].result_value
✓ /lab_panels/0/test_rows/-  (append)
```

**Invalid Paths**:
```
✗ lab_panels[99].test_rows[0].value  (index out of range)
✗ /lab_panels/0/nonexistent_field    (field doesn't exist)
✗ lab_panels.0.test_rows.2           (mixed syntax)
```

## Common Use Cases

### 1. Fix OCR Errors

```bash
curl -X POST http://localhost:8000/results/abc123.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "path": "lab_panels[0].test_rows[5].result_value",
      "value": "120",
      "note": "OCR read 129 as 120"
    }]
  }'
```

### 2. Add Missing Test

```bash
curl -X POST http://localhost:8000/results/abc123.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "path": "lab_panels[1].test_rows/-",
      "op": "add",
      "value": {
        "test_name": "Vitamin D",
        "result_value": "42",
        "units": "ng/mL",
        "ref_range": "30-100"
      }
    }]
  }'
```

### 3. Correct Multiple Fields

```bash
curl -X POST http://localhost:8000/results/abc123.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [
      {
        "path": "lab_panels[0].test_rows[2].result_value",
        "value": "95"
      },
      {
        "path": "lab_panels[0].test_rows[2].units",
        "value": "mg/dL"
      },
      {
        "path": "lab_panels[0].test_rows[2].flag",
        "value": "H"
      }
    ]
  }'
```

### 4. Remove Duplicate Test

```bash
curl -X POST http://localhost:8000/results/abc123.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "path": "lab_panels[0].test_rows/7",
      "op": "remove",
      "note": "Duplicate of test at index 3"
    }]
  }'
```

## Canonical Document Updates

When corrections are applied:

1. **Load Base Document**: Read original result
2. **Apply Corrections**: Execute each operation in order
3. **Save Canonical**: Write updated document
4. **Maintain Log**: Append to corrections.jsonl

### File Locations

```
/data/results/{result_id}/
  ├── result.json              # Original ML output
  ├── corrections.jsonl        # Append-only log
  └── canonical.json           # result.json + corrections
```

## Integration with UI

The React UI provides an interactive editor:

1. User views result side-by-side with PDF
2. User clicks field to edit
3. UI generates JSONPath automatically
4. User submits correction via API
5. UI reloads canonical document
6. Changes reflect immediately

## Active Learning Workflow

Corrections enable continuous model improvement:

```
1. Model makes predictions
   ↓
2. Human reviews and corrects errors
   ↓
3. Corrections logged to corrections.jsonl
   ↓
4. Periodic analysis identifies systematic errors
   ↓
5. Add failed cases to training set
   ↓
6. Retrain models
   ↓
7. Deploy improved models
```

## Error Handling

### Common Errors

**422 Unprocessable Entity**
- Invalid path syntax
- Path references non-existent location
- Array index out of bounds

**404 Not Found**
- Result ID doesn't exist

**400 Bad Request**
- Malformed JSON
- Missing required fields

### Example Error Response

```json
{
  "detail": "Invalid path: lab_panels[0].test_rows[99].value - Array index 99 is out of bounds (length: 15)"
}
```

## Best Practices

1. **Include Notes**: Always add human-readable notes for complex corrections
2. **Batch Corrections**: Submit multiple related corrections in one request
3. **Validate Paths**: Use the UI's auto-generated paths when possible
4. **Review Canonical**: Verify corrections by fetching the canonical document
5. **Audit Trail**: Preserve corrections.jsonl for compliance and debugging

## Testing Corrections

### Unit Testing

```python
import requests

def test_simple_correction():
    response = requests.post(
        'http://localhost:8000/results/test-id/corrections',
        json={
            'items': [{
                'path': 'lab_panels[0].panel_name',
                'value': 'LIPID PANEL'
            }]
        }
    )
    assert response.status_code == 200
    assert response.json()['saved'] == 1
```

### Integration Testing

```bash
# 1. Process a PDF
result_id=$(curl -X POST http://localhost:8000/upload -F "file=@test.pdf" | jq -r '.job_id')

# 2. Wait for completion
sleep 5

# 3. Apply correction
curl -X POST http://localhost:8000/results/${result_id}.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"path":"lab_panels[0].panel_name","value":"TEST PANEL"}]}'

# 4. Verify canonical document
curl http://localhost:8000/results/${result_id}.03_compose.canonical | jq '.lab_panels[0].panel_name'
# Should output: "TEST PANEL"
```

## Security Considerations

### Current Implementation
- No authentication (development only)
- No authorization (all users can correct any result)
- No rate limiting

### Production Requirements
- **Authentication**: JWT tokens or session-based
- **Authorization**: Users can only correct their own results
- **Audit**: Log user ID with corrections
- **Validation**: Strict input validation to prevent injection
- **Rate Limiting**: Prevent abuse

## Future Enhancements

1. **Undo/Redo**: Allow reverting corrections
2. **Approval Workflow**: Multi-stage review before applying
3. **Batch API**: Apply corrections to multiple results
4. **Webhooks**: Notify on correction events
5. **Conflict Resolution**: Handle concurrent corrections
6. **Export**: Download corrections for analysis

## References

- [JSON Pointer (RFC 6901)](https://tools.ietf.org/html/rfc6901)
- [JSONPath Specification](https://goessner.net/articles/JsonPath/)
- [JSON Patch (RFC 6902)](https://tools.ietf.org/html/rfc6902)
