# Lab AI Scripts

Utility scripts for Label Studio integration and data conversion.

## 📋 Label Studio Quickstart

### `ls_roles_quickstart.ipynb`

Interactive Jupyter notebook that guides you through:

1. **Starting Label Studio** with Docker Compose
2. **Creating a line-role labeling project** with proper configuration
3. **Importing *.lines.json files** from PDF processing
4. **Labeling 30-60 lines** with semantic roles
5. **Exporting labeled data** as JSON

**Usage:**
```bash
# Start Jupyter in this directory
jupyter notebook ls_roles_quickstart.ipynb

# Or use JupyterLab
jupyter lab ls_roles_quickstart.ipynb
```

**Prerequisites:**
- Docker Compose running with `labelstudio` service
- Some *.lines.json files generated from PDF processing
- Python with requests, pandas, pathlib

---

## 🔄 Data Converters

### `ls_roles_to_csv.py`

Converts Label Studio role annotations to CSV format for training.

**Features:**
- Converts Label Studio JSON export to roles training CSV
- Merges with existing training data
- Validates CSV format and provides quality checks
- Shows role distribution and balance analysis

**Usage:**
```bash
# Basic conversion
./ls_roles_to_csv.py /data/labelstudio/labeled_roles.json

# Specify output file
./ls_roles_to_csv.py /data/labelstudio/labeled_roles.json -o /data/training/new_roles.csv

# Merge with existing training data
./ls_roles_to_csv.py /data/labelstudio/labeled_roles.json --merge-with /data/training/existing_roles.csv

# Validate existing CSV
./ls_roles_to_csv.py /data/training/roles.csv --validate-only
```

**Output Format:**
```csv
text,y_tertile,is_bold,is_header_hint,role,page,source_file
"COMPREHENSIVE METABOLIC PANEL",2,true,false,SECTION_PANEL,1,report_123.pdf
"Glucose                    95      mg/dL     70-100",1,false,false,TEST_ROW,1,report_123.pdf
"Patient: SMITH, JOHN",2,false,true,HEADER_PATIENT,1,report_123.pdf
```

### `ls_testrow_to_ner.py`

Converts Label Studio NER annotations to token classification format.

**Features:**
- Converts entity annotations to BIO format
- Aligns entity spans with tokenized text
- Validates NER format and provides quality checks
- Outputs JSONL format for training
- Optional CSV export for inspection

**Usage:**
```bash
# Print Label Studio configuration for NER
./ls_testrow_to_ner.py --print-config

# Basic conversion
./ls_testrow_to_ner.py /data/labelstudio/testrow_ner.json

# Convert with CSV export for inspection
./ls_testrow_to_ner.py /data/labelstudio/testrow_ner.json --csv

# Validate existing JSONL
./ls_testrow_to_ner.py /data/training/testrow.jsonl --validate-only
```

**Output Format (JSONL):**
```json
{"text": "Glucose    95    mg/dL    70-100", "tokens": ["Glucose", "95", "mg/dL", "70-100"], "labels": ["B-TEST_NAME", "B-VALUE", "B-UNIT", "B-REF_RANGE"]}
{"text": "WBC        7.2    K/uL     4.0-11.0", "tokens": ["WBC", "7.2", "K/uL", "4.0-11.0"], "labels": ["B-TEST_NAME", "B-VALUE", "B-UNIT", "B-REF_RANGE"]}
```

---

## 🏷️ Label Studio Setup

### Docker Configuration

Label Studio is already configured in `docker-compose.yml`:

```yaml
labelstudio:
  image: heartexlabs/label-studio:latest
  ports:
    - "8080:8080"
  environment:
    - LABEL_STUDIO_USERNAME=admin@localhost
    - LABEL_STUDIO_PASSWORD=changeme
  volumes:
    - ./data:/data
    - ./data/labelstudio:/label-studio/data
```

### Starting Label Studio

```bash
# Start just Label Studio
docker-compose up labelstudio

# Or start the full system
docker-compose up
```

Access at: http://localhost:8080 (admin@localhost/changeme)

### Data Directory Structure

```
data/
├── inbox/              # Input PDFs
├── outbox/             # Processed *.lines.json files  
├── labelstudio/        # Label Studio projects and exports
├── training/           # Converted training data
└── expected/           # Manual review corrections
```

---

## 🎯 Labeling Workflows

### 1. Line Role Classification

**Goal:** Classify document lines into semantic roles

**Steps:**
1. Use `ls_roles_quickstart.ipynb` to set up project
2. Import *.lines.json files from PDF processing
3. Label 30-60 lines with roles:
   - PAGE_HEADER, PAGE_FOOTER
   - HEADER_PATIENT, HEADER_SPECIMEN  
   - SECTION_PANEL
   - TEST_ROW (most important!)
   - COMMENT, SECTION_MISC, JUNK
4. Export and convert with `ls_roles_to_csv.py`
5. Train model with converted data

**Quality Tips:**
- Focus on TEST_ROW detection (95% precision/recall target)
- Include diverse document formats and layouts
- Label ambiguous/boundary cases
- Maintain class balance (no role <5 examples)

### 2. Test Row NER

**Goal:** Extract entities from test result lines

**Steps:**
1. Filter for lines labeled as TEST_ROW
2. Create NER project with `ls_testrow_to_ner.py --print-config`
3. Label token-level entities in test lines:
   - test_name: "Glucose", "WBC Count"
   - value: "95", "7.2"  
   - unit: "mg/dL", "K/uL"
   - ref_range: "70-100", "4.0-11.0"
   - flag: "H", "L", "*"
4. Export and convert with `ls_testrow_to_ner.py`
5. Train NER model with JSONL data

**Quality Tips:**
- Label 50-100 diverse test lines
- Include various formats and layouts
- Handle multi-token entities (e.g., "Total Cholesterol")
- Balance entity types (not just TEST_NAME)
- Include edge cases and formatting variations

---

## 🔧 Training Integration

### Roles Training

```bash
# Convert Label Studio data
./scripts/ls_roles_to_csv.py /data/labelstudio/roles.json -o /data/training/roles.csv

# Train model (from services/trainer/roles/)
python train_roles.py --train-data /data/training/roles.csv
```

### Test-Row NER Training  

```bash
# Convert Label Studio data
./scripts/ls_testrow_to_ner.py /data/labelstudio/testrow.json -o /data/training/testrow.jsonl

# Train model (from services/trainer/testrow/)
python train_testrow.py --train-data /data/training/testrow.jsonl
```

---

## 📊 Quality Assurance

Both converters provide quality checks:

### Roles Quality Checks
- ✅ **Class balance**: No role with <5 examples
- ✅ **TEST_ROW coverage**: ≥20 examples (most critical)
- ✅ **Success rate**: >90% conversion rate
- ⚠️ **High imbalance**: Max/min ratio >10

### NER Quality Checks
- ✅ **Label coverage**: All entity types present
- ✅ **O/entity balance**: 30-80% O tokens
- ✅ **Critical entities**: TEST_NAME, VALUE ≥10 each
- ⚠️ **Missing entities**: Unused entity types

---

## 🚀 Best Practices

### Data Collection
- **Start small**: 30 examples → train → evaluate → add more
- **Focus on errors**: Label examples where model fails
- **Diverse sources**: Multiple document formats and labs
- **Edge cases**: Unusual layouts, multi-line tests, formatting variations

### Labeling Guidelines  
- **Be consistent**: Same patterns → same labels
- **Consider context**: What section is this line in?
- **Most specific rule**: Choose most applicable label
- **Quality over quantity**: Better to have fewer, high-quality labels

### Model Training
- **Iterative approach**: Label → train → evaluate → repeat
- **Hold-out testing**: Reserve 20% of data for final evaluation  
- **Cross-validation**: Use k-fold CV for robust evaluation
- **Error analysis**: Study failure cases to guide next labeling round

---

## 🆘 Troubleshooting

### Label Studio Issues
```bash
# Reset Label Studio data
docker-compose down
sudo rm -rf data/labelstudio/
docker-compose up labelstudio
```

### Conversion Errors
```bash
# Check Label Studio export format
head -n 5 /data/labelstudio/export.json

# Validate converted data
./ls_roles_to_csv.py /data/training/roles.csv --validate-only
./ls_testrow_to_ner.py /data/training/testrow.jsonl --validate-only
```

### Training Integration
```bash
# Check training data format
head -n 5 /data/training/roles.csv
head -n 5 /data/training/testrow.jsonl

# Verify column names match expected format
python -c "import pandas as pd; print(pd.read_csv('/data/training/roles.csv').columns.tolist())"
```

**Need help?** Check the individual script help: `./script_name.py --help`