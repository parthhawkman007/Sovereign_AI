"""
Sovereign AI Workbench - Enterprise Web Server
Wraps the LangGraph agent in a FastAPI app with SSE streaming, file management, 
audit logging, RAG stats, and air-gap telemetry.
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import json
import time
import asyncio
import threading
import subprocess

# Ensure working directory is workspace
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORKSPACE)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import requests
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent import workflow

app = FastAPI(title="Sovereign AI Workbench", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent in-memory checkpointer
memory = MemorySaver()
agent_app = workflow.compile(checkpointer=memory)
current_session_id = "default_session"

OUTPUT_EXTS = (".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".csv")

def get_output_files():
    files = []
    for fname in os.listdir(WORKSPACE):
        if fname.endswith(OUTPUT_EXTS) and not fname.startswith("trace."):
            fp = os.path.join(WORKSPACE, fname)
            try:
                stat = os.stat(fp)
                ext = fname.split('.')[-1].lower()
                files.append({
                    "name": fname,
                    "ext": ext,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    "timestamp": stat.st_mtime
                })
            except Exception:
                pass
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return files

def get_active_connections():
    """
    Returns only ESTABLISHED connections to external (non-loopback) addresses.
    Filters out 127.0.0.1, ::1, and port 8000.
    """
    LOOPBACK = ("127.0.0.1", "::1", "[::1]", "0.0.0.0")
    try:
        result = subprocess.run(["netstat", "-n"], capture_output=True, text=True)
        external = set()
        for line in result.stdout.split("\n"):
            if "ESTABLISHED" not in line:
                continue
            if any(lb in line for lb in LOOPBACK):
                continue
            if ":8000" in line:
                continue
            external.add(line.strip())
        return external
    except Exception:
        return set()

@app.get("/health")
def health():
    """Ping Ollama and return configured + loaded models."""
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=3)
        if res.status_code == 200:
            installed = [m["name"] for m in res.json().get("models", [])]
            return {
                "status": "ok",
                "air_gapped": True,
                "models": installed,
                "active_reasoning": "phi4-mini",
                "active_coding": "qwen2.5-coder:3b",
                "active_vision": "gemma3:4b",
                "active_embedding": "nomic-embed-text"
            }
    except Exception as e:
        return {"status": "error", "models": [], "detail": str(e), "air_gapped": True}
    return {"status": "error", "models": [], "air_gapped": True}

@app.get("/files")
def list_files():
    return get_output_files()

@app.get("/download/{filename}")
def download_file(filename: str):
    # Security check: disallow directory traversal
    clean_name = os.path.basename(filename)
    fp = os.path.join(WORKSPACE, clean_name)
    if os.path.exists(fp) and clean_name.endswith(OUTPUT_EXTS):
        return FileResponse(fp, filename=clean_name)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    clean_name = os.path.basename(file.filename)
    dest = os.path.join(WORKSPACE, clean_name)
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {
        "filename": clean_name,
        "size_kb": round(len(content)/1024, 1),
        "message": f"Saved as {clean_name}"
    }

@app.get("/audit")
def get_audit_logs():
    audit_file = os.path.join(WORKSPACE, "audit.log")
    logs = []
    if os.path.exists(audit_file):
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # grab last 50 lines
                logs = [l.strip() for l in lines[-50:] if l.strip()]
        except Exception:
            pass
    return {"logs": logs}

@app.get("/sops")
def get_sops():
    sops = []
    domains = ["engineering", "commercial", "compliance"]
    for domain in domains:
        sops_dir = os.path.join(WORKSPACE, f"data_{domain}")
        if os.path.exists(sops_dir):
            for f in os.listdir(sops_dir):
                fp = os.path.join(sops_dir, f)
                if os.path.isfile(fp):
                    stat = os.stat(fp)
                    sops.append({
                        "name": f,
                        "domain": domain,
                        "size_kb": round(stat.st_size/1024, 1),
                        "indexed": True
                    })
    return {"sops": sops}

@app.post("/reset-session")
def reset_session():
    global current_session_id
    current_session_id = f"session_{int(time.time())}"
    return {"status": "ok", "session_id": current_session_id}

@app.get("/chat")
async def chat_stream(message: str = Query(...)):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    agent_config = {"configurable": {"thread_id": current_session_id}}

    def run_agent():
        try:
            net_before = get_active_connections()
            t_start = time.time()
            initial_state = {"messages": [HumanMessage(content=message)]}
            nodes_executed = []

            for event in agent_app.stream(initial_state, config=agent_config):
                for node_name in event:
                    nodes_executed.append(node_name)
                    asyncio.run_coroutine_threadsafe(
                        queue.put({"type": "step", "node": node_name, "time": time.time() - t_start}),
                        loop,
                    )

            latency = round(time.time() - t_start, 2)
            net_after = get_active_connections()
            diff = net_after - net_before
            air_gapped = len(diff) == 0

            final_state = agent_app.get_state(agent_config).values
            msgs = final_state.get("messages", [])
            result_text = msgs[-1].content if msgs else "Task completed."

            # Log to audit.log
            with open("audit.log", "a", encoding="utf-8") as f:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] USER: {current_session_id} | INPUT: {message}\n")
                f.write(f"[{ts}] LATENCY: {latency:.2f}s | TOOLS: {','.join(nodes_executed)}\n")
                f.write("-" * 40 + "\n")

            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "type": "result",
                    "text": result_text,
                    "latency": latency,
                    "nodes": nodes_executed,
                    "air_gapped": air_gapped,
                    "files": get_output_files(),
                }),
                loop,
            )

        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "text": str(exc)}),
                loop,
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    async def generate():
        while True:
            item = await queue.get()
            if item is None:
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

os.makedirs(os.path.join(WORKSPACE, "static"), exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

@app.post("/resume")
def resume_agent():
    # Resume after HITL interrupt
    agent_config = {"configurable": {"thread_id": current_session_id}}
    agent_app.update_state(agent_config, {"messages": [HumanMessage(content="User confirmed. Proceed.")]})
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    from watcher import start_watcher
    start_watcher()
    print("=" * 60)
    print("  [+] Sovereign AI Workbench - Enterprise Web Server Ready")
    print("  [+] Access at: http://localhost:8000")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)