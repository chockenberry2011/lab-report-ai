# Worker Enhancements: Guarded Model Loading & Enhanced Fallbacks

## Overview
Enhanced the Lab AI worker with robust model loading, clear logging, and sophisticated rule-based fallbacks that ensure clean processing even when models are missing.

## Key Features Implemented

### 1. Guarded Model Loading
- **Location**: `services/worker/tasks.py`
- **Function**: `_load_models_with_logging()`
- **Features**:
  - Safe loading with exception handling
  - Clear logging for each model attempt
  - Graceful degradation when models are missing

**Log Output Examples**:
```
roles model: LOADED from /models/roles
testrow model: MISSING → using rules
```

### 2. Enhanced Rule-First Fallbacks
- **Location**: `services/worker/fallbacks.py`
- **Enhanced patterns**:
  - Panel headers: `\b(CMP|COMPREHENSIVE METABOLIC|CBC|COMPLETE BLOOD COUNT|LIPID|TSH|THYROID)\b`
  - Test rows: `\b\d+(\.\d+)?\s*(mg/dL|mmol/L|IU/L|U/L|g/dL|%|x10\^\d+)\b`
  - Header/footer quarantine: Top/bottom 10% of page area

### 3. Advanced Test Row NER
- **Name**: Leading text before first numeric value
- **Value**: First numeric with comparison operators (`>4.1`, `<100`)
- **Unit**: Next token from whitelist (`mg/dL`, `mmol/L`, etc.)
- **Reference Range**: Patterns like `(136-145)` or `low-high`
- **Flags**: `High|Low|H|L|↑|↓` indicators

**Example Input**:
```
Potassium >4.1 mmol/L (3.5-5.0) High
```

**Parsed Output**:
```python
{
    'test_name': 'Potassium',
    'result_value': '>4.1',
    'unit': 'mmol/L',
    'reference_range': '(3.5-5.0)',
    'flags': ['High']
}
```

### 4. Processing Statistics in JSON
- **Location**: Final document output
- **Fields Added**:
```json
{
  "document_info": {
    "processing_stats": {
      "roles_used_fallback": true,
      "testrow_used_fallback": true,
      "models_available": {
        "roles_model_ok": false,
        "testrow_model_ok": false
      }
    }
  },
  "quality_metrics": {
    "needs_review": true,
    "review_reasons": [
      "Role classification used rule-based fallback",
      "Test row parsing used rule-based fallback"
    ]
  }
}
```

### 5. Global State Flags
- `_roles_model_ok: bool` - Whether roles model loaded successfully
- `_testrow_model_ok: bool` - Whether testrow model loaded successfully
- `_roles_used_fallback_last: bool|None` - Last processing used fallback
- `_testrow_used_fallback_last: bool|None` - Last processing used fallback

## Environment Variables
- `MODEL_ROLES_DIR`: Path to roles model (default: `/models/roles`)
- `MODEL_TESTROW_DIR`: Path to testrow model (default: `/models/testrow`)
- `MODEL_MIN_CONF`: Minimum confidence threshold (default: `0.60`)
- `FALLBACK_RULES_STRICT`: Enable strict rule-based fallbacks (default: `1`)

## Processing Flow

### Startup
1. Load models with guarded error handling
2. Log success/failure for each model
3. Set global state flags
4. Continue regardless of model availability

### Runtime Processing
1. **Check model availability** and confidence thresholds
2. **Use models** if available and confident
3. **Fallback to rules** if models missing or low confidence
4. **Log processing path** taken
5. **Emit statistics** in final JSON

### Fallback Processing
1. **Header/Footer Quarantine**: Remove repeating elements in top/bottom 10%
2. **Panel Detection**: Regex patterns for common lab panels
3. **Test Row Detection**: Number + unit patterns and lexicon matching
4. **Field Extraction**: Rule-based NER with comparison operators and flags

## Benefits

### Reliability
- **Never fails** due to missing models
- **Always produces output** using rule-based fallbacks
- **Handles errors gracefully** with proper logging

### Transparency
- **Clear logging** shows which processing path was taken
- **Processing statistics** included in output JSON
- **Review flags** when fallbacks are used

### Quality
- **Enhanced NER** extracts detailed test information
- **Sophisticated parsing** handles comparison operators and flags
- **Reference ranges** and abnormal value detection

## Testing
Run the enhanced test to verify functionality:
```python
python3 test_fallbacks_enhanced.py
```

Expected results:
- ✅ Enhanced panel detection
- ✅ Enhanced testrow detection with 100% parsing success
- ✅ Model loading structure validation
- ✅ Proper field extraction with flags and ranges

## Integration
All enhancements are backward compatible and integrate seamlessly with:
- Existing Celery task pipeline
- FastAPI health endpoints
- Debug file generation
- Quality metrics reporting

The worker now provides robust, transparent processing that gracefully handles missing models while maintaining high-quality output through sophisticated rule-based fallbacks.