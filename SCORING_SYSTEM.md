# Lab Data Scoring System

## Overview

The lab-ai scoring module provides comprehensive quality assessment for parsed lab data with multi-level confidence scoring, automatic review flagging, and detailed reason tracking. All scores are persisted in the final JSON output for downstream processing and quality control.

## Architecture

### Field-Level Scoring (`FieldConfidence`)

Each test result field is scored individually (0.0-1.0):

- **VALUE** (`value_parse`): Numeric parse success
  - 1.0: Clean numeric values (integers, decimals, scientific notation)
  - 0.9: Qualitative results (POSITIVE, NEGATIVE, NORMAL)
  - 0.8: Approximate/bounded values (<, >, ~)
  - 0.1-0.4: Partial parsing success or text patterns
  - 0.0: Unparseable values

- **UNIT** (`unit_validity`): Medical unit whitelist validation
  - 1.0: Exact match with medical unit whitelist
  - 0.9: Close variations of valid units
  - 0.6: Valid format patterns (X/Y structure)
  - 0.1-0.4: Partial matches or suspicious patterns
  - 0.0: Invalid or missing units

- **REF_RANGE** (`reference_range`): Reference range well-formedness  
  - 1.0: Well-formed numeric ranges (5.0-10.0)
  - 0.9: Boundary conditions (<5.0, >10.0)
  - 0.8: Qualitative ranges (NORMAL, ABNORMAL)
  - 0.1-0.5: Malformed or partial ranges
  - 0.0: Missing or unintelligible ranges

- **TEST_NAME** (`test_name_clarity`): Name clarity and medical terminology
  - Based on length, medical terminology, proper formatting
  - Bonuses for recognized medical terms
  - Penalties for excessive special characters, poor capitalization

- **CLASSIFIER** (`classifier_proba`): ML model role prediction confidence
  - Direct pass-through of classifier probability (0.0-1.0)
  - Default 0.5 when not provided

### Panel-Level Scoring (`PanelScore`) 

Each lab panel receives:
- **Continuity Score**: Panel coherence across page breaks
- **Coherence Score**: Consistency of test patterns within panel  
- **Average Field Confidence**: Mean of all test row confidences
- **Review Determination**: Based on critical field failures

### Document-Level Scoring (`DocumentScore`)

Overall document assessment includes:
- **Total Statistics**: Panel counts, test counts, processing metrics
- **Confidence Distribution**: Mean, median, min, max, standard deviation
- **Quality Classification**: High/low confidence panel counts
- **Review Determination**: Aggregate review need assessment

## Threshold Configuration

Configurable thresholds determine review flagging:

```python
scorer = LabDataScorer(
    value_parse_threshold=0.7,      # Minimum acceptable value parsing
    unit_validity_threshold=0.8,    # Minimum unit validity  
    ref_range_threshold=0.6,        # Minimum reference range quality
    panel_score_threshold=0.7,      # Minimum panel score
    document_score_threshold=0.75   # Minimum document score
)
```

## Review Flagging

### Automatic Review Triggers

Documents/panels are flagged for review when:

1. **Critical Field Failures**: 
   - Poor value parsing in >30% of tests
   - Invalid units in >40% of tests  
   - Malformed reference ranges in >50% of tests

2. **Low Scoring Thresholds**:
   - Panel score < panel_score_threshold
   - Document score < document_score_threshold

3. **Structural Issues**:
   - Very low continuity scores across page breaks
   - Low coherence within panels
   - Insufficient test data

### Review Reasons Array

Detailed explanations provided:
- "Poor value parsing in X/Y tests"
- "Invalid units in X/Y tests"  
- "Malformed reference ranges in X/Y tests"
- "Low continuity score: X.XX"
- "Low coherence score: X.XX"
- "X panels have very low confidence"

## JSON Output Structure

All confidence scores are persisted in EHR-ready JSON:

```json
{
  "document_info": {
    "document_score": 0.750,
    "needs_review": false,
    "review_reasons": [],
    "confidence_distribution": {
      "mean": 0.825,
      "median": 0.850,
      "min": 0.650,
      "max": 0.950,
      "std": 0.125
    }
  },
  "lab_panels": [
    {
      "name": "Chemistry Panel",
      "panel_score": 0.875,
      "needs_review": false,
      "review_reasons": [],
      "test_rows": [
        {
          "test_name": "Glucose",
          "result_value": "95",
          "units": "mg/dL",
          "reference_range": "70-100",
          "confidence": 0.834,
          "field_confidences": {
            "value_parse": 1.0,
            "unit_validity": 1.0,
            "reference_range": 1.0,
            "test_name_clarity": 0.227,
            "classifier_proba": 0.95,
            "overall": 0.834
          }
        }
      ]
    }
  ]
}
```

## Unit Whitelist Categories

Comprehensive medical unit validation across:

- **Concentration**: mg/dL, g/dL, mmol/L, μmol/L, ng/mL, etc.
- **Blood Counts**: K/μL, M/μL, 10³/μL, cells/μL, etc. 
- **Percentages**: %, percent
- **Time**: sec, min, hr, days
- **Pressure**: mmHg, cmH₂O, kPa
- **Temperature**: °C, °F
- **Volume**: mL, L, μL, dL
- **Mass**: g, kg, mg, μg, ng, pg
- **Activity**: IU, U, mU, μU, KU, MU
- **Dimensionless**: ratio, index, score, units

## Usage Examples

### Basic Scoring
```python
from services.worker.composer import PanelComposer

composer = PanelComposer(enable_scoring=True)
result = composer.compose(lines_data, classifier_probabilities)

print(f"Document Score: {result.document_score}")
print(f"Needs Review: {result.needs_review}")
```

### Custom Thresholds
```python
strict_config = {
    'value_parse_threshold': 0.9,
    'unit_validity_threshold': 0.9,
    'panel_score_threshold': 0.8,
    'document_score_threshold': 0.8
}

composer = PanelComposer(
    enable_scoring=True, 
    scoring_config=strict_config
)
```

### Individual Field Scoring
```python
from services.worker.composer.scoring import LabDataScorer

scorer = LabDataScorer()
confidence = scorer.score_test_row(test_row, classifier_proba=0.85)

print(f"Value Parse: {confidence.value_parse}")
print(f"Unit Validity: {confidence.unit_validity}")
print(f"Overall: {confidence.overall}")
```

## Production Benefits

1. **Quality Assurance**: Automatic detection of parsing issues
2. **Review Optimization**: Intelligent flagging reduces manual review overhead
3. **Audit Trail**: Complete confidence tracking for regulatory compliance  
4. **Threshold Tuning**: Configurable sensitivity for different use cases
5. **EHR Integration**: Standardized JSON output with embedded quality metrics

The scoring system ensures high-quality lab data extraction while providing transparency and configurability for production medical data processing workflows.