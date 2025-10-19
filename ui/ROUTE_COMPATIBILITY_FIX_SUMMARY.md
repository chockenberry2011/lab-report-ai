# Route Compatibility + Fetch Wrapper Fix

## Summary

Created a unified API client that ensures all callers (1) normalize IDs and (2) add consistent headers. Refactored all existing API calls to use the shared client.

## Changes Made

### 1. Created Unified API Client

**Created: `ui/src/lib/apiClient.ts`**

```typescript
// Core API wrapper with consistent headers and error handling
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const j = await res.json(); if (j?.detail) msg = j.detail; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// Specialized wrappers with automatic ID normalization
resultsApi<T>(resultId: string, endpoint: string, init?: RequestInit): Promise<T>
reviewApi<T>(resultId: string, endpoint: string, init?: RequestInit): Promise<T>
resultsFetch(resultId: string, endpoint: string, init?: RequestInit): Promise<Response>
resultsBlob(resultId: string, endpoint: string, init?: RequestInit): Promise<Blob>
```

### 2. Refactored All API Libraries

**Modified: `ui/src/lib/correctionsApi.ts`**
- Now uses `resultsApi()` instead of direct fetch
- Automatic ID normalization and header management
- Consistent error handling with server detail extraction

**Modified: `ui/src/lib/trainingApi.ts`**
- Now uses `reviewApi()` instead of direct fetch
- Automatic ID normalization and header management
- Added `getTrainingData()` method

**Modified: `ui/src/lib/corrections.ts`** (legacy)
- Converted to use `resultsApi()` wrapper
- Maintains backward compatibility

### 3. Updated Services API

**Modified: `ui/src/services/api.ts`**
- Refactored `reviewApi.saveCorrection()` to use `resultsApiClient()`
- Refactored `reviewApi.addToTraining()` to use `reviewApiClient()`
- Refactored `reviewApi.getCorrections()` and `getTrainingData()`
- Updated `resultsApi.getResult()` and `downloadResult()`
- Updated `systemApi.getStats()` to use `genericApi()`

### 4. Updated Hooks

**Modified: `ui/src/hooks/useCorrections.ts`**
- Uses `resultsFetch()` for polling (supports AbortSignal)
- Uses `resultsApiClient()` for saving corrections
- Automatic ID normalization throughout

## API Endpoint Standardization

### Corrections Endpoints
- **POST** `/api/results/{normalized_id}/corrections` ✅
- **GET** `/api/results/{normalized_id}/corrections` ✅

### Training Endpoints
- **POST** `/api/review/{normalized_id}/training` ✅
- **GET** `/api/review/{normalized_id}/training` ✅

### Results Endpoints
- **GET** `/api/results/{normalized_id}` ✅
- **GET** `/api/results/{normalized_id}/extracted-text` ✅

## Consistent Headers

All API calls now include:
```javascript
{
  "Content-Type": "application/json",
  // ... any additional headers
}
```

## ID Normalization

All API calls automatically normalize IDs:
```javascript
// Input: "ce90e846-...-bf79955b074b.03_compose.debug"
// Used:  "ce90e846-...-bf79955b074b"
```

## Error Handling

Unified error handling extracts server details:
```javascript
// Server response: { "detail": "Invalid field name" }
// Thrown error: "Invalid field name"

// Server response: HTTP 500 (no detail)
// Thrown error: "HTTP 500"
```

## Payload Formats

### Corrections (all use envelope format)
```json
{
  "corrections": [
    {
      "field": "patient.name",
      "old_value": "John",
      "new_value": "Jane",
      "source": "review-ui"
    }
  ]
}
```

### Training (all use envelope format)
```json
{
  "include_manual_corrections": false,
  "annotations": [
    {
      "line_number": 5,
      "text": "Glucose 95 mg/dL",
      "type": "correction"
    }
  ]
}
```

## Migration Benefits

1. **Consistent Headers**: All API calls now have proper Content-Type
2. **Automatic ID Normalization**: No more manual ID processing
3. **Unified Error Handling**: Consistent error message extraction
4. **Route Compatibility**: All endpoints use normalized paths
5. **Maintainability**: Single source of truth for API configuration

## Files Modified

1. `ui/src/lib/apiClient.ts` - **Created** (unified API wrapper)
2. `ui/src/lib/correctionsApi.ts` - **Modified** (use unified client)
3. `ui/src/lib/trainingApi.ts` - **Modified** (use unified client)
4. `ui/src/lib/corrections.ts` - **Modified** (use unified client)
5. `ui/src/services/api.ts` - **Modified** (use unified client)
6. `ui/src/hooks/useCorrections.ts` - **Modified** (use unified client)

## Backward Compatibility

- All existing API interfaces preserved
- Legacy correction formats still supported
- Existing error handling behavior maintained
- No breaking changes to component APIs

## Next Steps

1. **Test all API endpoints** with the unified client
2. **Monitor error handling** to ensure server details are properly surfaced
3. **Verify ID normalization** works across all use cases
4. **Consider deprecating direct fetch calls** in favor of the unified client

## Usage Examples

```typescript
// Corrections
import { postCorrections } from '@/lib/correctionsApi'
await postCorrections(resultId, [correction])

// Training
import { postTraining } from '@/lib/trainingApi'
await postTraining(resultId, [annotation])

// Direct API calls
import { resultsApi, reviewApi } from '@/lib/apiClient'
const data = await resultsApi(resultId, '/some-endpoint')
const training = await reviewApi(resultId, '/training')
```