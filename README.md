# Sovereign AI Workbench

A powerful, 100% air-gapped AI workspace tailored for enterprise and engineering tasks. The Sovereign AI Workbench uses local models to ensure privacy, and integrates multiple domain-specific knowledge bases alongside AI-driven file generation tools.

## Features

- **100% Air-Gapped**: Runs entirely locally using Ollama.
- **AI Agent**: Intelligent agent powered by LangGraph that can chat, reason, write code, and analyze documents.
- **RAG (Retrieval-Augmented Generation)**: Domain-specific knowledge bases (Engineering, Commercial, Compliance).
- **Tooling**: Built-in tools for extracting tables from images, creating Excel reports, Word Approval Notes, and Powerpoint presentations.

## Prerequisites

Before running the Sovereign AI Workbench, you must have the following installed:

1. **Python 3.9+** (https://www.python.org/downloads/)
2. **Ollama** (https://ollama.com/)

You also need to pull the necessary models via Ollama. Open your terminal and run:

```bash
ollama run phi4-mini
ollama run qwen2.5-coder:3b
ollama run gemma3:4b
ollama run nomic-embed-text
```
*(Note: depending on the exact models configured, the system uses these local models for reasoning, coding, vision, and embeddings respectively)*

## Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/parthhawkman007/SIHPS26117.git
   cd SIHPS26117
   ```

2. **Create a Virtual Environment (Recommended)**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install Requirements**
   Run the following to install the required Python packages:
   ```bash
   pip install fastapi uvicorn requests langchain-core langchain-ollama langgraph
   ```
   *(Ensure other dependencies like `pandas`, `openpyxl`, `docx`, `pptx`, `PyMuPDF` are installed if using all features)*

## Running the System

1. Ensure Ollama is running in the background.
2. Run the main server script:
   ```bash
   python server.py
   ```
3. Open your web browser and navigate to:
   **http://localhost:8000**

## Project Structure

- `server.py`: The main FastAPI web server.
- `agent.py`: The LangGraph based AI agent definition.
- `tools.py`: A set of tools used by the AI agent (document generation, OCR, etc).
- `rag.py`: The Retrieval-Augmented Generation logic and local vector store integrations.
- `data_commercial/`, `data_compliance/`, `data_engineering/`: Folders containing SOPs and knowledge base data.
- `static/`: Frontend HTML/CSS/JS files.

Enjoy a private and powerful AI-assisted workflow!
