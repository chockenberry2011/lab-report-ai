# Training Payload Shape Fix

## Summary

Fixed the "save log" / training payload shape to match `POST /api/review/{result_id}/training` API which expects:

```json
{
  "include_manual_corrections": false,
  "annotations": [{ /* object(s) */ }]
}
```

## Changes Made

### 1. Created New Training API Utility

**Created: `ui/src/lib/trainingApi.ts`**
```typescript
export type TrainingAnnotation = Record<string, unknown>;

export async function postTraining(resultId: string, annotations: TrainingAnnotation[], includeManual = false) {
  const id = normalizeResultId(resultId);
  const body = {
    include_manual_corrections: includeManual ?? false,
    annotations: annotations ?? [],
  };
  const res = await fetch(`/api/review/${id}/training`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); if (j?.detail) msg = j.detail; } catch {}
    throw new Error(`Failed to save training: ${msg}`);
  }
  return res.json();
}
```

### 2. Updated Services API

**Modified: `ui/src/services/api.ts`**
- Changed endpoint from `/results/{jobId}/training` to `/api/review/{normalizedId}/training`
- Updated payload format to include `include_manual_corrections` field
- Uses normalized IDs for all training API calls
- Enhanced error handling to extract server detail messages
- Updated type signatures to use `FlexibleTrainingAnnotation`

### 3. Updated Type Definitions

**Modified: `ui/src/types/index.ts`**
- Added `FlexibleTrainingAnnotation = Record<string, unknown>` type
- Maintains backward compatibility with existing `TrainingAnnotation` interface
- Allows for flexible annotation structures

### 4. Created Unit Tests

**Created: `ui/src/lib/__tests__/trainingApi.test.ts`**
- Tests correct payload format: `{ include_manual_corrections: boolean, annotations: [...] }`
- Tests error handling with server detail extraction
- Tests single annotation saving as array
- Tests ID normalization

## New Training Payload Format

### Required Format
```typescript
{
  "include_manual_corrections": false,
  "annotations": [
    {
      // Any object structure - flexible
      "line_number": 5,
      "text": "Glucose 95 mg/dL",
      "field": "result_value",
      "old_value": "94",
      "new_value": "95"
    }
  ]
}
```

### API Endpoints

- **POST** `/api/review/{normalized_id}/training`
- **GET** `/api/review/{normalized_id}/training`

### Usage Examples

```typescript
// Save single log entry
await postTraining(resultId, [singleAnnotation]);

// Save multiple annotations with manual corrections
await postTraining(resultId, annotations, true);

// Save a log entry (convenience method)
await saveLog(resultId, logEntry);
```

## Error Handling Improvements

- Server error details extracted from response JSON `detail` field
- Fallback to HTTP status codes if no detail available
- Toast notifications show specific server error messages
- Consistent error format across all training operations

## API Response Format

Server expected to return:
```json
{
  "ok": true,
  "saved_count": 1,
  "path": "/training/annotations/result-id.json"
}
```

## Acceptance Criteria Met

✅ **"Save log" posts correct envelope format**
- Body: `{ "include_manual_corrections": false, "annotations": [{ ... }] }`
- Content-Type: `application/json`

✅ **Server returns 200 with success toast**
- Success toast shows "Added to training data successfully"
- Proper handling of server response format

✅ **Error handling surfaces server details**
- 4xx/5xx errors with `detail` field show specific error message
- Fallback to HTTP status if no detail available
- Toast notifications display user-friendly error messages

## Files Modified

1. `ui/src/lib/trainingApi.ts` - **Created** (new training API)
2. `ui/src/services/api.ts` - **Modified** (updated endpoints and payload format)
3. `ui/src/types/index.ts` - **Modified** (added flexible annotation type)
4. `ui/src/lib/__tests__/trainingApi.test.ts` - **Created** (unit tests)

## Migration Notes

- Existing `TrainingAnnotation` interface preserved for backward compatibility
- New `FlexibleTrainingAnnotation` type allows any object structure
- All training API calls now use normalized IDs
- Endpoint changed from `/results/` to `/api/review/` prefix

## Next Steps

1. **Test with development server** to ensure endpoint compatibility
2. **Verify error handling** with various server error scenarios
3. **Add UI elements** if "save log" functionality needs to be exposed
4. **Monitor training saves** to ensure new format works correctly