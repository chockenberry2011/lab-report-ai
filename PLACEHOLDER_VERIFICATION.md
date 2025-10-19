# Placeholder Model System Verification

## Overview
The system now includes placeholder models that allow the worker to report "models exist" while still using rule-based fallbacks. This prevents status pages from showing "missing" models before real training is complete.

## Placeholder Structure

### Roles Model (`/models/roles/`)
```json
// metadata.json
{
  "name": "roles-placeholder",
  "version": "0.0.1",
  "trained_on": "none",
  "type": "rules-only"
}
```

```python
// loader.py
class RolesModel:
    def predict(self, lines):
        raise NotImplementedError("placeholder")
```

### TestRow Model (`/models/testrow/`)
```json
// metadata.json
{
  "name": "testrow-placeholder",
  "version": "0.0.1", 
  "trained_on": "none",
  "type": "rules-only"
}
```

```python
// loader.py
class TestRowModel:
    def predict(self, tokens):
        raise NotImplementedError("placeholder")
```

## Verification Commands

### 1. Test Model Loading
```bash
python3 -c "
import sys; sys.path.append('/path/to/lab-ai')
from services.worker.model_io import load_roles_model, load_testrow_model
r = load_roles_model(); t = load_testrow_model()
print(f'Roles: ok={r.ok}, placeholder={r.is_placeholder}')
print(f'TestRow: ok={t.ok}, placeholder={t.is_placeholder}')
"
```

**Expected Output:**
```
Roles: ok=True, placeholder=True
TestRow: ok=True, placeholder=True
```

### 2. Test Placeholder Classes
```bash
python3 -c "
import sys; sys.path.append('/models/roles')
from loader import RolesModel
try: RolesModel().predict([])
except NotImplementedError: print('✓ Roles placeholder works')
"
```

### 3. Test Health Endpoint
```bash
curl -s http://localhost:8000/healthz/models | jq '
{
  roles_exists: .roles_model_exists,
  testrow_exists: .testrow_model_exists,
  roles_placeholder: .roles_is_placeholder,
  testrow_placeholder: .testrow_is_placeholder,
  roles_ok: .roles_model_ok,
  testrow_ok: .testrow_model_ok
}
'
```

**Expected JSON:**
```json
{
  "roles_exists": true,
  "testrow_exists": true,
  "roles_placeholder": true,
  "testrow_placeholder": true,
  "roles_ok": false,
  "testrow_ok": false
}
```

## System Behavior

### Worker Startup Logging
```
roles model: PLACEHOLDER at /models/roles → using rules
testrow model: PLACEHOLDER at /models/testrow → using rules
```

### Processing Pipeline
1. **Model Detection**: Finds metadata.json ✓
2. **Loader Test**: Attempts to import and call predict()
3. **Placeholder Detection**: Catches NotImplementedError
4. **Fallback Activation**: Uses rule-based processing
5. **Status Reporting**: Reports "exists but using rules"

### Health Endpoint Response
- `*_model_exists: true` - Metadata found
- `*_is_placeholder: true` - Loader raises NotImplementedError  
- `*_model_ok: false` - Not using ML inference
- `*_used_fallback_last: true` - Last processing used rules

## Benefits

### Status Pages
- ✅ **No "missing model" alerts**
- ✅ **Clear indication of rule-based processing**
- ✅ **Transparent about placeholder status**

### Development Workflow  
- ✅ **Smooth transition from placeholders to real models**
- ✅ **No code changes needed when replacing placeholders**
- ✅ **Clear logging of processing path taken**

### Production Readiness
- ✅ **System works end-to-end with placeholders**
- ✅ **Automatic fallback to rules when models fail**
- ✅ **Transparent reporting of processing method used**

## Transition to Real Models

When real models are ready:
1. **Replace** `loader.py` with actual model implementation
2. **Update** metadata.json with real training information
3. **System automatically detects** and uses real models
4. **Health endpoint** shows `*_model_ok: true` and `*_is_placeholder: false`

The placeholder system provides a seamless development experience while maintaining full production functionality.