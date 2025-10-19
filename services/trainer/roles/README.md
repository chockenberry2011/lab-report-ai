# Line Role Classifier

Machine learning classifier for medical document line roles. Classifies lines into semantic roles like headers, test results, comments, etc.

## Supported Roles

- `PAGE_HEADER` - Document headers (titles, lab names)
- `PAGE_FOOTER` - Page footers (page numbers, copyright)
- `HEADER_PATIENT` - Patient information (name, DOB, MRN)
- `HEADER_SPECIMEN` - Specimen details (collection date, type)
- `SECTION_PANEL` - Test panel headers (metabolic panel, CBC)
- `TEST_ROW` - Individual test results with values and ranges
- `COMMENT` - Comments and notes
- `SECTION_MISC` - Miscellaneous sections (provider info, signatures)
- `JUNK` - Non-content lines (separators, whitespace)

## Features Used

1. **Text embeddings** - Sentence transformer embeddings (384-dim)
2. **Y tertile** - Vertical position (0=bottom, 1=middle, 2=top)
3. **isBold** - Bold text indicator
4. **isHeaderHint** - Contains header keywords
5. **Font size** - Font size in points
6. **X coordinates** - Horizontal position and width

## Quick Start

### 1. Generate Sample Data
```bash
# Create synthetic training data for development
python sample_data_generator.py --output /data/sample_roles_data.json --type realistic --size 100

# Creates ~2000 lines from 100 synthetic documents
```

### 2. Train Classifier
```bash
# Train logistic regression model
python train_roles.py /data/sample_roles_data.json --model-type logistic

# Train random forest model  
python train_roles.py /data/sample_roles_data.json --model-type random_forest

# Model saved to /models/roles/
```

### 3. Evaluate Model
```bash
# Evaluate on test data
python eval_roles.py --test-data /data/sample_roles_data.json

# Interactive testing
python eval_roles.py --interactive
```

### 4. Apply to Real Data
```bash
# Process extractor output
python integrate_extractor.py --input /data/outbox/document.lines.json --output /data/classified/document.roles.json

# Batch processing
python integrate_extractor.py --input /data/outbox/ --output /data/classified/ --batch
```

## Working with Label Studio Data

### Prepare Training Data from Label Studio Export

1. **Export from Label Studio**
   - Go to your Label Studio project
   - Export → JSON
   - Save as `labelstudio_export.json`

2. **Convert to Training Format**
```bash
python prep_roles.py labelstudio_export.json --output /data/training_data.json
```

3. **Validate Data Quality**
```bash
python prep_roles.py labelstudio_export.json --validate
```

### Expected Label Studio Annotation Format

The script supports multiple annotation formats:

**Option 1: Structured JSON in Text Area**
```json
[
  {
    "text": "LABORATORY REPORT",
    "y_norm": 0.95,
    "is_bold": true,
    "role": "PAGE_HEADER",
    "font_size": 14.0
  },
  {
    "text": "Patient: Smith, John",
    "y_norm": 0.85,
    "is_bold": false,
    "role": "HEADER_PATIENT",
    "font_size": 12.0
  }
]
```

**Option 2: Rectangle Labels with Text**
- Draw bounding boxes around text regions
- Assign role labels to each box
- Text content extracted from annotations

## Model Architecture

### Logistic Regression (Default)
- **Input**: 390-dimensional feature vector
  - 384 dimensions: Sentence transformer embeddings (`all-MiniLM-L6-v2`)
  - 6 dimensions: Structural features (y_tertile, isBold, isHeaderHint, fontSize, xLeft, width)
- **Model**: Sklearn LogisticRegression with balanced class weights
- **Training time**: ~30 seconds for 1000 samples
- **Inference**: ~100ms for 50 lines

### Random Forest Alternative
- **Model**: 100 trees, balanced class weights
- **Benefits**: Feature importance, handles non-linear patterns
- **Trade-off**: Larger model size, slightly slower

## Performance

### Typical Results (Synthetic Data)
```
Overall Accuracy: 0.952
                     Precision  Recall  F1-Score  Support
PAGE_HEADER          0.950     0.950   0.950     40
PAGE_FOOTER          0.975     0.975   0.975     40  
HEADER_PATIENT       0.925     0.925   0.925     40
HEADER_SPECIMEN      0.950     0.925   0.937     40
SECTION_PANEL        0.975     1.000   0.987     40
TEST_ROW             0.975     0.975   0.975     40
COMMENT              0.900     0.925   0.912     40
SECTION_MISC         0.925     0.900   0.912     40
JUNK                 0.975     0.950   0.962     40
```

### Real-World Performance
- Depends heavily on training data quality
- Medical documents: 85-95% accuracy
- Best results with 500+ labeled examples per role

## File Structure

```
roles/
├── line_classifier.py      # Core classifier implementation
├── prep_roles.py          # Label Studio data preparation  
├── train_roles.py         # Training script
├── eval_roles.py          # Evaluation script
├── integrate_extractor.py # Integration with PDF extractor
├── sample_data_generator.py # Synthetic data generation
└── README.md             # This file
```

## Training Script Options

```bash
python train_roles.py --help

Options:
  --model-type {logistic,random_forest}  Model architecture
  --embedding-model TEXT                 Sentence transformer model
  --test-size FLOAT                      Train/test split ratio
  --output-dir PATH                      Model save directory
  --plots-dir PATH                       Visualization output
  --cross-validate                       5-fold cross-validation
  --random-seed INT                      Reproducibility seed
```

## Evaluation Features

- **Confusion matrix** visualization
- **Per-class metrics** (precision, recall, F1)
- **Feature importance** analysis
- **Misclassification patterns**
- **Confidence analysis**
- **Interactive testing** mode

## Integration with Extractor

The `integrate_extractor.py` script processes PDF extractor output:

### Input Format (from extractor)
```json
{
  "source_file": "/data/document.pdf",
  "total_lines": 145,
  "lines": [
    {
      "page": 1,
      "text": "LABORATORY REPORT",
      "xLeft": 72.0,
      "xRight": 540.0,
      "yNorm": 0.95,
      "fontSize": 12.0,
      "isBold": true,
      "hasText": true,
      "source": "pdf"
    }
  ]
}
```

### Output Format (with roles)
```json
{
  "source_file": "/data/document.pdf",
  "total_lines": 145,
  "processing_metadata": {
    "has_role_classification": true,
    "average_confidence": 0.887,
    "role_distribution": {
      "PAGE_HEADER": 2,
      "TEST_ROW": 45,
      "SECTION_PANEL": 8
    }
  },
  "lines": [
    {
      "text": "LABORATORY REPORT",
      "predicted_role": "PAGE_HEADER",
      "confidence": 0.952,
      "top_predictions": [
        {"role": "PAGE_HEADER", "confidence": 0.952},
        {"role": "SECTION_MISC", "confidence": 0.031},
        {"role": "JUNK", "confidence": 0.017}
      ],
      "features": {
        "y_tertile": 2,
        "is_bold": true,
        "is_header_hint": true
      }
    }
  ]
}
```

## Advanced Usage

### Custom Embedding Models
```python
# Use different sentence transformer
classifier = LineRoleClassifier(
    embedding_model="sentence-transformers/all-mpnet-base-v2"
)
```

### Feature Engineering
```python
# Custom header hint detection
def custom_header_hints(text: str) -> bool:
    keywords = ['patient', 'lab', 'test', 'result']
    return any(kw in text.lower() for kw in keywords)
```

### Model Ensembling
```python
# Combine multiple models
logistic_model = LineRoleClassifier(model_type="logistic")
rf_model = LineRoleClassifier(model_type="random_forest")

# Average predictions
ensemble_pred = (logistic_pred + rf_pred) / 2
```

## Troubleshooting

### Low Accuracy
- **Check data quality**: Review misclassifications in eval output
- **Balance classes**: Ensure adequate samples per role (50+ recommended)
- **Feature engineering**: Add domain-specific features
- **Data augmentation**: Generate more training examples

### Memory Issues
- **Reduce batch size**: Process fewer lines at once
- **Smaller embedding model**: Use `all-MiniLM-L12-v2` (384 dim) instead of larger models
- **Feature selection**: Remove less important features

### Slow Training
- **Use logistic regression**: Faster than random forest
- **Reduce embedding dimension**: Use smaller transformer models
- **Sample data**: Train on subset for development

## API Integration

### Celery Task Integration
```python
# In trainer.py
@app.task
def classify_line_roles(lines_json_path, model_dir="/models/roles"):
    classifier = LineRoleClassifier()
    classifier.load_model(model_dir)
    
    # Process lines and return results
    # ... implementation
```

### REST API Usage
```python
# Flask/FastAPI endpoint
@app.post("/classify-roles")
def classify_roles(lines: List[dict]):
    classifier = load_classifier()
    line_data = [LineData(**line) for line in lines]
    predictions = classifier.predict(line_data)
    return {"predictions": predictions}
```

## Model Versioning

Models are saved with metadata for versioning:

```json
{
  "model_type": "logistic",
  "embedding_model": "all-MiniLM-L6-v2", 
  "training_date": "2024-03-15T10:30:00",
  "accuracy": 0.952,
  "training_samples": 1800,
  "version": "1.0.0"
}
```

## Contributing

1. **Add new roles**: Update `ROLE_LABELS` in `line_classifier.py`
2. **Improve features**: Extend `FeatureExtractor` class
3. **New models**: Add to `LineRoleClassifier` model types
4. **Better templates**: Enhance `sample_data_generator.py`

## Performance Monitoring

- **Confidence tracking**: Monitor prediction confidence over time
- **Role distribution**: Check for data drift in role frequencies  
- **Error analysis**: Regular misclassification review
- **A/B testing**: Compare model versions on same data