# 🛡️ Sovereign AI Workbench

> **Fully air-gapped, enterprise-grade AI assistant built on local LLMs — zero cloud dependency.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLMs-orange.svg)](https://ollama.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-red.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🧠 What Is This?

The **Sovereign AI Workbench** is a production-ready, fully **offline AI system** designed for regulated industries (oil & gas, engineering, compliance). It routes every user request through a multi-node LangGraph pipeline, selecting the right local LLM for the job — no data leaves your machine, ever.

Built for **SIH 2026 (Smart India Hackathon) — Problem Statement PS26117**.

---

## ⚡ Architecture

```
User Request
     │
     ▼
┌─────────────┐     LangGraph Multi-Node Pipeline
│  Neuron     │ ──► Plans intent, selects model, routes to right node
│ (Orchestrator)│
└─────────────┘
     │
     ├──► 🧠 Reasoning Node     ──► phi4-mini:latest
     ├──► 💻 Coding Node        ──► qwen2.5-coder:3b  (Python sandbox)
     ├──► 📄 Document Tools     ──► granite3.2-vision:2b
     ├──► 👁️  Vision Node        ──► granite3.2-vision:2b  (OCR / P&ID / drawings)
     ├──► 🔍 RAG Node           ──► nomic-embed-text + FAISS
     ├──► 🔬 Structured Extract ──► granite3.2-vision:2b  → Pydantic schema
     ├──► ✅ Validation Node    ──► Calculation verifier + audit log
     ├──► 🧠 Memory Node        ──► Short-term + Long-term context
     └──► 🔌 Plugin Tools       ──► Engineering Unit Converter v1.0
          │
          ▼
     FastAPI SSE Server  →  Custom Web UI (http://localhost:8000)
```

### Models Running Locally (Ollama)
| Model | Purpose |
|-------|---------|
| `phi4-mini:latest` | Reasoning, summarization, Q&A |
| `qwen2.5-coder:3b` | Code generation + Python sandbox execution |
| `granite3.2-vision:2b` | Document extraction, OCR, image analysis, P&ID |
| `nomic-embed-text:latest` | Vector embeddings for RAG |

---

## ✨ Features

### 🔁 Intelligent Routing (Neuron Orchestrator)
- Automatically classifies every request and routes to the right node
- Image files (`.png`, `.jpg`, `.webp`) → always Vision
- "Write a script" + CSV → Coding (not Document pipeline)
- Equipment spreadsheet extraction → Granite document pipeline
- Physics/math/logic → Reasoning

### 💻 Python Sandbox (Coding Node)
- Generates and **executes** Python code in an isolated subprocess
- Multi-language generation: Python, JavaScript, SQL, C++, Bash
- **AST security scanner** — blocks `subprocess`, `sys`, `exec/eval`, `os.system`, `os.popen`, etc.
- `import os` allowed (for `os.path.*`); shell-escape functions blocked precisely
- `open()`, `pandas`, `numpy`, `matplotlib` all available
- Auto-retry up to 3× on execution failure with error feedback to model
- **Rich output format**: shows generated code block + execution output

### 📄 Document Processing
- PDF (native text + OCR fallback via Granite vision)
- DOCX, XLSX, PPTX, TXT, CSV
- Structured fact extraction → Pydantic `CanonicalDocument` schema
- Fields: equipment, findings, measurements, actions, relationships
- Full audit trail written to `workspace/audit.log`

### 👁️ Vision Capabilities
- OCR text extraction from images
- Engineering drawing / P&ID diagram analysis
- Table extraction from images → Excel
- General image understanding
- Supports: PNG, JPG, JPEG, WebP, BMP

### 🔌 Plugin System
- Hot-loadable plugins from `plugins/` directory
- Included: **Engineering Unit Converter v1.0** (PSI↔Bar, °C↔°F, etc.)

### 🧠 Memory
- Short-term: per-session conversation history
- Long-term: persistent memory across sessions (SQLite)
- RAG: FAISS vector store over engineering documents

### 🔒 Air-Gapped Security
- Zero external API calls
- Runs entirely on local Ollama models
- Code sandbox with AST-level security scanning
- Path traversal prevention on all file operations

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) installed and running
- ~10 GB free disk space (for models)

### 1. Pull Required Models
```bash
ollama pull phi4-mini
ollama pull qwen2.5-coder:3b
ollama pull granite3.2-vision:2b
ollama pull nomic-embed-text
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Server
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

### 4. Open the UI
Navigate to **http://localhost:8000** in your browser.

---

## 📁 Project Structure

```
Sovereign_AI_Workbench/
├── agent.py                  # LangGraph nodes + graph compilation
├── neuron.py                 # Intent router / orchestrator (Neuron)
├── server.py                 # FastAPI SSE server
├── tools.py                  # Python sandbox + file/image tools
├── execution_controller.py   # Step execution manager
├── orchestrator.py           # ExecutionController class
├── memory.py                 # Short + long-term memory
├── rag.py                    # FAISS RAG pipeline
├── model_router.py           # Model selection logic
├── schemas.py                # Pydantic CanonicalDocument schema
├── verification.py           # Calculation verifier
├── plugin_loader.py          # Plugin hot-loader
├── config.yaml               # Model configuration
├── plugins/
│   └── convert_units/        # Engineering Unit Converter plugin
├── static/
│   └── index.html            # Custom dark-themed web UI
├── workspace/
│   ├── uploads/              # User-uploaded files
│   ├── processed/            # Generated output files
│   └── audit.log             # Audit trail
├── test_suite.py             # 28 unit tests
└── hard_test_suite.py        # 22 end-to-end integration tests
```

---

## 🧪 Testing

### Unit Tests (28 tests)
```bash
python -m pytest test_suite.py -v
```

### End-to-End Hard Tests (22 tests)
```bash
# Requires server running at localhost:8000
python hard_test_suite.py
```

**Test coverage:**
- ✅ Reasoning (math, logic, technical Q&A)
- ✅ Coding (Python execution, Pandas, OOP, SQL, JS generation)
- ✅ Document extraction (PDF, DOCX, CSV, XLSX)
- ✅ Vision (OCR, P&ID, technical drawings, screenshots)
- ✅ Sandbox security (blocks os.system, subprocess, exec/eval)
- ✅ Unit conversion plugin
- ✅ Multi-step pipeline (document → extract → validate)

---

## 🔧 Configuration

Edit `config.yaml` to change models:

```yaml
reasoning: "phi4-mini:latest"
coding: "qwen2.5-coder:3b"
document: "granite3.2-vision:2b"
vision: "granite3.2-vision:2b"
embedding: "nomic-embed-text:latest"
```

---

## 📊 Bug Fix History

This project underwent a comprehensive debugging and hardening session. Key fixes:

| Bug | Fix |
|-----|-----|
| Echo-back bug (AI echoed user message instead of responding) | `neuron_node` now resets `completed_steps` with `__CLEAR__` on every new plan |
| Python sandbox blocked `open()` | Removed `open` from blocked names (isolated subprocess is safe) |
| `import os` caused `NameError` (model used it without import) | Removed `os` from `_BLOCKED_MODULES`; block only dangerous `os.*` shell functions |
| `validation_node` silently blocked on human approval → empty response | Removed approval gate; node now returns structured facts or raw extracted text |
| Structured extraction crash on malformed `\uXXXX` JSON | Added regex pre-clean before `json.loads()` |
| CSV "write a script" request diverted to document pipeline | Added `wants_code` guard in `_is_equipment_spreadsheet_request()` |
| PNG with spaces in filename routed to `document_tools` | Added image-extension shortcircuit at top of `generate_plan()` |
| Missing `document` model key in `config.yaml` | Added `document: "granite3.2-vision:2b"` |
| Duplicate imports, dead code, BOM encoding issues | Cleaned up across all 19 core files |

---

## 🏗️ Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Framework | LangGraph + LangChain |
| Local LLMs | Ollama |
| Web Server | FastAPI + Uvicorn |
| Document Processing | PyMuPDF, python-docx, openpyxl, python-pptx |
| Vector Store | FAISS |
| Code Execution | AST-secured Python subprocess sandbox |
| Database | SQLite (session memory) |
| UI | Vanilla HTML/CSS/JS (dark theme) |

---

## 👥 Team

Built for **Smart India Hackathon 2026** — Problem Statement **PS26117**

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
