# Testing Guide - Enhanced Corrections System

## Quick Start

### Basic Tests (No Setup Required)
```bash
cd ui
node run-basic-tests.cjs
```
This runs core logic tests without any dependencies.

### Full Test Suite (Requires Setup)
1. Install test dependencies:
```bash
cd ui
npm install -D jest ts-jest @testing-library/react @testing-library/jest-dom jest-environment-jsdom @types/jest
```

2. Add test scripts to package.json:
```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  }
}
```

3. Run tests:
```bash
npm test
```

## Manual QA Testing

Follow the comprehensive checklist in `QA.md`:
- [ ] Field editing for all schema sections
- [ ] Persistence across page reloads
- [ ] API integration verification
- [ ] Backward compatibility checks

## Integration Testing

### API Testing
```bash
cd ui
node test-enhanced-corrections.js [result-id]
```

### Example Test Scenarios
1. **Patient Field Edit**:
   - Edit patient.first_name → "Alice"
   - Save → Reload → Verify persistence

2. **Vendor Field Unset**:
   - Unset vendor.address.city
   - Reload → Verify field is empty/absent

3. **Mixed Format**:
   - Edit both new schema fields and legacy test rows
   - Verify both save correctly

## Test Coverage

### Unit Tests
- ✅ `corrections.test.ts` - API helper functions
- ✅ `EditableField.test.tsx` - Component behavior
- ✅ `fields-spec.test.ts` - Field definitions

### Integration Tests
- ✅ `test-enhanced-corrections.js` - End-to-end API testing
- ✅ `run-basic-tests.cjs` - Core logic validation

### Manual Tests
- ✅ `QA.md` - Comprehensive manual testing checklist

## Test Data

### Sample Corrections Payload (New Format)
```json
{
  "items": [
    {"op": "set", "path": "patient.first_name", "value": "Alice"},
    {"op": "unset", "path": "patient.mrn"},
    {"op": "set", "path": "specimen.collected_at", "value": "2024-09-01T08:30:00"}
  ]
}
```

### Sample Legacy Payload (Backward Compatible)
```json
{
  "corrections": [
    {"line_number": 5, "field": "test_name", "new_value": "Glucose"}
  ]
}
```

## Expected Test Results

### API Responses
- **POST /api/results/{id}/corrections**: `{"ok": true}`
- **GET /api/results/{id}/corrections**: `{"items": [...], "schema_version": 1}`
- **GET /api/results/{id}**: Merged result with corrections applied

### UI Behavior
- **Optimistic Updates**: Changes appear immediately
- **Error Handling**: Network errors show user-friendly messages
- **Loading States**: Save operations show loading indicators

## Debugging Tips

### Common Issues
1. **CORS Errors**: Check API base URL configuration
2. **Type Mismatches**: Verify field types match expected input types
3. **Path Resolution**: Test path parsing with complex nested objects

### Debug Tools
1. Browser DevTools → Network tab for API calls
2. React DevTools for component state
3. Console logs for correction payload inspection

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    cd ui
    npm ci
    npm run test:ci
    node run-basic-tests.cjs
```

### Docker Testing
```bash
docker-compose run --rm ui npm test
```

The testing strategy covers both automated unit/integration tests and comprehensive manual QA to ensure reliability of the enhanced corrections system.