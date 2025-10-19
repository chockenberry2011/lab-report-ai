# Document NER Testing Guide - Complete A-Z Instructions

_Your mission: Test the new document-level field extraction system with your 4 sample PDFs_

**🎯 Goal**: Set up and test our new comprehensive field extraction that will handle all the layout variations across different lab vendors.

**⏰ Estimated Time**: 2-3 hours total
- Setup: 30 minutes
- Labeling: 45 minutes per document
- Testing: 30 minutes

---

## 📋 Prerequisites Check

**Before starting, verify these are working:**

```bash
# 1. Check that you're in the lab-ai directory
pwd
# Should show: /Users/charliehockenberry/source/lab-ai (or your path)

# 2. Check Docker is running
docker --version
# Should show: Docker version 20.x.x or higher

# 3. Check services are running
make status
# Should show all services as "running" or "healthy"

# 4. Test UI access
# Open browser: http://localhost:3000 (should load)
# Open Label Studio: http://localhost:8080 (should load)
```

**If any of these fail:**
```bash
# Start services
make down || true
make build
make up
# Wait 3-5 minutes, then try again
```

---

## 🔍 Step 1: Audit Current Field Extraction (15 minutes)

**Goal**: See which fields are currently empty in your review form so we know what to improve.

### 1.1 Process your sample PDFs

```bash
# List your current PDFs in the inbox
docker compose exec api ls -la /data/inbox/

# If you don't have PDFs there, copy them:
# Replace 'your-pdf-name.pdf' with your actual PDF filename
cp /path/to/your-sample-1.pdf /data/inbox/sample-1.pdf
cp /path/to/your-sample-2.pdf /data/inbox/sample-2.pdf
cp /path/to/your-sample-3.pdf /data/inbox/sample-3.pdf
cp /path/to/your-sample-4.pdf /data/inbox/sample-4.pdf

# Process each PDF (replace 'sample-1' with your actual filename without .pdf)
make reprocess.one FILE=sample-1
make reprocess.one FILE=sample-2
make reprocess.one FILE=sample-3
make reprocess.one FILE=sample-4
```

### 1.2 Check what fields are currently populated

```bash
# Check the JSON output for one sample (replace 'sample-1' with your filename)
docker compose exec trainer cat /data/outbox/sample-1.json | head -50

# Look specifically at header fields:
docker compose exec trainer cat /data/outbox/sample-1.json | jq '.patient, .provider, .specimen, .performing_lab'
```

### 1.3 Document current state

**Create a notes file to track your findings:**
```bash
# Create a testing notes file
touch testing-notes.md
```

**In testing-notes.md, record for each PDF:**
- PDF name:
- Patient fields populated: (list which ones have data)
- Provider fields populated: (list which ones have data)
- Specimen fields populated: (list which ones have data)
- Lab fields populated: (list which ones have data)
- **Total estimated fields missing**: X out of Y

---

## 🏷️ Step 2: Set Up Label Studio Project (15 minutes)

### 2.1 Access Label Studio

```bash
# Open Label Studio in your browser
open http://localhost:8080
# Or manually go to: http://localhost:8080

# Login credentials:
# Username: admin
# Password: admin
```

### 2.2 Create the Document NER Project

1. **Click "Create Project"**
2. **Project Name**: `Document Field Extraction`
3. **Description**: `Comprehensive field extraction for all lab report fields`

### 2.3 Set Up Data Import

1. **Click "Data Import" tab**
2. **We'll import data in Step 3** - skip for now

### 2.4 Configure Labeling Interface

1. **Click "Settings" tab**
2. **Click "Labeling Interface"**
3. **Delete any existing XML**
4. **Paste this exact XML**:

```xml
<View>
  <Labels name="label" toName="text">
    <!-- Patient Fields -->
    <Label value="PATIENT_LAST_NAME" background="#FF6B6B"/>
    <Label value="PATIENT_FIRST_NAME" background="#FF8E8E"/>
    <Label value="PATIENT_MIDDLE_NAME" background="#FFB1B1"/>
    <Label value="PATIENT_DOB" background="#4ECDC4"/>
    <Label value="PATIENT_SEX" background="#67D7D0"/>
    <Label value="PATIENT_MRN" background="#45B7D1"/>
    <Label value="PATIENT_ADDRESS_STREET" background="#96CEB4"/>
    <Label value="PATIENT_ADDRESS_CITY" background="#B8D8C7"/>
    <Label value="PATIENT_ADDRESS_STATE" background="#DAE2DA"/>
    <Label value="PATIENT_ADDRESS_ZIP" background="#FFEAA7"/>
    <Label value="PATIENT_PHONE" background="#FDCB6E"/>
    <Label value="PATIENT_AGE" background="#E17055"/>

    <!-- Provider Fields -->
    <Label value="ORDERING_PROVIDER_NAME" background="#DDA0DD"/>
    <Label value="PROVIDER_NPI" background="#E6B8E6"/>
    <Label value="ORDERING_CLINIC_NAME" background="#F0D0F0"/>
    <Label value="ORDERING_CLINIC_ADDRESS" background="#F8E8F8"/>
    <Label value="ORDERING_CLINIC_PHONE" background="#D1A3D1"/>

    <!-- Specimen Fields -->
    <Label value="SPECIMEN_ID" background="#F4A460"/>
    <Label value="ACCESSION_NUMBER" background="#F7B373"/>
    <Label value="COLLECTION_DATE" background="#FAC286"/>
    <Label value="COLLECTION_TIME" background="#FDD199"/>
    <Label value="RECEIVED_DATE" background="#FFE0AC"/>
    <Label value="RECEIVED_TIME" background="#FFEFBF"/>
    <Label value="REPORTED_DATE" background="#FFB347"/>
    <Label value="REPORTED_TIME" background="#FFC266"/>
    <Label value="SPECIMEN_TYPE" background="#FFD185"/>
    <Label value="SPECIMEN_SOURCE" background="#FFE0A4"/>

    <!-- Lab Fields -->
    <Label value="PERFORMING_LAB" background="#87CEEB"/>
    <Label value="LAB_CLIA" background="#9DD9F3"/>
    <Label value="LAB_ADDRESS" background="#B3E4FB"/>
    <Label value="LAB_PHONE" background="#C9F0FF"/>
    <Label value="LAB_FAX" background="#DEB887"/>
    <Label value="LAB_DIRECTOR" background="#E6C79A"/>

    <!-- Report Fields -->
    <Label value="REPORT_ID" background="#F0F8FF"/>
    <Label value="REPORT_DATE" background="#E6F3FF"/>
    <Label value="REPORT_TIME" background="#DCEEFF"/>
    <Label value="PAGE_NUMBER" background="#D2E9FF"/>
    <Label value="CLINICAL_INFO" background="#C8E4FF"/>
    <Label value="VENDOR_ACCOUNT" background="#BED9FF"/>
  </Labels>
  <Text name="text" value="$text"/>
</View>
```

5. **Click "Save"**

---

## 📄 Step 3: Prepare PDFs for Labeling (20 minutes)

### 3.1 Extract full document text

```bash
# Create directory for document text
docker compose exec trainer mkdir -p /data/labelstudio/documents

# Extract full text from each PDF (replace filenames as needed)
docker compose exec trainer python - << 'EOF'
import json
from pathlib import Path

# List of your PDF basenames (without .pdf extension)
pdf_names = ["sample-1", "sample-2", "sample-3", "sample-4"]

for pdf_name in pdf_names:
    lines_file = f"/data/outbox/{pdf_name}.lines.json"
    output_file = f"/data/labelstudio/documents/{pdf_name}.txt"

    try:
        # Load the lines JSON
        with open(lines_file, 'r') as f:
            data = json.load(f)

        # Extract all text lines
        lines = []
        if isinstance(data, dict) and 'data' in data:
            lines = data['data'].get('lines', [])
        elif isinstance(data, list):
            lines = data

        # Combine all text
        full_text = ""
        for line in lines:
            text = line.get('text', '').strip()
            if text:
                full_text += text + "\n"

        # Save full document text
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(full_text.strip())

        print(f"✅ Created {output_file}")
        print(f"   Text length: {len(full_text)} characters")

    except Exception as e:
        print(f"❌ Error processing {pdf_name}: {e}")

print("\n📄 Document text files created!")
EOF
```

### 3.2 Convert to Label Studio format

```bash
# Convert document text to Label Studio import format
docker compose exec trainer python - << 'EOF'
import json
from pathlib import Path

# List of your PDF basenames
pdf_names = ["sample-1", "sample-2", "sample-3", "sample-4"]

label_studio_tasks = []

for pdf_name in pdf_names:
    text_file = f"/data/labelstudio/documents/{pdf_name}.txt"

    try:
        # Read the document text
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        if text:
            # Create Label Studio task
            task = {
                "data": {
                    "text": text,
                    "source_file": f"{pdf_name}.pdf"
                }
            }
            label_studio_tasks.append(task)
            print(f"✅ Prepared task for {pdf_name}")
        else:
            print(f"⚠️  No text found for {pdf_name}")

    except Exception as e:
        print(f"❌ Error reading {pdf_name}: {e}")

# Save Label Studio import file
output_file = "/data/labelstudio/imports/document_ner_tasks.json"
Path(output_file).parent.mkdir(parents=True, exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(label_studio_tasks, f, indent=2, ensure_ascii=False)

print(f"\n📥 Created Label Studio import file: {output_file}")
print(f"   Total tasks: {len(label_studio_tasks)}")
EOF
```

### 3.3 Import into Label Studio

1. **Go back to Label Studio** (http://localhost:8080)
2. **Go to your "Document Field Extraction" project**
3. **Click "Data Import" tab**
4. **Click "Upload Files"**
5. **Browse to**: `/data/labelstudio/imports/document_ner_tasks.json`
   - **Note**: You may need to copy this file to your local machine first:
   ```bash
   docker compose cp trainer:/data/labelstudio/imports/document_ner_tasks.json ./document_ner_tasks.json
   ```
   Then upload the local file to Label Studio
6. **Click "Import"**
7. **You should see 4 tasks imported**

---

## 🏷️ Step 4: Label Your Documents (45 minutes per document)

**⚠️ IMPORTANT**: Start with just **ONE document** first to test the process.

### 4.1 Start Labeling

1. **In Label Studio, click "Label All Tasks"**
2. **You'll see the full text of your first document**
3. **Your job**: Highlight and label every field you can find

### 4.2 How to Label (Example Patterns)

**Look for these patterns and label them:**

**Patient Names:**
- If you see: `Patient: DOE, JOHN`
  - Highlight `DOE` → Label: **PATIENT_LAST_NAME**
  - Highlight `JOHN` → Label: **PATIENT_FIRST_NAME**

- If you see: `Name: Jane M. Smith`
  - Highlight `Jane` → Label: **PATIENT_FIRST_NAME**
  - Highlight `M` → Label: **PATIENT_MIDDLE_NAME**
  - Highlight `Smith` → Label: **PATIENT_LAST_NAME**

- If you see: `Michael Johnson`
  - Highlight `Michael` → Label: **PATIENT_FIRST_NAME**
  - Highlight `Johnson` → Label: **PATIENT_LAST_NAME**

**Dates:**
- `DOB: 01/15/1980` → Highlight `01/15/1980` → Label: **PATIENT_DOB**
- `Collection Date: Jan 15, 2025` → Highlight `Jan 15, 2025` → Label: **COLLECTION_DATE**
- `Received: 1/16/25` → Highlight `1/16/25` → Label: **RECEIVED_DATE**

**IDs and Numbers:**
- `MRN: A123456789` → Highlight `A123456789` → Label: **PATIENT_MRN**
- `Accession: 12345678` → Highlight `12345678` → Label: **ACCESSION_NUMBER**
- `CLIA: 12D3456789` → Highlight `12D3456789` → Label: **LAB_CLIA**

**Addresses:**
- `123 Main Street` → Highlight `123 Main Street` → Label: **PATIENT_ADDRESS_STREET**
- `Springfield` → Label: **PATIENT_ADDRESS_CITY**
- `IL` → Label: **PATIENT_ADDRESS_STATE**
- `62701` → Label: **PATIENT_ADDRESS_ZIP**

**Doctor/Provider Info:**
- `Ordering Physician: Dr. Smith` → Highlight `Dr. Smith` → Label: **ORDERING_PROVIDER_NAME**
- `ABC Medical Clinic` → Label: **ORDERING_CLINIC_NAME**

### 4.3 Labeling Tips

**DO:**
- ✅ Label every field you can identify
- ✅ Be precise with highlighting (don't include extra spaces or punctuation)
- ✅ Skip fields you're unsure about rather than guess
- ✅ Look for variations (same field might appear multiple times in different formats)

**DON'T:**
- ❌ Include label text (don't label "Patient:" - just label "John Doe")
- ❌ Include punctuation unless it's part of the value
- ❌ Worry about perfect coverage - 60-70% is fine for testing

### 4.4 Complete First Document

1. **Label as many fields as you can find**
2. **Click "Submit" when done**
3. **Note how long it took**

---

## 🧪 Step 5: Test the Training Pipeline (30 minutes)

### 5.1 Export Your Labels

1. **In Label Studio, click "Export"**
2. **Choose "JSON" format**
3. **Download the export file**
4. **Copy to the container**:

```bash
# Replace 'project-1-export.json' with your actual downloaded filename
docker compose cp project-1-export.json trainer:/data/labelstudio/exports/document_ner_export.json

# Verify it's there
docker compose exec trainer ls -la /data/labelstudio/exports/
```

### 5.2 Test Data Preparation

```bash
# Test the data preparation script
docker compose exec trainer python -m services.trainer.document_ner.prep_document_ner \
  /data/labelstudio/exports/document_ner_export.json \
  --output /data/training/document_ner/test_data.jsonl \
  --validate

# Look for these in the output:
# - "Total extracted examples: X"
# - "Entity coverage by category:"
# - Any validation errors
```

**Expected output should show:**
- ✅ At least 1 extracted example
- ✅ Entity coverage showing counts for patient, provider, specimen, lab categories
- ✅ No critical validation errors

### 5.3 Check the Training Data

```bash
# Look at what was extracted
docker compose exec trainer head -5 /data/training/document_ner/test_data.jsonl

# Should show JSON lines with "tokens" and "labels" arrays
```

### 5.4 Report Results

**Add to your testing-notes.md:**

```markdown
## Test Results

### Data Preparation Test
- Documents labeled: 1
- Time to label: X minutes
- Examples extracted: X
- Entity categories found: (list)
- Validation errors: (list any)

### Issues Found
- (list any problems you encountered)

### Next Steps Needed
- (note what you need help with)
```

---

## 🐛 Troubleshooting Common Issues

### "No examples extracted"
**Problem**: Label Studio export format issue
**Solution**:
```bash
# Check the export file format
docker compose exec trainer head -20 /data/labelstudio/exports/document_ner_export.json
# Should be valid JSON with "data", "annotations" fields
```

### "File not found" errors
**Solution**:
```bash
# Check file exists
docker compose exec trainer ls -la /data/labelstudio/exports/
# If missing, re-export from Label Studio and copy again
```

### "Tokenization errors"
**Problem**: Text processing issues
**Solution**:
```bash
# Check document text quality
docker compose exec trainer head -10 /data/labelstudio/documents/sample-1.txt
# Should be clean readable text, not garbled
```

### Label Studio won't load
**Solution**:
```bash
# Restart Label Studio
docker compose restart labelstudio
# Wait 2 minutes, then try http://localhost:8080 again
```

---

## 📊 Success Criteria

**After Step 5, you should have:**
- ✅ 1 document fully labeled in Label Studio
- ✅ Successfully exported and converted to training format
- ✅ At least 10-20 different entity types found
- ✅ No critical validation errors

**If you have these, we're ready to:**
1. Build the training script
2. Train a model on your labeled data
3. Test extraction improvements
4. Scale to label all 4 documents

---

## 📞 When to Stop and Report

**STOP and message me if:**
- ❌ Step 1 shows that most fields are already populated (nothing to improve)
- ❌ Step 3 fails to extract readable text from PDFs
- ❌ Step 4 - you can't find any identifiable fields to label
- ❌ Step 5 shows 0 extracted examples or major validation errors

**CONTINUE to label more documents if:**
- ✅ Step 5 shows successful data extraction
- ✅ You found 10+ different field types to label
- ✅ The process was manageable (even if slow)

---

## 📋 Your Deliverables

**When you finish (or get stuck), send me:**

1. **Your testing-notes.md file** with findings
2. **The training data file**: `/data/training/document_ner/test_data.jsonl`
3. **Any error messages** you encountered
4. **Time estimates**: How long each step took
5. **Label coverage**: What % of fields you were able to identify and label

**Copy files for sharing:**
```bash
# Copy training data to your local machine
docker compose cp trainer:/data/training/document_ner/test_data.jsonl ./test_data.jsonl

# Copy any other files you want to share
docker compose cp trainer:/data/labelstudio/exports/document_ner_export.json ./document_ner_export.json
```

---

**🚀 Ready to start? Begin with Step 1 and work through systematically. Take notes as you go, and don't hesitate to stop and ask questions if anything is unclear!**