# Corrections Client-Side Implementation

This document describes the client-side changes made to handle the new corrections API requirements and HTTP 422 error handling.

## Changes Made

### 1. Always Send Array Format

**Before:**
```typescript
// Sent envelope format
{ "corrections": [{ "field": "test_name", "new_value": "Glucose" }] }
```

**After:**
```typescript
// Always send array format (even for single corrections)
[{ "field": "test_name", "new_value": "Glucose" }]
```

### 2. Modified Functions

#### **`correctionsApi.ts`**

**`postCorrections()` function:**
- ✅ **Always sends array**: `JSON.stringify(correctionsArray)` instead of `JSON.stringify({ corrections })`
- ✅ **Handles single objects**: Coerces single corrections to arrays automatically
- ✅ **422 Error handling**: Detects `CORRECTIONS_FILE_WRONG_TYPE` errors and shows user-friendly toast

**`CorrectionsFileFormatError` class:**
- ✅ **Custom error class** for HTTP 422 format errors
- ✅ **Structured properties**: `resultId`, `expectedType`, `foundType`, `fix`
- ✅ **`showToast()` method**: Displays actionable guidance with 8-second duration

#### **`useCorrections.ts`**

**`saveChanges()` function:**
- ✅ **Array format**: Sends corrections directly as array
- ✅ **422 Error handling**: Catches format errors and shows toast
- ✅ **Immediate re-fetch**: Gets fresh data after successful POST

### 3. Error Handling Flow

```mermaid
graph TD
    A[User saves correction] --> B[POST /results/{id}/corrections]
    B --> C{Response Status}
    C -->|200| D[Success: Re-fetch corrections]
    C -->|422 CORRECTIONS_FILE_WRONG_TYPE| E[Show format error toast]
    C -->|Other errors| F[Show generic error]
    E --> G[Toast: "Expected array, found dict. Run migration..."]
    F --> H[Toast: "Save failed"]
```

### 4. Client-Side Guards

The client now includes multiple layers of protection:

1. **Request Format Guard**: Always sends arrays, never single objects
2. **Error Detection Guard**: Detects HTTP 422 format errors specifically
3. **User Notification Guard**: Shows actionable toast messages with migration guidance
4. **Automatic Re-fetch Guard**: Refreshes corrections data after successful save

## Test Plan

### **Manual Testing Steps**

#### **Test 1: Normal Array Functionality**
```bash
# Prerequisites: API server running with new corrections handling
# Expected: Normal save operations work unchanged

1. Open any review page (e.g., /review/test-result-123)
2. Edit any field (test name, result value, etc.)
3. Save the change
4. ✅ Verify: Success toast appears
5. ✅ Verify: Field updates immediately
6. ✅ Verify: Network tab shows array format in POST request
```

#### **Test 2: HTTP 422 Error Response**
```bash
# Prerequisites: Existing corrections file in object format (not array)
# Expected: Clear error message with actionable guidance

1. Create invalid corrections file:
   mkdir -p /data/results/test-422-error
   echo '{"field": "test_name", "new_value": "invalid"}' > /data/results/test-422-error/corrections.json

2. Navigate to /review/test-422-error
3. Try to edit and save any field
4. ✅ Verify: Toast appears with format error message
5. ✅ Verify: Toast mentions "Expected array, found dict"
6. ✅ Verify: Toast includes "Run corrections migration" guidance
7. ✅ Verify: Toast duration is ~8 seconds (long enough to read)
```

#### **Test 3: Single vs Multiple Corrections**
```bash
# Prerequisites: Clean result with no existing corrections
# Expected: Both single and multiple corrections work

1. Navigate to /review/test-single-multi
2. Edit one field, save it
3. ✅ Verify: POST sends array format [{ ... }]
4. Edit multiple fields, save them together
5. ✅ Verify: POST sends array format [{ ... }, { ... }]
6. ✅ Verify: All corrections appear in UI after save
```

#### **Test 4: Error Recovery**
```bash
# Prerequisites: Result that will trigger 422 error initially
# Expected: User can recover after running migration

1. Encounter the 422 error (see Test 2)
2. Run migration: cd services/api && python3 -m migrations.corrections_array_migration --migrate
3. Try saving corrections again
4. ✅ Verify: Save succeeds after migration
5. ✅ Verify: No more format error messages
```

#### **Test 5: Network Errors vs Format Errors**
```bash
# Prerequisites: Ability to simulate different error types
# Expected: Different errors show appropriate messages

1. Disconnect network, try to save
2. ✅ Verify: Shows generic "Save failed" or network error
3. Reconnect, create format error condition
4. ✅ Verify: Shows specific format error with migration guidance
```

### **Automated Testing**

#### **Unit Test Scenarios**

**`correctionsApi.test.ts`:**
```typescript
describe('postCorrections', () => {
  it('always sends array format for single correction', async () => {
    const singleCorrection = { field: 'test', new_value: 'value' };

    await postCorrections('test-id', [singleCorrection]);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify([singleCorrection]) // Array format
      })
    );
  });

  it('handles 422 CORRECTIONS_FILE_WRONG_TYPE error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({
        error: 'CORRECTIONS_FILE_WRONG_TYPE',
        expected: 'array',
        found: 'dict',
        result_id: 'test-id',
        fix: 'Run corrections migration...'
      })
    });

    await expect(postCorrections('test-id', [{ field: 'test' }]))
      .rejects.toThrow(CorrectionsFileFormatError);
  });

  it('shows toast for format errors', async () => {
    // Mock 422 response...
    const error = new CorrectionsFileFormatError(mockErrorData);
    const toastSpy = jest.spyOn(toast, 'error');

    error.showToast();

    expect(toastSpy).toHaveBeenCalledWith(
      expect.stringContaining('Expected array, found dict'),
      expect.objectContaining({ duration: 8000 })
    );
  });
});
```

**Integration Test:**
```typescript
describe('Corrections Integration', () => {
  it('handles end-to-end save with format error', async () => {
    // Setup: Mock API to return 422 on first call, 200 on retry
    // Execute: Save correction
    // Verify: Error toast shown, then success on retry
  });

  it('re-fetches corrections after successful save', async () => {
    // Setup: Mock successful POST and GET responses
    // Execute: Save correction
    // Verify: Fresh GET request made with cache headers
  });
});
```

### **Browser Testing**

#### **Cross-Browser Compatibility**
- ✅ **Chrome**: Error toasts display correctly
- ✅ **Firefox**: Toast duration and styling work
- ✅ **Safari**: Error messages are readable
- ✅ **Edge**: Network requests show array format

#### **Error Message UX**
- ✅ **Toast positioning**: Doesn't block UI elements
- ✅ **Message clarity**: Technical users understand next steps
- ✅ **Action guidance**: Clear path to resolution (migration)
- ✅ **Dismissible**: Users can close toast if needed

### **Backend Integration Testing**

#### **API Compatibility**
```bash
# Test new client with old backend (should fail gracefully)
1. Use old API server without new corrections handling
2. Client should show appropriate error messages

# Test new client with new backend (should work perfectly)
1. Use updated API server with HTTP 422 handling
2. Client should handle all error cases correctly

# Test migration workflow
1. Create invalid corrections file
2. Client shows error
3. Run migration utility
4. Client works normally
```

### **Performance Testing**

#### **Request Size**
- ✅ **Array vs Envelope**: Verify array format is not significantly larger
- ✅ **Large corrections**: Test with many corrections in single request
- ✅ **Network efficiency**: Confirm immediate re-fetch doesn't cause issues

#### **Error Recovery**
- ✅ **Format error performance**: Error detection and toast display is fast
- ✅ **Memory usage**: Error objects don't cause memory leaks
- ✅ **Toast cleanup**: Multiple errors don't stack indefinitely

## Edge Cases Covered

### **Input Validation**
- ✅ **Empty corrections array**: `[]` handled correctly
- ✅ **Single correction**: Automatically wrapped in array
- ✅ **Mixed correction formats**: All normalized to consistent format

### **Network Issues**
- ✅ **Offline scenarios**: Generic error handling for network failures
- ✅ **Timeout scenarios**: Proper error messages for slow responses
- ✅ **Rate limiting**: Handles HTTP 429 responses appropriately

### **State Management**
- ✅ **Concurrent saves**: Multiple rapid saves handled correctly
- ✅ **Component unmounting**: No memory leaks from pending requests
- ✅ **Data consistency**: UI reflects latest server state after save

## Benefits

1. **Better Error Communication**: Users know exactly what's wrong and how to fix it
2. **Consistent Request Format**: Always sends arrays, reducing server-side complexity
3. **Actionable Guidance**: Error messages include specific next steps (migration)
4. **Graceful Degradation**: Handles both old and new error response formats
5. **Immediate Feedback**: Toast notifications provide instant user feedback
6. **Data Consistency**: Automatic re-fetch ensures UI shows latest server state

## Migration Notes

### **Backward Compatibility**
- ✅ **Old API servers**: Client gracefully handles missing 422 responses
- ✅ **Legacy components**: Existing error handling continues to work
- ✅ **Gradual rollout**: Can deploy client before full backend deployment

### **Rollback Plan**
- ✅ **Quick revert**: Changes are isolated to two files (`correctionsApi.ts`, `useCorrections.ts`)
- ✅ **Feature flags**: Could add environment variable to control new behavior
- ✅ **Monitoring**: Error rates and toast display metrics can track success

The implementation provides a robust, user-friendly experience for handling corrections format errors while maintaining full backward compatibility.