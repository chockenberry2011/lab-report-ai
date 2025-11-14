# Lab‑AI Training & Maturation Guide v4 (ELI5, Step‑by‑Step)

_Last updated: 2025-09-19_

**🎯 Purpose**: This guide shows **exactly** how to grow our proof‑of‑concept into a production‑ready lab ingestion pipeline. Follow these steps to go from a handful of sample PDFs to a robust system that can handle thousands of lab reports with high accuracy.

**👤 Audience**: Anyone who needs to pick up this project (including future you). No prior ML knowledge assumed.

---

## 📚 What we're building (at a glance)

Our system reads lab PDF reports and converts them into structured data. Think of it like having a really smart assistant who can:

1. **Look at each line** of a PDF and say "this is a test result", "this is patient info", "this is junk"
2. **Break down test lines** into parts: test name, value, units, reference range, flags
3. **Extract header info** like patient name, dates, lab info
4. **Combine everything** into clean JSON that can go into electronic health records

### The Three Learning Layers

We train **three separate models** that work together:

1. **Line Roles Classifier** 📝
   - **Job**: Look at each line and classify it (e.g., "TEST_ROW", "HEADER_PATIENT", "JUNK")
   - **Technology**: Scikit-learn LogisticRegression + TF-IDF (runs offline, no internet needed)
   - **Location**: `services/trainer/roles/`

2. **Test-Row Token Tagger** 🏷️
   - **Job**: Inside test result lines, tag each word/number (e.g., "Glucose" = TEST_NAME, "95" = VALUE)
   - **Technology**: CRF (Conditional Random Fields)
   - **Location**: `services/trainer/testrow/`

3. **Header Field Extractor** 📋
   - **Job**: Pull out patient names, dates, lab info from header sections
   - **Technology**: Rule-based (regex patterns) with optional ML enhancement
   - **Location**: `services/trainer/headers/`

---

## 🎯 What data we want to capture

Below is our target schema. Not every lab provides every field—we capture what's available.

### A. Lab/Vendor Information
- `vendor.name` (e.g., "LabCorp", "Quest")
- `vendor.account_number`
- `vendor.address` (street, city, state, zip)
- `vendor.phone`, `vendor.fax`

### B. Patient Information
- `patient.last_name`, `patient.first_name`, `patient.middle`
- `patient.dob` (date of birth)
- `patient.sex` (M/F)
- `patient.mrn` (medical record number)
- `patient.phone`
- `patient.address` (full address)

### C. Ordering Provider (who ordered the tests)
- `ordering.provider_name`
- `ordering.npi` (National Provider Identifier)
- `ordering.location.name`
- `ordering.location.address`

### D. Specimen Information
- `specimen.id` (accession number)
- `specimen.type` (blood, serum, urine, etc.)
- `specimen.collected_at` (when sample was taken)
- `specimen.received_at` (when lab got it)
- `specimen.reported_at` (when results were finalized)

### E. Lab Panels & Tests
Each panel contains multiple tests:
- `panel.name` (e.g., "COMPREHENSIVE METABOLIC PANEL")
- `panel.code` (LOINC/CPT codes if present)

For each test within a panel:
- `test.name` (e.g., "Glucose")
- `test.value` (e.g., "95")
- `test.unit` (e.g., "mg/dL")
- `test.reference_range` (e.g., "70-99")
- `test.flag` (e.g., "H" for high, "L" for low)

---

## 🏷️ Data labeling strategy

We use **Label Studio** (included in our Docker setup) to create training data. We split this into three separate projects so labelers have simple, focused jobs.

### Project 1: Line Role Classification

**Goal**: Look at each line of text and assign one label:
- `TEST_ROW` - Lines containing actual test results
- `SECTION_PANEL` - Panel headers like "COMPREHENSIVE METABOLIC PANEL"
- `HEADER_PATIENT` - Lines with patient information
- `HEADER_SPECIMEN` - Lines with specimen/collection info
- `PAGE_HEADER` - Page headers with lab name/logo
- `PAGE_FOOTER` - Page footers with addresses/disclaimers
- `COMMENT` - Comments, footnotes, interpretations
- `SECTION_MISC` - Other section headers
- `JUNK` - Noise, artifacts, irrelevant text

**Label Studio Configuration:**
```xml
<View>
  <Choices name="role" toName="txt" choice="single" required="true">
    <Choice value="TEST_ROW"/>
    <Choice value="SECTION_PANEL"/>
    <Choice value="HEADER_PATIENT"/>
    <Choice value="HEADER_SPECIMEN"/>
    <Choice value="PAGE_HEADER"/>
    <Choice value="PAGE_FOOTER"/>
    <Choice value="COMMENT"/>
    <Choice value="SECTION_MISC"/>
    <Choice value="JUNK"/>
  </Choices>
  <Text name="txt" value="$text"/>
</View>
```

**Labeling Tips:**
- Present one line at a time with context (neighboring lines visible)
- Target ≥300 examples per class over time
- Label across ≥10 different vendors/layouts early on

### Project 2: Test-Row Token Tagging

**Goal**: For lines labeled as `TEST_ROW`, tag each word/token with BIO format:
- `B-TEST_NAME`, `I-TEST_NAME` - Test name (e.g., "Glucose", "White Blood Cell Count")
- `B-VALUE`, `I-VALUE` - The result value (e.g., "95", "4.2")
- `B-UNIT`, `I-UNIT` - Units (e.g., "mg/dL", "K/uL")
- `B-REF_RANGE`, `I-REF_RANGE` - Reference range (e.g., "70-99", "4.0-10.0")
- `B-FLAG`, `I-FLAG` - Abnormal flags (e.g., "H", "L", "CRIT")

**Label Studio Configuration:**
```xml
<View>
  <Labels name="ner" toName="text">
    <Label value="TEST_NAME" background="#b3e5fc"/>
    <Label value="VALUE" background="#c8e6c9"/>
    <Label value="UNIT" background="#ffcdd2"/>
    <Label value="REF_RANGE" background="#ffe0b2"/>
    <Label value="FLAG" background="#f8bbd0"/>
  </Labels>
  <Text name="text" value="$text"/>
</View>
```

**Labeling Tips:**
- Only show lines that were tagged as `TEST_ROW` in Project 1
- Include edge cases: missing units, text ranges ("Negative"), unusual flags
- Target ≥1,500 test rows across many different vendors

### Project 3: Header Field Extraction

**Goal**: Extract structured fields from header sections. This validates our rule-based extraction.

**Key Labels**: `PATIENT_NAME`, `DOB`, `SEX`, `MRN`, `ADDRESS`, `PHONE`, `SPECIMEN_ID`, `COLLECTED_AT`, `RECEIVED_AT`, `REPORTED_AT`, `ORDERING_PROVIDER`, `PERFORMING_LAB`, `CLIA`

**Label Studio Configuration:**
```xml
<View>
  <Labels name="hdr" toName="text">
    <Label value="PATIENT_NAME"/><Label value="DOB"/><Label value="SEX"/><Label value="MRN"/>
    <Label value="ADDRESS"/><Label value="PHONE"/>
    <Label value="SPECIMEN_ID"/><Label value="COLLECTED_AT"/><Label value="RECEIVED_AT"/>
    <Label value="ORDERING_PROVIDER"/><Label value="PERFORMING_LAB"/><Label value="CLIA"/>
  </Labels>
  <Text name="text" value="$text"/>
</View>
```

---

## 📊 Data collection strategy

### Where to get PDFs
- **Primary**: Live fax inbox (de-identify first!)
- **Secondary**: Test portals, vendor sample reports
- **Backup**: Previously scanned/saved lab reports

### De-identification (CRITICAL!)
Before labeling, run a script to redact:
- Patient names → "DOE, JOHN"
- Phone numbers → "(555) 123-4567"
- Addresses → "123 Main St, City, ST 12345"
- MRNs/IDs → "A1234567"

**Keep layout intact** - spacing and formatting must be preserved!

### Diversity targets
- **Vendors**: ≥10 different labs (LabCorp, Quest, hospital labs, etc.)
- **Panel types**: CMP, CBC, Lipid, Thyroid, A1C, Urinalysis, etc.
- **Document quality**: Clean digital PDFs, scanned images, multi-page reports
- **Phase 1 goal**: ~50 documents per vendor = ~500 PDFs total

---

## 🛠️ Complete end-to-end workflow

**Prerequisites**: Docker Desktop installed and running, git repo cloned

### Step 0: Environment setup

```bash
# Navigate to project root
cd /path/to/lab-ai

# Start all services (this takes a few minutes first time)
make down || true  # Stop any existing containers
make build         # Build all Docker images
make up           # Start all services

# Verify services are running
make status
```

**Expected services:**
- API: http://localhost:8000
- UI: http://localhost:3000
- Label Studio: http://localhost:8080 (admin@localhost/changeme)
- Redis: localhost:6379

### Step 1: Set up Label Studio projects

1. Go to http://localhost:8080, login with admin@localhost/changeme
2. Create three projects using the XML configs above
3. Import your de-identified PDF text data

### Step 2: Label your data

**For Project 1 (Line Roles):**
- Export lines from PDF extraction to Label Studio format
- Label each line with appropriate role
- Export results to `/data/labelstudio/exports/roles.json`

**For Project 2 (Test-Row Tokens):**
- Filter to only `TEST_ROW` lines from Project 1
- Label tokens within each line
- Export results to `/data/labelstudio/exports/testrow.json`

**For Project 3 (Headers):**
- Label header fields for validation
- Export results to `/data/labelstudio/exports/headers.json`

### Step 3: Prepare training data

**For Line Roles:**
```bash
# Check that your export file exists
docker compose exec trainer ls -la /data/labelstudio/exports/roles.json

# The training expects data at this specific path:
# /data/training/roles/roles.aug.json
# Copy/move your export there if needed
docker compose exec trainer mkdir -p /data/training/roles
docker compose exec trainer cp /data/labelstudio/exports/roles.json /data/training/roles/roles.aug.json
```

**For Test-Row Tokens:**
```bash
# Convert Label Studio export to JSONL format
docker compose exec trainer python -m services.trainer.testrow.prep_testrow \
  /data/labelstudio/exports/testrow.json \
  --output /data/training/testrow/all.jsonl

# Split into train/dev sets (80/20 split)
docker compose exec trainer python - << 'EOF'
import json, random
random.seed(13)

# Load all data
with open('/data/training/testrow/all.jsonl', 'r') as f:
    lines = [line.strip() for line in f if line.strip()]

# Shuffle and split
random.shuffle(lines)
split_idx = int(0.8 * len(lines))

# Write training set
with open('/data/training/testrow/train.jsonl', 'w') as f:
    for line in lines[:split_idx]:
        f.write(line + '\n')

# Write dev set
with open('/data/training/testrow/dev.jsonl', 'w') as f:
    for line in lines[split_idx:]:
        f.write(line + '\n')

print(f"Created train.jsonl with {split_idx} examples")
print(f"Created dev.jsonl with {len(lines) - split_idx} examples")
EOF

# Verify files were created
docker compose exec trainer wc -l /data/training/testrow/*.jsonl
```

### Step 4: Train the models

**Train Line Roles Classifier:**
```bash
# This trains a TF-IDF + LogisticRegression model
make roles.train

# Evaluate the trained model
make roles.eval

# Check that model files were created
docker compose exec trainer ls -la /models/roles/
```

**Expected output files:**
- `/models/roles/model.joblib` - The trained classifier
- `/models/roles/vectorizer.joblib` - The TF-IDF vectorizer
- `/models/roles/metadata.json` - Model info and performance metrics

**Train Test-Row CRF:**
```bash
# This trains a CRF (Conditional Random Field) model
make testrow.train

# Evaluate the trained model
make testrow.eval

# Check that model files were created
docker compose exec trainer ls -la /models/testrow/
```

**Expected output files:**
- `/models/testrow/model.crf` - The trained CRF model
- `/models/testrow/metadata.json` - Model info and performance metrics

### Step 5: Verify models are loaded

```bash
# Check that worker can load the models
docker compose exec worker python - << 'EOF'
from services.worker import tasks

# Check roles model
print("Roles model loaded:", hasattr(tasks, 'classify_line_roles'))

# Check testrow model
print("TestRow model loaded:", hasattr(tasks, 'tag_testrow_line'))

# Test the models
if hasattr(tasks, 'tag_testrow_line'):
    result = tasks.tag_testrow_line("Glucose 101 mg/dL 70-99 H")
    print("TestRow demo:", result)
EOF
```

### Step 6: Process PDFs end-to-end

```bash
# Put a test PDF in the inbox
cp your-test-file.pdf /data/inbox/

# Process it (replace 'filename' with your actual file basename without .pdf)
make reprocess.one FILE=filename

# Check the results
make debug-report

# Look at the structured output
docker compose exec trainer ls -la /data/outbox/filename*
docker compose exec trainer cat /data/outbox/filename.json | head -50
```

### Step 7: Review and improve via UI

1. Go to http://localhost:3000
2. Navigate to your processed result
3. Use the review interface to make corrections
4. Export corrections back to training data
5. Retrain models with improved data

---

## 📊 Quality gates & success metrics

### Line Roles Classifier
- **Target**: ≥90% precision and recall on `TEST_ROW` and `SECTION_PANEL`
- **Check**: Classification report from `make roles.eval`
- **Improve**: Add more diverse examples of misclassified cases

### Test-Row CRF
- **Target**: ≥90% F1 score on `TEST_NAME`, `VALUE`, `UNIT` fields
- **Check**: Entity-level metrics from `make testrow.eval`
- **Improve**: Add more examples of poorly tagged test rows

### End-to-End Pipeline
- **Target**: Every PDF produces ≥1 panel with parsed test results
- **Check**: Process 10 diverse PDFs, manually verify outputs
- **Improve**: Fix extraction rules, add missing training examples

---

## 🔧 Troubleshooting common issues

### "Worker says testrow loaded? False"
**Problem**: CRF model not loading
**Solution**:
```bash
# Check model files exist
docker compose exec trainer ls -la /models/testrow/

# Verify metadata.json has correct format
docker compose exec trainer cat /models/testrow/metadata.json

# Restart worker
docker compose restart worker
```

### "Roles training tries to contact HuggingFace"
**Problem**: Code trying to download transformer models
**Solution**: Ensure you're using `--embedding-model tfidf` (not transformers)

### "No test rows found in processed PDF"
**Problem**: Line roles classifier not identifying test lines correctly
**Solution**:
1. Check `debug.json` output to see line classifications
2. Add more `TEST_ROW` examples to training data
3. Retrain roles model
4. Reprocess PDF

### "Test row parsing is messy"
**Problem**: CRF model not extracting test components correctly
**Solution**:
1. Add the problematic test rows to testrow training data
2. Label them carefully in Label Studio
3. Retrain CRF model
4. Usually 200-300 new examples fixes most issues

### UI shows "Failed to load result"
**Problem**: Result ID mismatch or file not found
**Solution**:
```bash
# Check if files exist
docker compose exec trainer ls -la /data/outbox/ | grep your-id

# Check file permissions
docker compose exec trainer ls -la /data/outbox/your-file.json

# Restart API service
docker compose restart api
```

---

## 🚀 Production deployment roadmap

### Phase 1: Foundation (Current)
- [x] Core 3-layer architecture working
- [x] Docker deployment with all services
- [x] Basic UI for review and corrections
- [ ] Train on 500+ diverse PDFs
- [ ] Achieve 90%+ accuracy on key metrics

### Phase 2: Scale (Next 3 months)
- [ ] Automated training pipeline
- [ ] Active learning (auto-select low-confidence examples for labeling)
- [ ] Model versioning and A/B testing
- [ ] Production monitoring and alerting

### Phase 3: Production (Next 6 months)
- [ ] FHIR output format
- [ ] EHR integration testing
- [ ] Compliance and security review
- [ ] Load testing and performance optimization

---

## 💡 Weekly improvement loop

1. **Monday**: Process new PDFs from fax inbox
2. **Tuesday**: Review UI corrections, export to training data
3. **Wednesday**: Add 100-200 new labels in Label Studio
4. **Thursday**: Retrain models with updated data
5. **Friday**: Evaluate new models, deploy if improved

**Goal**: Continuous 1-2% weekly accuracy improvements

---

## 📁 File locations reference

**Training Data:**
- `/data/labelstudio/exports/` - Raw exports from Label Studio
- `/data/training/roles/roles.aug.json` - Roles training data
- `/data/training/testrow/train.jsonl` - TestRow training data
- `/data/training/testrow/dev.jsonl` - TestRow validation data

**Models:**
- `/models/roles/` - Line roles classifier files
- `/models/testrow/` - Test-row CRF model files

**Processing:**
- `/data/inbox/` - Put PDFs here for processing
- `/data/outbox/` - Structured JSON results appear here

**Code:**
- `services/trainer/roles/` - Line roles training code
- `services/trainer/testrow/` - Test-row training code
- `services/worker/` - Production inference code

---

## 🎯 Example success: What good output looks like

```json
{
  "vendor": {
    "name": "LabCorp",
    "account_number": "12345"
  },
  "patient": {
    "last_name": "DOE",
    "first_name": "JOHN",
    "dob": "1960-01-01",
    "sex": "M",
    "mrn": "A1234567"
  },
  "specimen": {
    "id": "ACC123456",
    "collected_at": "2025-09-19T08:00:00Z",
    "type": "serum"
  },
  "performing_lab": {
    "name": "LabCorp",
    "clia": "12D3456789"
  },
  "panels": [
    {
      "name": "COMPREHENSIVE METABOLIC PANEL",
      "tests": [
        {
          "name": "Glucose",
          "value": "101",
          "unit": "mg/dL",
          "reference_range": "70-99",
          "flag": "H"
        },
        {
          "name": "Sodium",
          "value": "142",
          "unit": "mmol/L",
          "reference_range": "136-145",
          "flag": null
        }
      ]
    }
  ]
}
```

---

## 📞 Getting help

If you get stuck:
1. Check the troubleshooting section above
2. Look at `/data/outbox/*.debug.json` files for diagnostic info
3. Check Docker logs: `docker compose logs api worker trainer`
4. Review this guide from the beginning—often you missed a step

**Remember**: This is a step-by-step process. Each piece builds on the previous one. Don't skip steps, and verify each stage works before moving to the next.

**You've got this!** 🚀