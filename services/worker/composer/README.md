# Panel Composer

A composer that walks lines top-down and maintains panel state to structure lab data into coherent panels with EHR-ready JSON output and comprehensive confidence scoring.

## Features

- **Top-down line processing**: Walks through lines sequentially, maintaining current panel state
- **Panel state management**: Tracks `{id, name, started_at_page, continuity_score, open}` for each panel
- **Quarantine zones**: Honors `PAGE_HEADER`/`PAGE_FOOTER` quarantine, skipping these lines
- **Panel opening**: Opens new panels on `SECTION_PANEL` lines  
- **Test row attachment**: Attaches subsequent `TEST_ROW` lines to the current open panel
- **Page break handling**: At page breaks, continues open panels if no new panel header found within first N lines
- **Two-pass repair**: Second pass repairs page-break attachments using cost function that minimizes panel switches and prefers coherent units/ref-range patterns
- **Comprehensive scoring**: Evaluates confidence for each field (value parsing, unit validity, reference range quality, test name clarity) with configurable thresholds
- **Quality assessment**: Computes per-panel and per-document scores with automatic review flagging when quality falls below thresholds
- **EHR-ready output**: Clean JSON schema suitable for Electronic Health Records with embedded confidence scores

## Usage

### As a Python Module

```python
from services.worker.composer import PanelComposer

# Sample line data (from extractor or role classifier)
lines_data = [
    {"text": "CHEMISTRY PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.8},
    {"text": "Glucose 95 mg/dL 70-100", "role": "TEST_ROW", "page": 1, "yNorm": 0.7},
    # ... more lines
]

# Initialize composer with scoring
composer = PanelComposer(
    page_break_lookahead=5,      # Lines to look ahead after page break
    min_continuity_score=0.3,     # Minimum score to continue panel
    cost_weight_switches=2.0,     # Penalty for panel switches
    cost_weight_coherence=1.0,    # Bonus for coherent patterns
    enable_scoring=True,          # Enable confidence scoring
    scoring_config={              # Scoring thresholds
        'value_parse_threshold': 0.7,
        'unit_validity_threshold': 0.8,
        'ref_range_threshold': 0.6,
        'panel_score_threshold': 0.7,
        'document_score_threshold': 0.75
    }
)

# Optional: include classifier probabilities for enhanced scoring
classifier_probabilities = {
    0: 0.95,  # Line 0 has 95% confidence in role classification
    1: 0.87,  # Line 1 has 87% confidence
    # ... more line probabilities
}

# Compose panels with scoring
result = composer.compose(lines_data, classifier_probabilities)

# Check quality assessment
print(f"Document score: {result.document_score:.3f}")
print(f"Needs review: {result.needs_review}")
print(f"Review reasons: {result.review_reasons}")

# Get EHR-ready JSON with confidence scores
ehr_json = result.to_ehr_json()
```

### CLI Interface

```bash
cd services/worker/composer
python3 -m composer.cli input_lines.json output_panels.json --format ehr --verbose
```

#### CLI Options

**Composition Parameters:**
- `--format`: Output format (`ehr` or `raw`, default: `ehr`)
- `--lookahead`: Page break lookahead lines (default: 5)
- `--min-continuity`: Minimum continuity score (default: 0.3)
- `--cost-switches`: Cost weight for panel switches (default: 2.0)
- `--cost-coherence`: Cost weight for coherence (default: 1.0)

**Scoring Parameters:**
- `--disable-scoring`: Disable confidence scoring
- `--value-threshold`: Value parse confidence threshold (default: 0.7)
- `--unit-threshold`: Unit validity confidence threshold (default: 0.8)
- `--range-threshold`: Reference range confidence threshold (default: 0.6)
- `--panel-threshold`: Panel confidence threshold (default: 0.7)
- `--document-threshold`: Document confidence threshold (default: 0.75)

**Output:**
- `--verbose`: Enable verbose output with panel scores and review status

### Testing

```bash
# Test basic composition
cd services/worker
python3 -m composer.test_composer

# Test comprehensive scoring system  
python3 -m composer.test_scoring
```

## Scoring System

The composer includes a comprehensive scoring system that evaluates confidence in parsed lab data and flags content that may need manual review.

### Field-Level Scoring

Each test row field receives individual confidence scores:

**Value Parse Confidence** (0.0 - 1.0):
- `1.0`: Clean numeric values (`95`, `4.2`, `140`)
- `0.9`: Scientific notation, ranges (`1.5e-3`, `70-100`)
- `0.8`: Comparison operators (`<100`, `>40`)
- `0.7-0.9`: Text results (`POSITIVE`, `NORMAL`, `HIGH`)
- `0.1-0.4`: Contains numbers but unparseable
- `0.0`: No recognizable value

**Unit Validity Confidence** (0.0 - 1.0):
- `1.0`: Valid units from comprehensive whitelist (`mg/dL`, `mEq/L`, `K/uL`)
- `0.9`: Common variations (`mg/dl`, `meq/l`)
- `0.6`: Proper format but not in whitelist (`something/something`)
- `0.4`: Letters/symbols only
- `0.1`: Unrecognizable format

**Reference Range Quality** (0.0 - 1.0):
- `1.0`: Well-formed numeric ranges (`70-100`, `3.5-5.1`)
- `0.9`: Comparison operators (`<200`, `>40`)
- `0.8`: Standard qualitative ranges (`NORMAL`, `POSITIVE`)
- `0.5`: Contains numbers but irregular format
- `0.1`: Malformed or missing

**Test Name Clarity** (0.0 - 1.0):
- Based on length, medical terminology, proper capitalization
- Penalties for special characters, ALL CAPS, numeric codes
- Bonuses for recognized medical terms

### Panel-Level Scoring

Panels receive composite scores considering:

- **Average field confidence** across all test rows
- **Continuity score** from page break analysis  
- **Coherence score** based on consistent units/ranges
- **Review thresholds** trigger automatic flagging:
  - Poor value parsing in >30% of tests
  - Invalid units in >40% of tests  
  - Malformed ranges in >50% of tests
  - Low continuity (<0.5) or coherence (<0.6) scores

### Document-Level Scoring  

Documents receive overall assessment including:

- **Average panel scores** with weighting
- **Confidence distribution** statistics (mean, median, std dev)
- **Review triggers**:
  - >30% of panels need review
  - Average panel score <0.6
  - Very low confidence panels present
  - Insufficient test data

### Review Flagging

The system automatically sets `needsReview = true` and populates `reasons[]` arrays when:

- **Critical field failures** exceed thresholds
- **Panel scores** fall below configurable limits  
- **Document scores** indicate systematic quality issues
- **Classifier probabilities** suggest uncertain role predictions

### Configuration

Scoring thresholds are fully configurable:

```python
scoring_config = {
    'value_parse_threshold': 0.7,      # Min value parsing score
    'unit_validity_threshold': 0.8,    # Min unit validity score  
    'ref_range_threshold': 0.6,        # Min reference range score
    'panel_score_threshold': 0.7,      # Min panel score
    'document_score_threshold': 0.75   # Min document score
}
```

## Input Format

The composer accepts line data in the format produced by the extractor and role classifier:

```json
{
  "lines": [
    {
      "text": "CHEMISTRY PANEL", 
      "role": "SECTION_PANEL",
      "page": 1,
      "yNorm": 0.8,
      "xLeft": 0,
      "xRight": 100,
      "fontSize": 14,
      "isBold": true
    },
    {
      "text": "Glucose 95 mg/dL 70-100",
      "role": "TEST_ROW", 
      "page": 1,
      "yNorm": 0.7,
      "xLeft": 10,
      "xRight": 90
    }
  ]
}
```

## Output Format

### EHR-Ready JSON Schema

```json
{
  "document_info": {
    "source": "input_file.json",
    "processed_at": "2025-09-04T20:17:26.378642",
    "total_panels": 3,
    "total_tests": 11,
    "document_score": 0.847,
    "needs_review": false,
    "review_reasons": [],
    "confidence_distribution": {
      "mean": 0.823,
      "median": 0.841,
      "min": 0.654,
      "max": 0.943,
      "std": 0.098
    },
    "processing_stats": {
      "lines_processed": 20,
      "page_breaks_handled": 2,
      "repairs_made": 1,
      "processing_time_seconds": 0.00008
    }
  },
  "lab_panels": [
    {
      "id": "1095d94e",
      "name": "CHEMISTRY",
      "started_at_page": 1,
      "started_at_line": 1,
      "continuity_score": 1.0,
      "open": false,
      "panel_type": null,
      "test_count": 5,
      "coherence_score": 1.0,
      "panel_score": 0.874,
      "needs_review": false,
      "review_reasons": [],
      "test_rows": [
        {
          "text": "Glucose 95 mg/dL 70-100",
          "page": 1,
          "line_number": 2,
          "y_norm": 0.7,
          "test_name": "Glucose",
          "result_value": "95",
          "units": "mg/dL", 
          "reference_range": "70-100",
          "flag": null,
          "confidence": 0.834,
          "field_confidences": {
            "value_parse": 1.0,
            "unit_validity": 1.0,
            "reference_range": 1.0,
            "test_name_clarity": 0.227,
            "overall": 0.834
          }
        }
      ]
    }
  ]
}
```

## Algorithm Overview

### First Pass: Top-down Processing

1. **Line Context**: Convert raw lines to `LineContext` objects with quarantine detection
2. **Sequential Processing**: Walk lines top-down, maintaining `current_panel` state
3. **Quarantine Skipping**: Skip `PAGE_HEADER`/`PAGE_FOOTER` lines  
4. **Panel Management**: Open new panels on `SECTION_PANEL`, attach `TEST_ROW` to current panel
5. **Page Break Handling**: At page breaks, look ahead N lines for new panel headers
6. **Continuity Scoring**: Calculate continuity score based on pattern similarity

### Second Pass: Repair Phase  

1. **Page Break Identification**: Find all page break locations
2. **Repair Option Evaluation**: For each page break, evaluate:
   - **Continue**: Continue current panel (cost = switches penalty - coherence bonus)
   - **New Panel**: Start new panel (cost = new panel penalty)
3. **Cost Function**: Minimize `switches_weight * panel_switches - coherence_weight * pattern_coherence`
4. **Pattern Analysis**: Compare units, reference ranges, numeric results before/after break

### Test Row Parsing

Extracts structured data from test rows using regex patterns:

- **Numeric Results**: `Test Name 123 mg/dL 70-100` → name, value, units, range
- **Text Results**: `Test Name POSITIVE Normal` → name, value, reference  
- **Flags**: Detects `HIGH`, `LOW`, `CRITICAL`, `ABNORMAL` flags
- **Reference Ranges**: Extracts `70-100`, `>40`, `<200` patterns

## Configuration

### Parameters

- `page_break_lookahead` (default: 5): Lines to examine after page break
- `min_continuity_score` (default: 0.3): Threshold for continuing panels across pages
- `cost_weight_switches` (default: 2.0): Penalty weight for creating new panels
- `cost_weight_coherence` (default: 1.0): Bonus weight for coherent patterns

### Customization

Extend the composer by:

1. **Custom Patterns**: Add regex patterns to `test_patterns` dictionary
2. **Scoring Functions**: Override `_calculate_continuity_score()` method  
3. **Cost Functions**: Modify `_calculate_repair_cost()` for different repair strategies
4. **Output Formats**: Add new methods to `ComposerResult` class

## Integration

The composer integrates with:

- **Extractor**: Processes line data from `services/extractor`  
- **Role Classifier**: Uses role predictions from `services/trainer/roles`
- **Worker**: Can be deployed as Celery tasks
- **EHR Systems**: Outputs standard JSON schema for lab results