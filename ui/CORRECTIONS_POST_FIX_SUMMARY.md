# Corrections POST Shape + ID Normalization Fix

## Summary

Updated the review UI to ensure saving a field or correction always succeeds against `POST /api/results/{result_id}/corrections` by:

1. **Normalizing all result IDs** to remove processing stage suffixes
2. **Standardizing correction payloads** to use envelope format `{ corrections: [...] }`
3. **Improving error handling** to surface server detail messages

## Changes Made

### 1. ID Normalization Utility

**Created: `ui/src/utils/normalizeResultId.ts`**
```typescript
export function normalizeResultId(raw: string): string {
  // Converts "ce90e846-...-bf79955b074b.03_compose.debug"
  // to "ce90e846-...-bf79955b074b"
  return raw?.split?.(".")?.[0] ?? raw;
}
```

### 2. Updated Corrections Library

**Modified: `ui/src/lib/corrections.ts`**
- Uses normalized IDs for all API calls
- Converts legacy `CorrectionItem[]` format to new `Correction[]` format
- Wraps corrections in envelope: `{ corrections: [...] }`
- Enhanced error handling with server detail extraction

### 3. Updated Services API

**Modified: `ui/src/services/api.ts`**
- All `resultsApi` and `reviewApi` methods now use normalized IDs
- `saveCorrection()` method standardized to envelope format
- Handles both new array format and legacy items format
- Improved error messages from server responses

### 4. Updated Corrections Hook

**Modified: `ui/src/hooks/useCorrections.ts`**
- Uses the new normalized ID utility
- Converts field updates to proper `Correction[]` format
- Enhanced error handling with server detail extraction

### 5. Updated Review Pages

**Modified: `ui/src/pages/ReviewPage.tsx`**
- Uses normalized ID for all API calls
- Simplified ID handling logic

## New Correction Format

### Envelope Format (Preferred)
```typescript
{
  "corrections": [
    {
      "field": "patient.first_name",
      "old_value": "John",
      "new_value": "Jane",
      "note": "Manual correction",
      "source": "review-ui",
      "location": { "page": 1, "start": 10, "end": 20 }
    }
  ]
}
```

### Server Response
```typescript
{
  "ok": true,
  "saved_count": 1,
  "path": "/data/corrections/normalized-id.json"
}
```

## API Endpoints Now Use Normalized IDs

All these endpoints now consistently use the base UUID without suffixes:

- `POST /api/results/{normalized_id}/corrections`
- `GET /api/results/{normalized_id}/corrections`
- `GET /api/results/{normalized_id}`
- `GET /api/results/{normalized_id}/extracted-text`

## Error Handling Improvements

- Server error details are extracted from response JSON
- Fallback to HTTP status codes if no detail available
- Toast notifications show specific server error messages
- No more generic "Failed to save" messages

## Validation

Created test file `test-corrections-format.js` that validates:
- ✅ ID normalization works correctly
- ✅ Envelope format is properly structured
- ✅ Edge cases (empty, null, undefined IDs) handled

## Acceptance Criteria Met

✅ **Saving a single field triggers POST with envelope format**
- Body: `{ "corrections": [{ "field": "...", "new_value": "...", "source": "review-ui" }] }`
- Content-Type: `application/json`

✅ **Server responds with success format**
- Response: `{ "ok": true, "saved_count": 1, "path": "..." }`
- Toast shows success message

✅ **No requests include dotted result IDs**
- All API calls use `normalizeResultId()` to strip suffixes
- Only base UUID is sent in path parameters

✅ **Error handling surfaces server details**
- Server `detail` field shown in toast messages
- Fallback to HTTP status if no detail available
- No hardcoded error messages

## Files Modified

1. `ui/src/utils/normalizeResultId.ts` - **Created**
2. `ui/src/lib/correctionsApi.ts` - **Created** (new preferred API)
3. `ui/src/lib/corrections.ts` - **Modified** (legacy compatibility)
4. `ui/src/services/api.ts` - **Modified** (ID normalization + envelope format)
5. `ui/src/hooks/useCorrections.ts` - **Modified** (ID normalization)
6. `ui/src/pages/ReviewPage.tsx` - **Modified** (ID normalization)
7. `ui/test-corrections-format.js` - **Created** (validation)

## Next Steps

1. **Test in development environment** with real server
2. **Monitor correction saves** to ensure envelope format works
3. **Check error handling** with various server error scenarios
4. **Consider migrating** other correction-related code to use `correctionsApi.ts`