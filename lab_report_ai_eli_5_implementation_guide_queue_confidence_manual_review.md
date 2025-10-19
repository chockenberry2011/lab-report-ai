# Goal

Build a **local, Dockerized** learning system on your M1 Mac that parses lab report PDFs like a human:

- Extracts text + layout.
- Classifies each **line role** (patient/specimen header, panel header, test row, comments, page header/footer, junk).
- Pulls fields **within the correct role** (e.g., TEST\_NAME | VALUE | UNIT | REF\_RANGE | FLAG only inside a test row).
- **Groups** tests into panels with a **document memory** that survives page breaks (two‑pass composer).
- Emits a JSON ready for EHR import.
- Computes a **confidence score**; items below threshold are flagged **Needs Review** in the SPA.
- SPA supports **manual correction** and saving **human‑corrected JSON** that can be fed back to training.
- Background **queue/worker** so large PDFs don’t block the API (single‑concurrency worker for MacBook).
- Optional orchestration with **Airflow** for scheduled processing + retraining.

No code appears here; you’ll have **Claude** generate 100% of the code/config from the prompts below.

---

## 0) One‑time installs (ELI5)

1. **Open Terminal** (Spotlight → type "Terminal").
2. Install **Homebrew** (if you don’t have it):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. Install **Docker Desktop** (Apple Silicon):
   ```bash
   brew install --cask docker
   ```
   - Open **Docker.app** from Applications; wait until it finishes initializing (whale icon steady).
4. Install **Node.js LTS** and **Python 3.11**:
   ```bash
   brew install node
   brew install python@3.11
   ```
5. Install **Tesseract OCR** (for scanned PDFs):
   ```bash
   brew install tesseract
   ```
6. Install **Claude Code CLI** and log in with your Claude Pro plan (no API key):
   ```bash
   npm i -g @anthropic-ai/claude-code
   claude
   ```
   - Follow the browser link; sign in; return to terminal once it says you’re logged in.
7. Install **Claude Code** JetBrains plugin:
   - Open **Rider** (for C#) or **IntelliJ IDEA** (for Java) → **Settings → Plugins → Marketplace** → search **“Claude Code [Beta]”** → **Install** → restart IDE.

> We’ll keep everything local for PHI safety; all models/tools we use are free.

---

## 1) Project folders

```bash
mkdir -p ~/lab-ai/{data/{inbox,outbox,labelstudio,expected,training},models,ui,orchestrator,services/{extractor,trainer,api,worker}} && cd ~/lab-ai
```

- `data/inbox`  → drop PDFs here.
- `data/outbox` → parsed JSON appears here.
- `data/expected` → optional human/golden JSONs for compare.
- `data/training` → Label Studio exports + converted datasets.
- `models` → saved NER and other models.

---

## 2) High-level architecture (what will be generated)

- **redis**: lightweight queue broker.
- **api**: FastAPI for `POST /jobs` and `GET /results/{id}`; enqueue work.
- **worker**: consumes queue jobs; runs extractor → line roles → field taggers → composer → confidence → JSON to outbox.
- **extractor**: library container (pdfminer + Tesseract); also a CLI for debugging.
- **trainer**: training + evaluation for line-role classifier and within-line test-row tagger.
- **ui**: Vite React SPA for dashboard, viewer, manual review editor, and “commit corrected JSON to golden set”.
- **labelstudio**: labeling UI to create small training sets quickly.
- **airflow** (optional): scheduler for nightly processing and weekly retraining.

All wired together by **docker-compose** with Apple Silicon–friendly images.

---

## 3) Paste‑to‑Claude prompts (scaffold + services)

Open Terminal in `~/lab-ai`, run `claude`. Paste each prompt **one at a time**.

### A) Monorepo + docker compose

> Create a Docker-first monorepo in the current folder with services: `redis`, `api`, `worker`, `extractor`, `trainer`, `ui`, `labelstudio`, and optional `airflow`. Use Apple Silicon compatible images. Mount volumes: `./data:/data` and `./models:/models`. Provide a top-level `docker-compose.yml`, Makefile targets (`make up`, `make down`, `make build`). Do **not** include secrets. Add a root `README.md` with step-by-step run instructions for Mac.

### B) Extractor (text + layout + header/footer hints)

> In `services/extractor`: implement a Python package + Dockerfile that:
>
> - Uses `pdfminer.six` to extract per-page **lines** with: `page`, `text`, `xLeft`, `xRight`, `yNorm (0..1)`, `fontSize`, `isBold` (best-effort), `hasText`.
> - If a page has near-zero text, render to image and run **Tesseract OCR**; merge into the same line format.
> - Add `headers.py` that marks repeating **PAGE\_HEADER/FOOTER** lines by clustering top/bottom 10% lines across pages (normalized text, shingle similarity ≥ 0.85).
> - CLI: `extract_text <pdf>` → prints raw text; `extract_lines <pdf>` → writes `/data/outbox/<file>.lines.json`.
> - Include unit tests with synthetic multi-page docs.

### C) Line‑role classifier

> In `services/trainer/roles`: create code to train/evaluate a **line-role classifier** with roles: `PAGE_HEADER`, `PAGE_FOOTER`, `HEADER_PATIENT`, `HEADER_SPECIMEN`, `SECTION_PANEL`, `TEST_ROW`, `COMMENT`, `SECTION_MISC`, `JUNK`. Features: line text + `y tertile` + `isBold` + `isHeaderHint`. Use a small model (e.g., logistic regression over sentence embeddings or a tiny transformer). Provide scripts: `prep_roles.py` (from Label Studio export), `train_roles.py`, `eval_roles.py`. Save model to `/models/roles/`.

### D) Test‑row within‑line tagger

> In `services/trainer/testrow`: implement a within-line **token classification** micro‑NER for lines known to be `TEST_ROW`, with labels: `TEST_NAME`, `VALUE`, `UNIT`, `REF_RANGE`, `FLAG`. Handle subword alignment and class imbalance (penalize `O`). Scripts: `prep_testrow.py` (from Label Studio export), `train_testrow.py`, `eval_testrow.py`. Save to `/models/testrow/`. Provide a fallback rule-assisted splitter.

### E) Patient/specimen field pickers

> Add `services/trainer/headers`: scoped extractors for header roles:
>
> - From `HEADER_PATIENT`: `PATIENT_NAME`, `SEX` (if present).
> - From `HEADER_SPECIMEN`: `SPECIMEN_NUMBER`, `DATE_COLLECTED`, `DATE_RECEIVED`, `DATE_ENTERED`, `DATE_REPORTED`. Use date parsing and small lexicons; expose as a library used by the worker.

### F) Composer (pagination-aware, two-pass)

> In `services/worker/composer`: implement a composer that walks lines top-down and maintains `current_panel {id, name, started_at_page, continuity_score, open}`; honors `PAGE_HEADER/FOOTER` quarantine; opens a panel on `SECTION_PANEL`; attaches subsequent `TEST_ROW`s; at page break, if no new panel header within first N lines, continue the open panel. Add a **second pass** that repairs page-break attachments using a cost function (minimize panel switches; prefer coherent units/ref-range patterns). Output a clean EHR-ready JSON schema.

### G) Confidence + abstention

> Add a scoring module: each field gets a confidence (VALUE numeric parse success, UNIT in whitelist, REF\_RANGE well-formed, panel continuity, classifier probabilities). Compute a per-panel and per-document score. If critical fields fall below threshold, set `needsReview = true` and add a `reasons[]` array. Persist confidences in the final JSON.

### H) API + queue + worker

> Add `services/api` (FastAPI) with endpoints:
>
> - `POST /jobs` (multipart PDF upload or `pdf_url`) → returns `job_id`.
> - `GET /jobs/{id}` → status + link to result JSON if done.
> - `GET /results/{id}` → returns final JSON. The API enqueues jobs in **Redis**. Add `services/worker` (Python) that consumes jobs (use RQ or Celery with Redis). Set worker **concurrency=1** by default. Worker pipeline: extractor → roles → headers/specimen/patient → testrow tagger → composer → confidence → write `/data/outbox/<job_id>.json`.

### I) UI (Vite React) with manual review

> In `ui` create a SPA with pages:
>
> - **Inbox**: upload PDF → calls `POST /jobs`.
> - **Queue**: shows jobs pending/processing/done.
> - **Processed**: list JSON results (search/filter by flags & low confidence).
> - **Viewer**: left panel shows extracted text (and page thumbnails); right panel shows hierarchical JSON (patient/specimen → panels → tests). **Highlight low-confidence fields**.
> - **Manual Review**: editable form/table for any panel/test; buttons: **Save Correction** (writes to `/data/expected/<job_id>.json`) and **“Add to Training”** (stores per-line annotations derived from edits to `/data/training/pending/`). Provide `npm run dev` for local dev and a Dockerfile for production serve.

### J) Label Studio setup + converters

> Add a `labelstudio` service to `docker-compose` bound to `/data/labelstudio`. Provide a script/notebook: `ls_roles_quickstart.ipynb` showing how to: start Label Studio, create a project with **line-role labeling**, import `*.lines.json` files, label \~30–60 lines, export JSON. Provide converters: `ls_roles_to_csv.py` and `ls_testrow_to_ner.py` for roles and test-row tagging respectively.

### K) Airflow (optional)

> Add an `orchestrator/airflow` folder and compose services (Postgres, Redis, Scheduler, Webserver, Workers). Create a DAG `lab_pipeline.py` with tasks: `scan_inbox` (list PDFs), `enqueue_jobs` (API calls), `weekly_train_roles`, `weekly_train_testrow`, `evaluate_models`, `archive_outputs`. Document ARM/M1 run steps in README.

### L) Golden set + Compare view

> Add a small `compare` page in the UI where I can load `/data/expected/<job>.json` side-by-side with `/data/outbox/<job>.json`, with a diff viewer and a **“promote corrections to golden”** button.

---

## 4) Start the stack (ELI5)

1. In Terminal (inside `~/lab-ai`):
   ```bash
   make build
   make up
   ```
2. Wait for logs to settle. You should have:
   - API at [http://localhost:8000/docs](http://localhost:8000/docs)
   - UI at the printed dev URL (or container port; Claude’s README will say)
   - Label Studio at [http://localhost:8080](http://localhost:8080) (if enabled)

---

## 5) First run with your four PDFs (no training yet)

1. Download the four PDFs (TSH 004259, Glucose 001032, CMP 322000, CBC 005009) to your Mac.
2. Move them into `~/lab-ai/data/inbox/` (drag & drop in Finder).
3. In the UI → **Queue**, you should see jobs appear (the API enqueues automatically or via “Upload”).
4. When done, open **Processed** → click a file → **Viewer**. Inspect patient/specimen/panels/tests.
5. Click **Manual Review** if something looks off → edit → **Save Correction**.
6. Optional: click **Add to Training** for tricky lines (this will create a pending annotation pack under `/data/training/pending/`).

---

## 6) Label Studio — create a tiny training set (ELI5)

1. In a browser, open [**http://localhost:8080**](http://localhost:8080) → Sign up (any email/pa





