# Lab AI - System Architecture

## Overview

Lab AI is a microservices-based ML platform designed to automatically extract, structure, and validate medical laboratory report data from PDF documents. The system employs a human-in-the-loop workflow with active learning to continuously improve extraction accuracy.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface (React)                   │
│  - Upload PDFs      - Review Results      - Manual Corrections   │
└────────────────┬───────────────┬──────────────────┬─────────────┘
                 │               │                  │
                 ▼               ▼                  ▼
┌────────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                          │
│  - Job Management    - Results API    - Corrections Endpoint   │
└────────┬───────────────────┬──────────────────────┬────────────┘
         │                   │                      │
         ▼                   ▼                      ▼
┌────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│     Redis      │  │   File Storage    │  │  Label Studio    │
│  (Message Q)   │  │   (/data, /models)│  │  (Annotation)    │
└────────┬───────┘  └───────────────────┘  └──────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│                 Worker (Celery Background Tasks)                │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Extractor   │→ │ Line Roles   │→ │  Composer    │        │
│  │   (PDF→Text) │  │  Classifier  │  │  (Merge)     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│         │                 │                  │                 │
│         └─────────────────┴──────────────────┘                 │
│                           │                                    │
│                  ┌────────▼─────────┐                         │
│                  │  Test Row NER    │                         │
│                  │  (Field Extract) │                         │
│                  └──────────────────┘                         │
└────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────┐
│                    Trainer (ML Toolbox)                         │
│  - Model Training    - Evaluation    - Data Conversion         │
└────────────────────────────────────────────────────────────────┘
```

## Service Breakdown

### 1. **UI Service** (React + Vite)
**Purpose**: User-facing web application

**Key Features**:
- PDF upload and job submission
- Real-time job status monitoring
- Interactive results viewer with PDF side-by-side
- Manual correction interface with JSONPath editing
- Queue management (inbox, processing, completed)

**Technology**: React 18, React Router, TanStack Query, PDF.js, Tailwind CSS

**Port**: 3000

---

### 2. **API Service** (FastAPI)
**Purpose**: REST API for job orchestration and data access

**Key Endpoints**:
- `POST /upload` - Upload PDF and create job
- `GET /jobs/{job_id}` - Job status and metadata
- `GET /results/{result_id}` - Structured extraction results
- `POST /results/{result_id}/corrections` - Submit manual corrections
- `GET /stats` - System statistics

**Technology**: FastAPI, Pydantic, Celery client

**Port**: 8000

---

### 3. **Worker Service** (Celery)
**Purpose**: Background task processing for document extraction pipeline

**Main Tasks**:
1. **process_pdf_pipeline** - Orchestrates full extraction workflow
   - Calls extractor service
   - Applies line role classification
   - Runs test row NER
   - Merges results into structured format

**Processing Stages**:
- `01_lines` - Raw line extraction from PDF
- `02_roles` - Line role classification (15 categories)
- `03_compose` - Final structured output with test row NER

**Technology**: Celery, Redis backend, ML model inference

---

### 4. **Extractor Service** (Python)
**Purpose**: PDF text extraction and line detection

**Functionality**:
- Extract text lines from PDF with position metadata
- Preserve formatting (bold, font size, coordinates)
- Output JSON format for downstream processing

**Technology**: PyMuPDF (fitz), Python

---

### 5. **Trainer Service** (ML Toolbox)
**Purpose**: Model training and data preparation

**Capabilities**:
- Train line role classifier (scikit-learn)
- Train test row NER model (CRF/BERT)
- Convert Label Studio exports to training format
- Model evaluation and cross-validation

**Technology**: scikit-learn, CRF, transformers (optional), pandas

---

### 6. **Redis**
**Purpose**: Message broker and result backend for Celery

**Usage**:
- Task queue for worker
- Job status caching
- Session storage

---

### 7. **Label Studio**
**Purpose**: Data annotation platform for training data creation

**Usage**:
- Label line roles (15 categories)
- Annotate test row entities (10 entity types)
- Document-level NER for header fields
- Export annotations for model training

**Port**: 8080
**Credentials**: admin/admin (development)

---

## Data Flow

### Document Processing Pipeline

```
1. PDF Upload
   ↓
2. Job Creation (API)
   ↓
3. Celery Task Queued (Redis)
   ↓
4. Worker Picks Up Task
   ↓
5. Extractor: PDF → Lines JSON
   ↓
6. Line Classifier: Lines → Role Labels
   ↓
7. Composer: Merge into Panels
   ↓
8. Test Row NER: Extract Fields
   ↓
9. Save Results to /data/results
   ↓
10. Update Job Status (Redis)
```

### Corrections Flow

```
1. User Reviews Results (UI)
   ↓
2. User Edits Field Values
   ↓
3. POST /results/{id}/corrections
   ↓
4. API Validates JSONPath
   ↓
5. Save to corrections.jsonl
   ↓
6. Apply to Canonical Document
   ↓
7. UI Reflects Corrected Values
```

### Training Pipeline

```
1. Process PDFs → Lines JSON
   ↓
2. Import to Label Studio
   ↓
3. Human Annotation
   ↓
4. Export Labeled Data
   ↓
5. Convert to Training Format
   ↓
6. Train Models (Trainer Service)
   ↓
7. Evaluate Performance
   ↓
8. Deploy to /models/
   ↓
9. Restart Worker (Hot Reload)
```

## ML Models

### 1. Line Role Classifier
- **Type**: Multi-class classification (15 categories)
- **Algorithm**: Logistic Regression with TF-IDF
- **Input**: Single text line + positional features
- **Output**: Role label (TEST_ROW, HEADER_PATIENT_NAME, etc.)
- **Training**: Supervised learning on labeled lines

### 2. Test Row Token Classifier
- **Type**: Named Entity Recognition (10 entity types)
- **Algorithm**: CRF (Conditional Random Fields)
- **Input**: Tokenized test row line
- **Output**: BIO tags (TEST_NAME, VALUE, UNIT, etc.)
- **Training**: Sequence labeling on annotated test rows

### 3. Document NER (Future)
- **Type**: Document-level field extraction
- **Input**: Full document text or header sections
- **Output**: Structured patient/provider/lab information
- **Status**: Partially implemented, can be enhanced

## Key Design Decisions

### 1. **Microservices Architecture**
- **Why**: Separation of concerns, independent scaling, language flexibility
- **Trade-off**: More complex deployment vs monolith

### 2. **Celery for Background Processing**
- **Why**: Production-proven task queue, retry logic, monitoring
- **Alternative**: Could use FastAPI BackgroundTasks for simpler deployment

### 3. **File-Based Storage**
- **Why**: Simple, no database overhead, easy debugging
- **Trade-off**: Not ideal for high concurrency, consider PostgreSQL for production

### 4. **Label Studio Integration**
- **Why**: Industry-standard annotation tool, flexible config
- **Alternative**: Could build custom annotation UI

### 5. **CRF for Test Row NER**
- **Why**: Fast inference, interpretable, works well with limited data
- **Alternative**: Could use transformer-based models for better accuracy

## Scaling Considerations

### Current Limitations
- Single worker instance (sequential processing)
- File-based storage (no concurrent writes)
- No authentication/authorization
- Limited error recovery

### Production Improvements
1. **Horizontal Scaling**
   - Multiple worker instances
   - Load balancer for API
   - Distributed file storage (S3, GCS)

2. **Database Layer**
   - PostgreSQL for job metadata
   - Redis for caching only
   - Indexed queries for fast lookups

3. **Security**
   - JWT authentication
   - Role-based access control
   - HTTPS/TLS
   - PHI compliance (HIPAA if handling real data)

4. **Monitoring**
   - Prometheus + Grafana
   - Celery Flower for task monitoring
   - Structured logging (ELK stack)

5. **CI/CD**
   - GitHub Actions for tests
   - Docker image builds
   - Automated deployment (k8s)

## Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| Frontend | React + Vite | 18.2 / 5.x |
| API | FastAPI | 0.104+ |
| Worker | Celery | 5.x |
| Message Queue | Redis | 7.x |
| ML Framework | scikit-learn | 1.3+ |
| NER | python-crfsuite | 0.9+ |
| PDF Processing | PyMuPDF | 1.23+ |
| Annotation | Label Studio | Latest |
| Orchestration | Docker Compose | 3.8 |
| Language | Python 3.11, Node 20 | - |

## File System Layout

```
/data/
  ├── inbox/          # Uploaded PDFs
  ├── outbox/         # Intermediate outputs (*.lines.json, *.debug.json)
  ├── results/        # Final structured results
  │   └── {uuid}/
  │       ├── result.json
  │       ├── corrections.jsonl
  │       └── canonical.json (after corrections)
  ├── training/       # Training data
  │   ├── roles/
  │   └── testrow/
  └── labelstudio/    # Label Studio workspace
      ├── imports/
      └── exports/

/models/
  ├── roles/          # Line classifier models
  └── testrow/        # Test row NER models
```

## Security Considerations

### Current Status (Development)
- No authentication
- Default passwords (admin/admin)
- No encryption at rest
- No audit logging

### Production Requirements
- PHI data requires HIPAA compliance
- Encrypt data at rest and in transit
- Audit all data access
- Regular security audits
- Data retention policies

## Future Enhancements

1. **Multi-vendor Support** - Handle Quest, LabCorp, local labs
2. **Real-time Collaboration** - Multiple reviewers on same document
3. **Advanced NER** - Transformer-based models (BERT, BioBERT)
4. **Confidence Scoring** - Auto-flag low-confidence extractions
5. **Batch Processing** - Process entire folders
6. **API Webhooks** - Notify on job completion
7. **Export Formats** - FHIR, HL7, CSV
8. **Analytics Dashboard** - Model performance over time

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Label Studio](https://labelstud.io/)
- [CRF for NER](https://sklearn-crfsuite.readthedocs.io/)
