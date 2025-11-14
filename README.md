# Lab AI - Intelligent Laboratory Report Processing System

> A microservices-based ML platform for automatically extracting, structuring, and validating medical laboratory report data from PDF documents with human-in-the-loop corrections and active learning.

![Status: Learning Project](https://img.shields.io/badge/Status-Learning%20Project-yellow)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Not Production Ready](https://img.shields.io/badge/Production-NOT%20READY-red)

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react&logoColor=black)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

---

## ⚠️ IMPORTANT DISCLAIMER

**This is a learning/proof-of-concept project created for educational purposes.**

- ❌ **NOT production-ready** - Missing critical features like authentication, proper error handling, and security hardening
- ❌ **NOT HIPAA compliant** - Do not use with real patient data or PHI
- ❌ **NOT actively maintained** - Created as a learning exercise to explore ML, microservices, and full-stack development
- ❌ **NO WARRANTY** - Use at your own risk (see [LICENSE](LICENSE))
- ✅ **Educational use only** - Great for learning Docker, ML pipelines, React, FastAPI, and system architecture
- ✅ **Portfolio/demonstration** - Showcases integration of multiple technologies in a realistic scenario

**If you plan to use this in any production capacity, you will need significant additional development, security review, and compliance work.**

---

## 📋 Table of Contents

- [Overview](#overview)
- [What I Learned](#what-i-learned)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Known Limitations](#known-limitations)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [Training ML Models](#training-ml-models)
- [Development](#development)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

**Lab AI is a learning project** that explores building an end-to-end ML platform for extracting structured data from PDF laboratory reports. Created as a proof-of-concept to learn Python ML libraries, React, microservices architecture, and Docker orchestration.

### The Problem (Educational Scenario)

- Medical laboratories generate millions of PDF reports daily
- Manual data entry is slow, expensive, and error-prone
- Unstructured PDFs make data analysis difficult
- Vendors use different formats, requiring custom parsers

### The Solution (Proof of Concept)

This POC demonstrates:
- **Automated extraction** using custom-trained ML models (scikit-learn, CRF)
- **Intelligent document understanding** via multi-stage NLP pipeline
- **Human-in-the-loop corrections** for error refinement
- **Active learning** to continuously improve accuracy
- **Vendor-agnostic** approach (designed for, but limited testing)

### Potential Use Cases (If Fully Developed)

- **Electronic Health Records (EHR) Integration** - Ingest lab results automatically
- **Clinical Research** - Extract data from historical reports
- **Lab Information Systems (LIS)** - Migrate data between systems
- **Healthcare Analytics** - Structure unstructured lab data
- **Telemedicine Platforms** - Process lab uploads from patients

**Note**: This implementation only scratches the surface of what would be needed for production use.

## 📚 What I Learned

Building this project was an educational journey covering multiple technologies and concepts:

### Machine Learning
- **Supervised Learning**: Trained line role classifiers using scikit-learn
- **Named Entity Recognition (NER)**: Used Conditional Random Fields (CRF) for extracting test row entities
- **Active Learning**: Implemented human-in-the-loop workflow for continuous improvement
- **Label Studio**: Integrated annotation platform for training data creation
- **Model Training Pipeline**: Built end-to-end training workflow from raw data to deployed models

### Backend Development
- **FastAPI**: Built RESTful APIs with automatic OpenAPI documentation
- **Celery**: Implemented distributed task queues for background processing
- **Redis**: Used as message broker and caching layer
- **Python Services**: Created multiple microservices with clear separation of concerns
- **PDF Processing**: Extracted text and metadata using PyMuPDF

### Frontend Development
- **React 18**: Modern component-based UI with hooks
- **Vite**: Fast build tooling and hot module replacement
- **TanStack Query**: Efficient data fetching and caching
- **PDF.js**: In-browser PDF rendering
- **Tailwind CSS**: Utility-first styling

### DevOps & Architecture
- **Docker & Docker Compose**: Multi-container orchestration
- **Microservices Architecture**: Service isolation and communication
- **Message Queues**: Asynchronous job processing
- **File-based Storage**: Simple persistence for POC
- **API Design**: RESTful conventions and JSONPath for corrections

### Domain Knowledge
- **Healthcare Data**: Understanding lab report structure (panels, test rows, reference ranges)
- **Data Quality**: Importance of corrections tracking and audit trails
- **Human-in-the-Loop**: Balancing automation with human verification

### What I'd Do Differently
- Use PostgreSQL instead of file-based storage from the start
- Implement authentication/authorization earlier
- Add comprehensive integration tests
- Use transformer-based models (BERT) for better NER accuracy
- Design for horizontal scaling from day one

## ✨ Key Features

### Core Capabilities

- 🤖 **Multi-Stage ML Pipeline**
  - Line role classification (15 categories)
  - Test row entity extraction (10 entity types)
  - Document-level field extraction

- 📄 **PDF Processing**
  - Extract text with position metadata
  - Preserve formatting (bold, font size, coordinates)
  - Multi-page document support

- 🔍 **Intelligent Extraction**
  - Panel detection (CMP, CBC, Lipid Panel, etc.)
  - Test row parsing (name, value, units, reference range, flags)
  - Header field extraction (patient info, provider, lab details)

- ✏️ **Human-in-the-Loop**
  - Interactive review interface
  - Side-by-side PDF viewer
  - JSONPath-based field editing
  - Correction history tracking

- 🎓 **Active Learning**
  - Label Studio integration for training data creation
  - Systematic error analysis
  - Continuous model improvement

- 🔄 **Production-Ready Features**
  - RESTful API with FastAPI
  - Celery-based background job processing
  - Redis message queue and caching
  - Docker containerization for easy deployment
  - Comprehensive error handling and validation

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interface (React)                        │
│   Upload PDFs → Monitor Jobs → Review Results → Submit Corrections│
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                           │
│   /upload  /jobs  /results  /corrections                        │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
           ▼                      ▼
    ┌──────────┐         ┌────────────────┐
    │  Redis   │         │  File Storage  │
    │ Queue+Cache│       │  /data /models │
    └──────┬───┘         └────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Worker (Celery Background Tasks)                    │
│                                                                  │
│   PDF → Extractor → Line Classifier → Composer → Test Row NER   │
│                         (ML Models)                              │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │  Trainer    │
    │  (Toolbox)  │
    └─────────────┘
```

**See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed system design.**

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework with automatic OpenAPI docs
- **Celery** - Distributed task queue for background job processing
- **Redis** - Message broker and caching layer
- **scikit-learn** - ML framework for line classification
- **python-crfsuite** - Conditional Random Fields for sequence labeling (NER)
- **PyMuPDF (fitz)** - Fast PDF text extraction with position data

### Frontend
- **React 18** - Modern UI library with hooks
- **Vite** - Lightning-fast build tool
- **React Router** - Client-side routing
- **TanStack Query** - Data fetching and caching
- **PDF.js** - PDF rendering in browser
- **Tailwind CSS** - Utility-first styling

### ML & Data
- **Label Studio** - Data annotation platform
- **pandas** - Data manipulation
- **numpy** - Numerical computing

### Infrastructure
- **Docker & Docker Compose** - Containerization and orchestration
- **nginx** - Reverse proxy and static file serving
- **Make** - Build automation

### Optional
- **Apache Airflow** - Workflow orchestration (for batch processing)
- **Flower** - Celery monitoring dashboard

## ⚠️ Known Limitations

This is a proof-of-concept with significant limitations:

### Security
- ❌ No authentication or authorization
- ❌ No input validation/sanitization in many places
- ❌ Default passwords in docker-compose (admin@localhost/changeme)
- ❌ No rate limiting
- ❌ No HTTPS/TLS

### Functionality
- ⚠️ **Limited vendor support** - Only tested with a handful of LabCorp samples
- ⚠️ **Low model accuracy** - Trained on minimal data (4-20 examples)
- ⚠️ **File-based storage** - Not suitable for concurrent access
- ⚠️ **No retry logic** - Failed jobs don't auto-retry
- ⚠️ **Basic error handling** - Many edge cases not covered
- ⚠️ **Single worker** - No horizontal scaling

### Compliance & Privacy
- ❌ **NOT HIPAA compliant** - No encryption, audit logs, or access controls
- ❌ **No data retention policies**
- ❌ **No audit trail** for data access
- ❌ **Corrections not validated** against schema

### Production Readiness
- ❌ No monitoring or alerting
- ❌ No backup/disaster recovery
- ❌ No load balancing
- ❌ No CI/CD pipeline
- ❌ Limited test coverage
- ❌ No performance optimization

### What Would Be Needed for Production

To make this production-ready would require:
1. Complete security overhaul (auth, encryption, input validation)
2. HIPAA compliance implementation
3. Database layer (PostgreSQL)
4. Comprehensive testing (unit, integration, E2E)
5. Monitoring and logging infrastructure
6. Horizontal scaling support
7. Model improvements (more training data, better algorithms)
8. Error handling and retry logic
9. API rate limiting and throttling
10. Documentation and compliance audits

**Estimated effort: 6-12 months of full-time development for production use**

## 📋 Prerequisites

Before you begin, ensure you have:

- **Docker Desktop** (latest version)
  - macOS: [Download for Mac](https://www.docker.com/products/docker-desktop)
  - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)
  - Windows: [Download for Windows](https://www.docker.com/products/docker-desktop) (WSL2 required)

- **Make** (usually pre-installed)
  - macOS/Linux: Already available
  - Windows: Install via [Chocolatey](https://chocolatey.org/) or WSL

- **System Resources**
  - 8GB+ RAM available for Docker
  - 10GB+ disk space
  - Multi-core CPU recommended

- **Sample Lab Reports** (see [Data Setup](#data-setup))

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/lab-ai.git
cd lab-ai
```

### 2. Initial Setup

```bash
# Create required directories and build all services
make dev-setup
```

This command will:
- Create `data/` and `models/` directories
- Build Docker images (takes 5-10 minutes first time)
- Start all services
- Initialize Label Studio

**Expected output:**
```
Services available at:
  API: http://localhost:8000
  UI: http://localhost:3000
  Label Studio: http://localhost:8080
  Redis: localhost:6379
```

### 3. Verify Services Are Running

```bash
make status
```

All services should show `Up` status.

### 4. Access the Dashboard

Open your browser to **http://localhost:3000**

You should see the Lab AI dashboard.

## 📊 Usage Guide

### Processing Your First Lab Report

#### Step 1: Obtain Sample PDFs

Lab AI requires laboratory report PDFs for processing. **LabCorp** provides excellent sample reports:

1. Visit [LabCorp.com](https://www.labcorp.com/)
2. Search for "sample lab report" or specific test types:
   - Comprehensive Metabolic Panel (CMP)
   - Complete Blood Count (CBC)
   - Lipid Panel
   - Thyroid Function Tests
3. Download PDF reports to your `data/inbox/` directory

**Example:**
```bash
# Place PDFs in the inbox directory
cp ~/Downloads/sample_cmp.pdf data/inbox/
cp ~/Downloads/sample_cbc.pdf data/inbox/
```

See [data/README.md](data/README.md) for more details on obtaining sample reports.

#### Step 2: Upload via UI

1. Navigate to http://localhost:3000
2. Click "Upload PDF" button
3. Select a lab report PDF
4. Monitor job status in the dashboard

#### Step 3: Review Results

Once processing completes:
1. Click on the result in the "Completed" queue
2. View extracted data side-by-side with PDF
3. Verify accuracy of extracted fields

#### Step 4: Submit Corrections (Optional)

If you find errors:
1. Click on any field to edit
2. Modify the value
3. Add a note explaining the correction
4. Submit to save

Corrections are logged and can be used to retrain models.

### Processing via API

```bash
# Upload a PDF
curl -X POST http://localhost:8000/upload \
  -F "file=@data/inbox/sample_report.pdf"

# Response: {"job_id": "abc-123-def-456"}

# Check job status
curl http://localhost:8000/jobs/abc-123-def-456

# Retrieve results
curl http://localhost:8000/results/abc-123-def-456.03_compose.debug

# Submit corrections
curl -X POST http://localhost:8000/results/abc-123-def-456.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "path": "lab_panels[0].test_rows[2].result_value",
      "value": "95",
      "note": "OCR error - was 85"
    }]
  }'
```

See [docs/CORRECTIONS_API.md](docs/CORRECTIONS_API.md) for full API documentation.

## 🎓 Training ML Models

Lab AI uses custom-trained ML models for extraction. Follow these steps to train your own models:

### Overview of Training Pipeline

1. **Collect PDFs** - Gather diverse lab reports
2. **Extract Lines** - Convert PDFs to line-based JSON
3. **Label Data** - Use Label Studio to annotate
4. **Train Models** - Run training scripts
5. **Evaluate** - Check model performance
6. **Deploy** - Copy models to `/models/` directory

### Phase 0: Initial Training (4 examples)

This proves the pipeline works end-to-end.

#### Step 1: Prepare Sample PDFs

```bash
# Place 4 sample PDFs in inbox
ls data/inbox/
# 001032.pdf  004259.pdf  005009.pdf  322000.pdf
```

#### Step 2: Extract Lines

```bash
# Extract lines from each PDF
for pdf in 001032 004259 005009 322000; do
  make extract-lines PDF=/data/inbox/${pdf}.pdf
done

# Verify extraction
docker compose exec trainer ls -la /data/outbox/*.lines.json
```

#### Step 3: Convert for Label Studio

```bash
# Convert to Label Studio format
docker compose exec trainer python -m services.trainer.utils.lines_to_ls \
  /data/outbox/*.lines.json \
  --output /data/labelstudio/imports/all_lines.json

# Copy to local machine for upload
docker compose cp trainer:/data/labelstudio/imports/all_lines.json ./
```

#### Step 4: Label in Label Studio

1. Navigate to http://localhost:8080 (login: admin@localhost/changeme)
2. Create project: "Line Role Classification - Phase 0"
3. Configure labeling interface (see [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md))
4. Import `all_lines.json`
5. Label ~100 lines across 4 documents
6. Export as JSON

#### Step 5: Train Line Classifier

```bash
# Copy Label Studio export to container
docker compose cp project-1-export.json trainer:/data/labelstudio/exports/roles_phase0.json

# Convert to training format
docker compose exec trainer python /app/scripts/ls_roles_to_csv.py \
  /data/labelstudio/exports/roles_phase0.json \
  --output /data/training/roles/roles_phase0.csv

# Train model
make roles.train

# Evaluate
make roles.eval
```

#### Step 6: Train Test Row NER

Similar process for test row entity extraction - see full guide.

### Comprehensive Training Guide

For complete step-by-step instructions including:
- All 15 line role categories
- 10 test row entity types
- Document NER training
- Active learning workflow
- Phase 1-3 scaling (20, 50, 100+ examples)

**See [docs/TRAINING_GUIDE.md](docs/TRAINING_GUIDE.md)**

## 💻 Development

### Common Tasks

```bash
# Start services
make up

# Stop services
make down

# View logs (all services)
make logs

# Check status
make status

# Rebuild after code changes
make rebuild

# Fresh deployment (stop, rebuild, start)
make fresh

# Clean everything (including volumes - nuclear option)
make clean
```

### Quick Reference: Key Make Commands

| Command | Description |
|---------|-------------|
| `make dev-setup` | Initial setup (creates dirs, builds, starts) |
| `make up` | Start all core services |
| `make down` | Stop all services |
| `make status` | Check service status |
| `make logs` | View logs from all services |
| `make build` | Build all Docker images |
| `make rebuild` | Rebuild from scratch (no cache) |
| `make fresh` | **Stop → Rebuild → Start** (fresh deployment) |
| `make clean` | Stop services and remove volumes |
| `make shell-api` | Open shell in API container |
| `make shell-worker` | Open shell in worker container |
| `make shell-trainer` | Open shell in trainer container |
| `make extract-lines` | Extract lines from PDF |
| `make roles.train` | Train line role classifier |
| `make roles.eval` | Evaluate line classifier |
| `make testrow.train` | Train test row NER model |
| `make testrow.eval` | Evaluate test row NER model |

### When to Use Which Command

- **`make fresh`** - Use when you've made Docker/config changes and want a clean restart
- **`make rebuild`** - Use when you've changed Dockerfiles or dependencies
- **`make up`** - Use for normal startup after `make down`
- **`make clean`** - Use when things are really broken (removes all data volumes!)

### Service-Specific Commands

```bash
# Open shell in a service
make shell-api
make shell-worker
make shell-trainer
make shell-extractor

# Restart specific service
docker compose restart worker
make api-restart  # Rebuild + restart API

# View service logs
docker compose logs -f worker
docker compose logs -f api
docker compose logs -f ui

# Build specific service
docker compose build worker
docker compose build ui
```

### Development Workflow

1. **Make code changes** in `services/` or `ui/`
2. **Rebuild** the affected service:
   ```bash
   docker compose build worker  # for Python services
   docker compose build ui      # for React frontend
   ```
3. **Restart** the service:
   ```bash
   docker compose up -d worker
   ```
4. **Test** your changes
5. **Check logs** if issues occur:
   ```bash
   docker compose logs --tail=50 worker
   ```

### Running Tests

```bash
# API tests
docker compose exec api pytest tests/

# Worker tests
docker compose exec worker pytest tests/

# UI tests (from ui directory)
cd ui && npm test

# Extractor tests
make test-extractor

# Trainer self-test
make trainer-selftest
```

### All Available Make Commands

<details>
<summary>Click to expand complete command reference</summary>

#### Core Operations
- `make help` - Show all available commands
- `make dev-setup` - Initial setup (one-time)
- `make up` - Start all services
- `make down` - Stop all services
- `make status` - Check service status
- `make logs` - View all service logs
- `make build` - Build all Docker images
- `make rebuild` - Rebuild from scratch (no cache)
- `make fresh` - Stop, rebuild, and start (fresh deployment)
- `make clean` - Stop and remove volumes (⚠️ deletes data!)

#### Service Management
- `make shell-api` - Open shell in API container
- `make shell-worker` - Open shell in worker container
- `make shell-extractor` - Open shell in extractor container
- `make shell-trainer` - Open shell in trainer container
- `make api-restart` - Rebuild and restart API
- `make worker-restart` - Restart worker

#### Airflow (Optional)
- `make up-airflow` - Start with Airflow
- `make down-airflow` - Stop Airflow services

#### PDF Processing
- `make extract-text PDF=/data/file.pdf` - Extract text from PDF
- `make extract-lines PDF=/data/file.pdf` - Extract lines with metadata
- `make reprocess.one FILE=basename` - Reprocess a single PDF

#### Model Training - Line Roles
- `make roles.train` - Train line role classifier
- `make roles.eval` - Evaluate line classifier
- `make sample-roles-data` - Generate sample training data
- `make classify-roles INPUT=/data/file.lines.json` - Apply classifier
- `make roles-sanity FILE=/data/file.lines.json` - Sanity check output

#### Model Training - Test Rows
- `make testrow.train` - Train test row NER model
- `make testrow.eval` - Evaluate test row NER model
- `make sample-testrow-data` - Generate sample test row data
- `make parse-testrow TEXT="..."` - Parse test row into tokens

#### Corrections & Data
- `make corrections.triage ID=<result_id>` - Triage corrections file
- `make corrections.normalize` - Normalize corrections
- `make corrections.apply` - Apply corrections to canonical docs

#### Testing & Debugging
- `make test-extractor` - Run extractor unit tests
- `make test-headers` - Run header extractor tests
- `make trainer-selftest` - Test trainer module imports
- `make demo-extractor` - Run extractor demo
- `make demo-headers` - Run header extraction demo
- `make debug-report` - View last processed job artifacts
- `make check-imports` - Audit import paths

#### UI Specific
- `make ui-check-lock` - Verify npm lockfile integrity
- `make ui-check-scripts` - Verify package.json scripts
- `make up-ui-verbose` - Start UI with verbose output

</details>

### Common Workflows

**First time setup:**
```bash
make dev-setup
```

**Normal development:**
```bash
make up          # Start
# ... work ...
make down        # Stop when done
```

**After changing code:**
```bash
make fresh       # Clean restart
```

**After changing dependencies:**
```bash
make rebuild     # Rebuild with new deps
make up
```

**Something broken?**
```bash
make clean       # Nuclear option - removes everything
make dev-setup   # Start fresh
```

### Debugging

**Enable debug mode:**
```bash
# In docker-compose.yml, set:
LAB_DEBUG=1  # Writes intermediate debug files
```

**Inspect intermediate outputs:**
```bash
# Check debug files
ls data/outbox/*.debug.json

# View specific stage
cat data/outbox/abc-123.02_roles.debug.json | jq '.predictions | .[:5]'
```

**Check Celery tasks:**
```bash
# Inspect worker
docker compose exec worker celery -A tasks inspect active

# View task history (if Flower is running)
open http://localhost:5555
```

## 📚 API Documentation

### Interactive API Docs

FastAPI provides automatic interactive documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload PDF and create job |
| `GET` | `/jobs/{job_id}` | Get job status |
| `GET` | `/jobs` | List all jobs |
| `GET` | `/results/{result_id}` | Get extraction results |
| `POST` | `/results/{result_id}/corrections` | Submit corrections |
| `GET` | `/stats` | System statistics |
| `GET` | `/health` | Health check |

### Example: Full Workflow

```bash
# 1. Upload PDF
RESPONSE=$(curl -s -X POST http://localhost:8000/upload \
  -F "file=@data/inbox/sample.pdf")

JOB_ID=$(echo $RESPONSE | jq -r '.job_id')
echo "Job ID: $JOB_ID"

# 2. Poll until complete
while true; do
  STATUS=$(curl -s http://localhost:8000/jobs/$JOB_ID | jq -r '.status')
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 2
done

# 3. Get results
curl -s http://localhost:8000/results/${JOB_ID}.03_compose.debug | jq '.'

# 4. Submit correction
curl -X POST http://localhost:8000/results/${JOB_ID}.03_compose.debug/corrections \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [{
      "path": "lab_panels[0].panel_name",
      "value": "COMPREHENSIVE METABOLIC PANEL"
    }]
  }'

# 5. Get corrected results
curl -s http://localhost:8000/results/${JOB_ID}.03_compose.canonical | jq '.'
```

## 📁 Project Structure

```
lab-ai/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── docker-compose.yml           # Service orchestration
├── Makefile                     # Build and dev commands
├── .gitignore                   # Git exclusions
│
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md         # System design details
│   ├── TRAINING_GUIDE.md       # ML training workflow
│   └── CORRECTIONS_API.md      # API documentation
│
├── data/                        # Runtime data (excluded from Git)
│   ├── README.md               # Data setup instructions
│   ├── inbox/                  # PDF uploads
│   ├── outbox/                 # Processing outputs
│   ├── results/                # Final structured results
│   ├── training/               # ML training data
│   └── labelstudio/            # Label Studio workspace
│
├── models/                      # Trained ML models (excluded from Git)
│   ├── roles/                  # Line classifier
│   └── testrow/                # Test row NER
│
├── services/                    # Microservices
│   ├── api/                    # FastAPI backend
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── main.py
│   │   └── routes/
│   ├── worker/                 # Celery worker
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── tasks.py
│   │   └── composer/
│   ├── extractor/              # PDF extraction
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── extract.py
│   └── trainer/                # ML training toolbox
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── roles/
│       └── testrow/
│
├── ui/                         # React frontend
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   └── public/
│
├── scripts/                    # Utility scripts
│   ├── check-lock.sh
│   └── ls_roles_to_csv.py
│
├── tests/                      # Test suite
│   ├── api/
│   ├── worker/
│   └── conftest.py
│
└── orchestrator/               # Airflow (optional)
    ├── Dockerfile
    ├── dags/
    └── config/
```

## 🔧 Troubleshooting

### Services Won't Start

```bash
# Check if ports are already in use
lsof -i :3000 -i :8000 -i :8080 -i :6379

# Kill conflicting processes or change ports in docker-compose.yml

# Clean and restart
make clean
make up
```

### Out of Memory Errors

```bash
# Check Docker stats
docker stats

# Increase memory in Docker Desktop
# Settings → Resources → Memory → 8GB+
```

### Worker Not Processing Jobs

```bash
# Check worker logs
docker compose logs worker | tail -50

# Verify Redis connection
docker compose exec worker redis-cli -h redis PING
# Should return: PONG

# Restart worker
docker compose restart worker
```

### Models Not Found

```bash
# Check models directory
ls -la models/

# Train initial models (see Training section)
make roles.train
make testrow.train

# Verify models loaded
docker compose logs worker | grep "model"
```

### UI Not Loading

```bash
# Check UI logs
docker compose logs ui

# Verify UI is running
docker compose ps ui

# Check nginx config
docker compose exec ui cat /etc/nginx/conf.d/default.conf

# Rebuild UI
docker compose build ui
docker compose up -d ui
```

### Permission Denied on Volumes

```bash
# Fix ownership (macOS/Linux)
sudo chown -R $(whoami) data/ models/

# Verify Docker has file sharing enabled
# Docker Desktop → Settings → Resources → File Sharing
```

## 🚀 Future Enhancements

### Planned Features

- [ ] **Multi-vendor Support** - LabCorp, Quest, local labs with vendor detection
- [ ] **Real-time Collaboration** - Multiple users reviewing same document
- [ ] **Transformer Models** - BERT/BioBERT for improved NER accuracy
- [ ] **Confidence Scoring** - Auto-flag low-confidence extractions for review
- [ ] **Batch Processing** - Process folders of PDFs in one operation
- [ ] **Export Formats** - FHIR, HL7 v2, CSV, Excel exports
- [ ] **Analytics Dashboard** - Model performance tracking over time
- [ ] **Webhooks** - Notify external systems on job completion
- [ ] **Authentication** - User accounts with role-based access
- [ ] **Audit Logging** - Comprehensive activity tracking for compliance

### Scalability Improvements

- [ ] Horizontal worker scaling (Kubernetes)
- [ ] PostgreSQL for metadata (replace file-based storage)
- [ ] S3/GCS for PDF storage
- [ ] GPU support for transformer inference
- [ ] Load balancing for API
- [ ] Caching layer (Redis + CDN)

### Model Enhancements

- [ ] Few-shot learning for new vendors
- [ ] Semi-supervised learning
- [ ] Active learning automation
- [ ] Model version management
- [ ] A/B testing framework

## 🤝 Contributing

This is primarily a **learning/portfolio project** and is not actively maintained. However, if you find it useful for learning:

### Learning from This Project

Feel free to:
- Fork it for your own learning
- Use it as a reference for similar projects
- Study the architecture and code patterns
- Experiment with improvements

### If You Want to Contribute

While this isn't actively maintained, suggestions are welcome:

1. **Open an issue** to discuss significant changes
2. **Fork the repository**
3. **Create a feature branch** (`git checkout -b feature/improvement`)
4. **Document your changes** clearly
5. **Open a Pull Request** with detailed explanation

**Note**: Response times may be slow as this is not an active project.

### Code Style

- **Python**: Follow PEP 8, use `black` for formatting
- **TypeScript/React**: Follow Airbnb style guide
- **Commits**: Use conventional commits (feat:, fix:, docs:, etc.)

### Better Alternatives

If you're looking for production-ready solutions, consider:
- Commercial OCR/document extraction services (AWS Textract, Google Document AI)
- Open-source alternatives with active communities
- FHIR-compliant healthcare data integration platforms

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Key Points from MIT License:**
- ✅ Free to use, modify, and distribute
- ❌ **NO WARRANTY of any kind**
- ❌ **NO LIABILITY** for damages or issues
- ✅ Must include copyright notice in distributions

**USE AT YOUR OWN RISK** - This is experimental/educational software.

## 🙏 Acknowledgments

- **Label Studio** - Excellent annotation platform for creating training data
- **FastAPI** - Modern Python web framework with great developer experience
- **LabCorp** - Sample laboratory reports available for educational purposes
- **Open Source Community** - All the amazing tools that made this learning project possible
- **Python & React Communities** - Documentation and examples that helped throughout development

## 📬 About

**Created by**: Charlie Hockenberry

**Purpose**: Learning project to explore ML pipelines, microservices, React, and full-stack development

**Status**: Educational proof-of-concept - not maintained for production use

If you found this project helpful for learning:
- ⭐ Star the repo
- 🍴 Fork it for your own experiments
- 📖 Use it as a reference for your projects

---

**Questions?** Open an issue (responses may be slow) or fork and experiment on your own!

**Warning**: Do not use this with real patient data or in production environments without significant additional development and security review.
