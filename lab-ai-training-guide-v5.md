# Lab‑AI Training & Maturation Guide v5 (Complete Step‑by‑Step)

_Last updated: 2025-09-19_

**🎯 Purpose**: This guide provides **exact commands and detailed steps** for anyone to grow our proof‑of‑concept into a production‑ready lab ingestion pipeline. No ML knowledge required—just follow the steps exactly.

**👤 Audience**: Engineers, analysts, support teams, anyone who needs to contribute to model training.

---

## 📚 What we're building (simple explanation)

Our system reads lab PDF reports and converts them into structured data (like turning a messy paper form into a clean database). Here's how it works:

1. **PDF → Text Lines**: Extract every line of text from the PDF with position info
2. **Line Classification**: Label each line (test result, patient info, junk, etc.)
3. **Test Parsing**: Break test lines into parts (test name, value, units, flags)
4. **Header Extraction**: Pull out patient/lab info from header sections
5. **JSON Output**: Combine everything into clean structured data

### Our System Architecture

**Services in our Docker setup:**
- **UI** (http://localhost:3000): React website for reviewing/correcting results
- **API** (http://localhost:8000): Saves/retrieves data, handles corrections
- **Worker**: Runs PDFs through our trained models
- **Trainer**: Training environment with all ML utilities
- **Extractor**: Converts PDFs to text lines
- **Label Studio** (http://localhost:8080): Web tool for labeling training data
- **Redis**: Message broker for coordinating everything

---

## 🎯 What data we capture

**Goal**: Convert messy PDF lab reports into clean JSON like this:

```json
{
  "patient": {"name": "DOE, JOHN", "dob": "1960-01-01", "sex": "M"},
  "specimen": {"id": "A123456", "collected_at": "2025-09-19"},
  "panels": [{
    "name": "COMPREHENSIVE METABOLIC PANEL",
    "tests": [
      {"name": "Glucose", "value": "95", "unit": "mg/dL", "reference_range": "70-99", "flag": null}
    ]
  }]
}
```

---

## 🛠️ STEP-BY-STEP: Getting your environment ready

### Step 0: Prerequisites check

**What you need installed:**
- Docker Desktop (running)
- Git
- Terminal/Command Prompt

**Verify Docker is working:**
```bash
docker --version
docker compose --version
```

### Step 1: Start the system

```bash
# Navigate to project directory
cd /path/to/lab-ai

# Stop any existing containers and start fresh
make down || true
make build
make up

# Wait 2-3 minutes for everything to start
make status
```

**Expected output:** All services should show as "running" or "healthy"

**Test the services:**
- API: http://localhost:8000/health (should show "OK")
- UI: http://localhost:3000 (should load the web interface)
- Label Studio: http://localhost:8080 (login: admin@localhost/changeme)

---

## 📊 STEP-BY-STEP: Creating training data

### Step 2: Get some PDFs to work with

**Where to find lab PDFs:**
1. **Test PDFs**: Use sample lab reports (de-identified)
2. **Fax inbox**: Get real PDFs but DE-IDENTIFY first
3. **Online samples**: Download vendor sample reports

**CRITICAL - De-identify PDFs first:**
- Replace patient names: "Smith, John" → "DOE, JOHN"
- Replace phone numbers: "(555) 123-4567"
- Replace addresses: "123 Main St, City, ST 12345"
- Keep the layout exactly the same!

### Step 3: Extract text lines from PDFs

**Put your PDF in the system:**
```bash
# Copy your PDF to the inbox
cp your-sample-lab-report.pdf /data/inbox/

# OR if you're outside the container:
docker compose exec api cp /your/pdf/path.pdf /data/inbox/
```

**Extract lines from the PDF:**
```bash
# Replace 'sample-lab-report' with your PDF filename (without .pdf)
make extract-lines PDF=/data/inbox/sample-lab-report.pdf

# This creates: /data/outbox/sample-lab-report.lines.json
# Check it was created:
docker compose exec trainer ls -la /data/outbox/sample-lab-report*
```

**Look at what was extracted:**
```bash
# See the first 20 lines extracted from your PDF
docker compose exec trainer head -20 /data/outbox/sample-lab-report.lines.json
```

You should see JSON with text lines and position information.

### Step 4: Convert PDF lines to Label Studio format

**Convert extracted lines to tasks for labeling:**
```bash
# This converts the lines.json file to a format Label Studio can import
docker compose exec trainer python -m services.trainer.utils.lines_to_ls \
  /data/outbox/sample-lab-report.lines.json \
  --out /data/labelstudio/imports/sample-lab-report.ls.json \
  --strip-cid \
  --min-chars 3

# Verify the file was created:
docker compose exec trainer ls -la /data/labelstudio/imports/
docker compose exec trainer head -10 /data/labelstudio/imports/sample-lab-report.ls.json
```

**Repeat for more PDFs:** Do this for 5-10 different PDFs to get variety.

---

## 🏷️ STEP-BY-STEP: Label Studio setup and labeling

### Step 5: Set up Label Studio projects

**Access Label Studio:**
1. Go to http://localhost:8080
2. Login with username: `admin`, password: `admin`
3. You should see the Label Studio dashboard

**Create Project 1 - Line Roles:**

1. Click **"Create Project"**
2. Project Name: **"Line Roles Classification"**
3. Click **"Data Import"** tab
4. Click **"Upload Files"** and select `/data/labelstudio/imports/sample-lab-report.ls.json`
   - **Note**: You may need to navigate to the Docker volume or copy the file to your local machine first
5. Click **"Settings"** tab
6. Click **"Labeling Interface"**
7. Delete any existing XML and paste this:

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

8. Click **"Save"**

**Create Project 2 - Test Row Tokens:**

1. Click **"Create Project"**
2. Project Name: **"Test Row Token Tagging"**
3. **Data Import**: Upload lines that you labeled as "TEST_ROW" from Project 1
4. **Labeling Interface**:

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

### Step 6: Label your data (the manual work)

**For Project 1 (Line Roles):**

1. Go to your "Line Roles Classification" project
2. Click **"Label All Tasks"**
3. For each line of text you see, click the appropriate role:
   - **TEST_ROW**: `Glucose 95 mg/dL 70-99`
   - **SECTION_PANEL**: `COMPREHENSIVE METABOLIC PANEL`
   - **HEADER_PATIENT**: `Patient: DOE, JOHN DOB: 01/01/1960`
   - **HEADER_SPECIMEN**: `Specimen ID: A123456 Collected: 09/19/2025`
   - **PAGE_HEADER**: `LabCorp` (at top of page)
   - **PAGE_FOOTER**: `Lab address and phone numbers`
   - **COMMENT**: `Reference ranges are for adults`
   - **SECTION_MISC**: `Additional Tests Ordered:`
   - **JUNK**: Garbled text, artifacts, meaningless strings

4. **Label 300+ lines total** (aim for 30+ examples of each type)
5. Focus on getting good coverage of different vendors/layouts

**For Project 2 (Test Row Tokens):**

1. Go to your "Test Row Token Tagging" project
2. For each test row, highlight and label parts:
   - Highlight "Glucose" → Label: **TEST_NAME**
   - Highlight "95" → Label: **VALUE**
   - Highlight "mg/dL" → Label: **UNIT**
   - Highlight "70-99" → Label: **REF_RANGE**
   - Highlight "H" → Label: **FLAG**

3. **Label 200+ test rows** from different panels and vendors

### Step 7: Export labeled data

**Export from Project 1 (Line Roles):**
1. In Label Studio, go to your "Line Roles Classification" project
2. Click **"Export"** button (top right)
3. Choose **"JSON"** format
4. Download the file
5. **Copy it to the container:**

```bash
# Copy your downloaded export to the container
# Replace 'project-1-export.json' with your actual downloaded filename
docker compose cp project-1-export.json trainer:/data/labelstudio/exports/roles.json

# Verify it's there:
docker compose exec trainer ls -la /data/labelstudio/exports/
```

**Export from Project 2 (Test Row Tokens):**
1. In Label Studio, go to your "Test Row Token Tagging" project
2. Click **"Export"** button
3. Choose **"JSON"** format
4. Download and copy to container:

```bash
docker compose cp project-2-export.json trainer:/data/labelstudio/exports/testrow.json
```

---

## 🚀 STEP-BY-STEP: Train the models

### Step 8: Prepare training data

**Prepare Line Roles data:**
```bash
# Convert Label Studio export to training format
docker compose exec trainer python -m services.trainer.roles.prep_roles \
  /data/labelstudio/exports/roles.json \
  --output /data/training/roles/roles.aug.json

# Check what was created:
docker compose exec trainer ls -la /data/training/roles/
docker compose exec trainer head -20 /data/training/roles/roles.aug.json
```

**Prepare Test Row data:**
```bash
# Convert Label Studio export to JSONL training format
docker compose exec trainer python -m services.trainer.testrow.prep_testrow \
  /data/labelstudio/exports/testrow.json \
  --output /data/training/testrow/all.jsonl

# Split into training and validation sets (80/20)
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

# Write validation set
with open('/data/training/testrow/dev.jsonl', 'w') as f:
    for line in lines[split_idx:]:
        f.write(line + '\n')

print(f"✅ Split complete:")
print(f"   Training: {split_idx} examples")
print(f"   Validation: {len(lines) - split_idx} examples")
EOF

# Verify files were created:
docker compose exec trainer wc -l /data/training/testrow/*.jsonl
```

### Step 9: Train the Line Roles model

```bash
# Train the model (this takes 2-5 minutes)
make roles.train

# You should see output like:
# Training complete. Model saved to /models/roles/
# Accuracy: 0.95, F1: 0.94
```

**Check the model was created:**
```bash
docker compose exec trainer ls -la /models/roles/
# Should show: metadata.json, model.joblib, vectorizer.joblib
```

**Evaluate the model:**
```bash
make roles.eval

# Look for these target metrics:
# - Overall accuracy: >90%
# - TEST_ROW precision/recall: >90%
# - SECTION_PANEL precision/recall: >85%
```

### Step 10: Train the Test Row model

```bash
# Train the CRF model (this takes 5-10 minutes)
make testrow.train

# You should see:
# Training complete. Model saved to /models/testrow/
# F1 scores for each entity type...
```

**Check the model was created:**
```bash
docker compose exec trainer ls -la /models/testrow/
# Should show: metadata.json, model.crf
```

**Evaluate the model:**
```bash
make testrow.eval

# Look for these target metrics:
# - TEST_NAME F1: >85%
# - VALUE F1: >90%
# - UNIT F1: >85%
# - REF_RANGE F1: >80%
```

### Step 11: Verify models are working

**Test that the worker can load both models:**
```bash
docker compose exec worker python - << 'EOF'
# Test roles model
try:
    from services.worker.runtime.roles_infer import classify_line_roles
    result = classify_line_roles([{"text": "Glucose 95 mg/dL 70-99"}])
    print("✅ Roles model working:", result[0] if result else "No result")
except Exception as e:
    print("❌ Roles model error:", e)

# Test testrow model
try:
    from services.worker.runtime.testrow_infer import tag_testrow_line
    result = tag_testrow_line("Glucose 95 mg/dL 70-99")
    print("✅ TestRow model working:", result)
except Exception as e:
    print("❌ TestRow model error:", e)
EOF
```

**If you see errors:**
```bash
# Restart the worker to reload models
docker compose restart worker

# Wait 30 seconds, then test again
```

---

## ✅ STEP-BY-STEP: Test end-to-end processing

### Step 12: Process a PDF with your trained models

```bash
# Put a test PDF in the inbox
cp your-test-file.pdf /data/inbox/test-file.pdf

# Process it with your trained models
# Replace 'test-file' with your PDF filename (without .pdf)
make reprocess.one FILE=test-file

# Check the results
docker compose exec trainer ls -la /data/outbox/test-file*

# Look at the final structured output
docker compose exec trainer head -50 /data/outbox/test-file.json
```

**What you should see:**
- `test-file.json`: Final structured output with panels and tests
- `test-file.debug.json`: Detailed processing information
- Test rows properly classified and parsed into components

### Step 13: Review results in the UI

1. Go to http://localhost:3000
2. You should see your processed PDF in the list
3. Click **"View"** to see the results
4. Check that:
   - Patient info was extracted correctly
   - Test panels are grouped properly
   - Individual test values, units, and flags are correct
5. Use the **"Review & Edit"** button to make corrections

---

## 🔍 TROUBLESHOOTING: Common issues and solutions

### "No lines extracted from PDF"
**Problem**: The extractor can't read your PDF
**Solution**:
```bash
# Check if the PDF file exists and is readable
docker compose exec trainer ls -la /data/inbox/your-file.pdf

# Try a different PDF - some are corrupted or image-only
# Make sure it's a text-based PDF, not a scanned image
```

### "Worker says testrow loaded? False"
**Problem**: CRF model didn't load properly
**Solution**:
```bash
# Check model files exist
docker compose exec trainer ls -la /models/testrow/

# Check the metadata file
docker compose exec trainer cat /models/testrow/metadata.json

# Restart worker and try again
docker compose restart worker
```

### "Roles training failed"
**Problem**: Not enough training data or data format issue
**Solution**:
```bash
# Check your training data
docker compose exec trainer python -m services.trainer.roles.prep_roles \
  /data/labelstudio/exports/roles.json \
  --validate

# Make sure you have:
# - At least 50 examples of TEST_ROW
# - At least 20 examples of each other role
# - No validation errors in the output
```

### "Label Studio won't import my file"
**Problem**: File format or permissions issue
**Solution**:
```bash
# Check the file format is correct
docker compose exec trainer head -5 /data/labelstudio/imports/your-file.ls.json

# Should be Label Studio JSON format, not raw lines
# Re-run the lines_to_ls conversion script if needed
```

### "Models are terrible - everything classified wrong"
**Problem**: Not enough diverse training data
**Solution**:
1. **More variety**: Label data from 5+ different vendors/layouts
2. **More volume**: Aim for 300+ labeled lines, 200+ test rows
3. **Better quality**: Review your labels - are they consistent?
4. **Re-train**: After adding more data, re-run training

---

## 📈 SUCCESS METRICS: How to know you're on track

### Line Roles Model
**Target Performance:**
- Overall accuracy: **≥90%**
- TEST_ROW precision: **≥90%**
- TEST_ROW recall: **≥90%**
- SECTION_PANEL precision: **≥85%**

**How to check:**
```bash
make roles.eval
# Look at the classification report output
```

### Test Row CRF Model
**Target Performance:**
- TEST_NAME F1: **≥85%**
- VALUE F1: **≥90%**
- UNIT F1: **≥85%**
- REF_RANGE F1: **≥80%**

**How to check:**
```bash
make testrow.eval
# Look at the entity-level F1 scores
```

### End-to-End Pipeline
**Target Performance:**
- **90%+ of PDFs** produce at least 1 panel with tests
- **95%+ of test values** extracted correctly
- **90%+ of test names** extracted correctly
- **85%+ of units and reference ranges** extracted correctly

**How to check:**
Process 10 diverse PDFs and manually review the JSON outputs.

---

## 🔄 WEEKLY IMPROVEMENT LOOP

### Monday: Collect new data
```bash
# Process new PDFs from your inbox
cp new-pdf-1.pdf /data/inbox/
make reprocess.one FILE=new-pdf-1

# Identify problematic results
# Look for PDFs where extraction failed or was poor quality
```

### Tuesday: Review and correct
1. Go to http://localhost:3000
2. Review recent processing results
3. Use the UI to make corrections
4. Export corrections for training data

### Wednesday: Add training examples
1. Convert new PDFs to Label Studio format
2. Import into Label Studio
3. Label 50-100 new lines/test rows
4. Focus on cases where current models failed

### Thursday: Retrain models
```bash
# Export updated labels from Label Studio
# Re-run the training preparation and training steps
make roles.train
make testrow.train
```

### Friday: Evaluate improvements
```bash
# Run evaluations on both models
make roles.eval
make testrow.eval

# Process a few test PDFs to see if accuracy improved
# Deploy new models if performance is better
```

**Goal**: Achieve 1-2% accuracy improvement each week.

---

## 📁 QUICK REFERENCE: File locations and commands

### Important File Paths
```
/data/inbox/                          # Put PDFs here for processing
/data/outbox/                         # Structured JSON results
/data/labelstudio/exports/            # Label Studio export files
/data/labelstudio/imports/            # Files to import into Label Studio
/data/training/roles/                 # Line roles training data
/data/training/testrow/               # Test row training data
/models/roles/                        # Trained line roles model
/models/testrow/                      # Trained test row CRF model
```

### Essential Commands
```bash
# Environment
make up                               # Start all services
make down                             # Stop all services
make status                           # Check service health

# Data preparation
make extract-lines PDF=/data/inbox/file.pdf
python -m services.trainer.utils.lines_to_ls [file.lines.json]

# Training
make roles.train                      # Train line roles model
make roles.eval                       # Evaluate line roles model
make testrow.train                    # Train test row CRF model
make testrow.eval                     # Evaluate test row model

# Processing
make reprocess.one FILE=basename      # Process single PDF
make debug-report                     # Quick diagnostics
```

### Service URLs
- **UI**: http://localhost:3000
- **API**: http://localhost:8000
- **Label Studio**: http://localhost:8080 (admin@localhost/changeme)

---

## 🎯 NEXT STEPS: Scaling to production

### Phase 1: Foundation (Current)
- [x] Core architecture working
- [x] Training pipeline established
- [x] Basic UI for review/corrections
- [ ] **Train on 500+ PDFs from 10+ vendors**
- [ ] **Achieve 90%+ accuracy targets**

### Phase 2: Automation (Next 3 months)
- [ ] Automated data collection from fax systems
- [ ] Active learning (auto-select difficult cases for labeling)
- [ ] Model versioning and A/B testing
- [ ] Automated quality monitoring

### Phase 3: Production (Next 6 months)
- [ ] FHIR output format for EHR integration
- [ ] Compliance and security audit
- [ ] Load testing and performance optimization
- [ ] Multi-tenant deployment

---

## 🎓 TRAINING TIPS: How to be effective

### For Line Roles Labeling
- **Be consistent**: Same types of lines should get same labels
- **When in doubt**: SECTION_MISC is better than wrong specific label
- **Context matters**: Look at surrounding lines to understand structure
- **Quality over speed**: Better to label 50 lines correctly than 200 poorly

### For Test Row Token Labeling
- **Follow BIO format**: First word of entity gets B-, continuation gets I-
- **Units are tricky**: "mg/dL" is one unit, "K/uL" is one unit
- **Ranges are inclusive**: "70-99" is all one REF_RANGE
- **Flags vary**: Could be "H", "HIGH", "*", "ABN", etc.

### General Best Practices
- **Diverse data wins**: 10 different vendor layouts > 100 examples from one vendor
- **Label edge cases**: Weird formatting, missing values, unusual units
- **Document decisions**: Keep notes on labeling rules for consistency
- **Test frequently**: Retrain after every 100-200 new examples

---

**🚀 You're ready to scale up the lab-ai training pipeline! Follow these steps exactly and you'll have production-quality models in no time.**