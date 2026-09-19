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
RUNTIME_WORKSPACE = os.path.join(WORKSPACE, "workspace")
UPLOADS_DIR = os.path.join(RUNTIME_WORKSPACE, "uploads")
PROCESSED_DIR = os.path.join(RUNTIME_WORKSPACE, "processed")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from agent import workflow

from contextlib import asynccontextmanager

last_activity_time = time.time()
inactivity_stop_event = threading.Event()
inactivity_thread = None

def monitor_inactivity(stop_event):
    global last_activity_time
    from agent import ltm_cache
    timeout = 1800 # 30 mins
    consolidation_ran = False
    
    while not stop_event.is_set():
        elapsed = time.time() - last_activity_time
        if elapsed >= timeout and not consolidation_ran:
            print("[System] 30 minutes of inactivity detected. Starting dynamic memory consolidation...")
            for sid, ltm in ltm_cache.items():
                try:
                    print(f"Consolidating memory for session {sid}...")
                    ltm.consolidate_memories()
                except Exception as e:
                    print(f"[Memory] Error during consolidation for {sid}: {e}")
            consolidation_ran = True
        elif elapsed < timeout:
            consolidation_ran = False
        time.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    from watcher import start_watcher
    app.state.observer = start_watcher()
    
    global inactivity_thread, inactivity_stop_event
    inactivity_thread = threading.Thread(target=monitor_inactivity, args=(inactivity_stop_event,), daemon=True)
    inactivity_thread.start()
    
    print("=" * 60)
    print("  [+] Sovereign AI Workbench - Enterprise Web Server Ready")
    print("  [+] Access at: http://localhost:8000")
    print("=" * 60)
    yield
    inactivity_stop_event.set()
    if inactivity_thread:
        inactivity_thread.join()
    if hasattr(app.state, 'observer'):
        app.state.observer.stop()
        app.state.observer.join()

app = FastAPI(title="Sovereign AI Workbench", docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent in-memory checkpointer.  Deliverable creation is deliberately
# interrupted until the user confirms it in the UI.
memory = MemorySaver()
agent_app = workflow.compile(checkpointer=memory, interrupt_before=["tools"])
current_session_id = "default_session"

OUTPUT_EXTS = (".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".csv")

def get_output_files():
    files = []
    if not os.path.exists(PROCESSED_DIR): return files
    for fname in os.listdir(PROCESSED_DIR):
        if fname.endswith(OUTPUT_EXTS) and not fname.startswith("trace."):
            fp = os.path.join(PROCESSED_DIR, fname)
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

_latest_network_status = "NOT_YET_VERIFIED"
_latest_air_gapped = False

import psutil

def monitor_network(stop_event, detected_connections):
    LOOPBACK = ("127.0.0.1", "::1", "0.0.0.0", "[::1]")
    me = psutil.Process(os.getpid())
    while not stop_event.is_set():
        try:
            target_pids = {me.pid}
            for child in me.children(recursive=True):
                target_pids.add(child.pid)
            
            for p in psutil.process_iter(['pid', 'name']):
                if p.info['name'] and 'ollama' in p.info['name'].lower():
                    target_pids.add(p.info['pid'])
                    try:
                        for child in p.children(recursive=True):
                            target_pids.add(child.pid)
                    except:
                        pass
                        
            for conn in psutil.net_connections(kind='inet'):
                if conn.status != 'ESTABLISHED':
                    continue
                if conn.pid not in target_pids:
                    continue
                if not conn.raddr:
                    continue
                    
                r_ip = conn.raddr.ip
                if r_ip in LOOPBACK:
                    continue
                
                if conn.laddr and conn.laddr.port == 8000:
                    continue
                if conn.raddr.port == 8000:
                    continue
                    
                detected_connections.add(f"{r_ip}:{conn.raddr.port} (PID: {conn.pid})")
        except Exception:
            pass
        time.sleep(0.5)

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
    global _latest_air_gapped, _latest_network_status
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=3)
        if res.status_code == 200:
            installed = [m["name"] for m in res.json().get("models", [])]
            from model_router import router
            return {
                "status": "ok",
                "air_gapped": _latest_air_gapped,
                "network_status": _latest_network_status,
                "models": installed,
                "active_reasoning": router.get_reasoning_model(),
                "active_coding": router.get_coding_model(),
                "active_vision": router.get_vision_model(),
                "active_embedding": router.get_embedding_model()
            }
    except Exception as e:
        return {"status": "error", "models": [], "detail": str(e), "air_gapped": _latest_air_gapped, "network_status": _latest_network_status}
    return {"status": "error", "models": [], "air_gapped": _latest_air_gapped, "network_status": _latest_network_status}

@app.get("/files")
def list_files():
    return get_output_files()

@app.get("/download/{filename}")
def download_file(filename: str):
    # Security check: disallow directory traversal
    clean_name = os.path.basename(filename)
    fp = os.path.join(PROCESSED_DIR, clean_name)
    if os.path.exists(fp) and clean_name.endswith(OUTPUT_EXTS):
        return FileResponse(fp, filename=clean_name)
    raise HTTPException(status_code=404, detail="File not found")

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    clean_name = os.path.basename(file.filename)
    dest = os.path.join(UPLOADS_DIR, clean_name)
    content = await file.read()
    def _write_file():
        with open(dest, "wb") as f:
            f.write(content)
    await asyncio.to_thread(_write_file)
    return {
        "filename": clean_name,
        "size_kb": round(len(content)/1024, 1),
        "message": f"Saved as {clean_name}"
    }

@app.get("/audit")
def get_audit_logs():
    import json
    audit_file = os.path.join(RUNTIME_WORKSPACE, "audit.log")
    logs = []
    if os.path.exists(audit_file):
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                # grab last 50 lines and try to parse JSON
                for line in lines[-50:]:
                    try:
                        logs.append(json.loads(line))
                    except json.JSONDecodeError:
                        logs.append({"type": "legacy_log", "content": line})
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
    import uuid
    return {"status": "ok", "session_id": f"session_{uuid.uuid4().hex[:8]}"}

@app.post("/cancel")
def cancel_pending_operation():
    """Discard a paused graph so a later chat cannot execute it accidentally."""
    import uuid
    return {"status": "ok", "session_id": f"session_{uuid.uuid4().hex[:8]}"}

@app.get("/chat")
async def chat_stream(message: str = Query(...), session_id: str = Query(default=None)):
    global last_activity_time
    last_activity_time = time.time()
    import uuid
    active_session = session_id or str(uuid.uuid4())
    return _agent_stream({"messages": [HumanMessage(content=message)]}, message, session_id=active_session)


def _agent_stream(initial_state, audit_input: str, session_id: str = None):
    import uuid
    active_session = session_id or f"session_{uuid.uuid4().hex[:8]}"
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    agent_config = {"configurable": {"thread_id": active_session}}

    abort_event = threading.Event()
    def run_agent():
        try:
            files_before = {f["name"]: f["timestamp"] for f in get_output_files()}
            stop_event = threading.Event()
            detected_connections = set()
            monitor_thread = threading.Thread(target=monitor_network, args=(stop_event, detected_connections), daemon=True)
            monitor_thread.start()
            
            t_start = time.time()
            nodes_executed = []

            for event in agent_app.stream(initial_state, config=agent_config):
                if abort_event.is_set():
                    print(f"[{active_session}] Client disconnected. Aborting graph execution.")
                    break

                for node_name, state_update in event.items():
                    nodes_executed.append(node_name)
                    
                    step_data = {"type": "step", "node": node_name, "time": round(time.time() - t_start, 2)}
                    if node_name == "neuron":
                        step_data["sentiment"] = state_update.get("sentiment", "casual")
                        step_data["selected_model"] = state_update.get("selected_model", "")
                        step_data["filler_message"] = state_update.get("filler_message", "Musing over possibilities and honoring constraints…")
                        
                    asyncio.run_coroutine_threadsafe(
                        queue.put(step_data),
                        loop,
                    )

            latency = round(time.time() - t_start, 2)
            stop_event.set()
            monitor_thread.join(timeout=1.0)
            
            air_gapped = len(detected_connections) == 0
            global _latest_air_gapped, _latest_network_status
            _latest_air_gapped = air_gapped
            _latest_network_status = "VERIFIED_LOCAL_ONLY" if air_gapped else "EXTERNAL_CONNECTIONS_DETECTED"

            final_state = agent_app.get_state(agent_config).values
            msgs = final_state.get("messages", [])

            # Detect HITL interrupt: the graph paused before the "tools" node.
            pending_next = agent_app.get_state(agent_config).next or []
            is_hitl = "tools" in pending_next

            if is_hitl:
                # Construct canonical preview
                val_status = final_state.get("validation_status", "PENDING")
                app_state = final_state.get("approval_state", "PENDING HUMAN REVIEW")
                canonical = final_state.get("canonical_document", {})

                preview_lines = []
                preview_lines.append(f"### CANONICAL STRUCTURED FACTS")
                preview_lines.append(f"**Validation Status**: {val_status}")
                preview_lines.append(f"**Approval State**: {app_state}")
                preview_lines.append("---")

                if val_status in ("FAIL", "EXTRACTION_FAILED", "INSUFFICIENT_EVIDENCE", "ARTIFACT_QA_FAILED"):
                    preview_lines.append(f"**WARNING:** Validation failed ({val_status}). Artifact generation is blocked until issues are resolved.")
                else:
                    if canonical.get("findings"):
                        preview_lines.append("**Findings:**")
                        for f in canonical.get("findings", []):
                            preview_lines.append(f"- **{f.get('id', '')}**: {f.get('description', '')} (Target: {f.get('target', '')}) [Evidence: {f.get('provenance', {}).get('evidence', '')}]")
                    if canonical.get("measurements"):
                        preview_lines.append("\n**Measurements:**")
                        for m in canonical.get("measurements", []):
                            preview_lines.append(f"- {m.get('target', '')} = {m.get('raw_value', '')} [Evidence: {m.get('provenance', {}).get('evidence', '')}]")
                    if canonical.get("actions"):
                        preview_lines.append("\n**Actions:**")
                        for a in canonical.get("actions", []):
                            preview_lines.append(f"- **{a.get('id', '')}**: {a.get('description', '')} (Fixes: {a.get('finding_id', '')}) [Evidence: {a.get('provenance', {}).get('evidence', '')}]")
                    if not canonical.get("findings") and not canonical.get("measurements") and not canonical.get("actions"):
                        preview_lines.append("No canonical data extracted.")

                preview = "\n".join(preview_lines)
                asyncio.run_coroutine_threadsafe(
                    queue.put({
                        "type": "hitl_pause",
                        "preview": preview,
                        "latency": latency,
                        "nodes": nodes_executed,
                        "air_gapped": air_gapped,
                    }),
                    loop,
                )
                import json
                with open(os.path.join(RUNTIME_WORKSPACE, "audit.log"), "a", encoding="utf-8") as f:
                    log_entry = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "session_id": current_session_id,
                        "type": "HITL_PAUSE",
                        "input": audit_input
                    }
                    f.write(json.dumps(log_entry) + "\n")
            else:
                last_msg = msgs[-1] if msgs else None
                result_text = last_msg.content if last_msg else "Task completed."
                if isinstance(result_text, str):
                    import re
                    result_text = re.sub(r'<response>', '', result_text, flags=re.IGNORECASE)
                    result_text = re.sub(r'</response>', '', result_text, flags=re.IGNORECASE)
                    result_text = result_text.strip()

                # Only return files created/modified during this execution
                current_files = get_output_files()
                new_files = [f for f in current_files if f["name"] not in files_before or f["timestamp"] > files_before[f["name"]]]

                # Log to audit.log in structured JSON format
                import json
                with open(os.path.join(RUNTIME_WORKSPACE, "audit.log"), "a", encoding="utf-8") as f:
                    log_entry = {
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "session_id": current_session_id,
                        "type": "USER_INTERACTION",
                        "input": audit_input,
                        "latency_s": round(latency, 2),
                        "nodes_executed": nodes_executed,
                        "air_gapped": air_gapped
                    }
                    f.write(json.dumps(log_entry) + "\n")

                asyncio.run_coroutine_threadsafe(
                    queue.put({
                        "type": "result",
                        "text": result_text,
                        "latency": latency,
                        "nodes": nodes_executed,
                        "air_gapped": air_gapped,
                        "new_files": new_files,
                        "files": new_files,
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
        try:
            while True:
                item = await queue.get()
                if item is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(item)}\n\n"
        except asyncio.CancelledError:
            print(f"[{active_session}] SSE stream cancelled by client.")
            abort_event.set()
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/resume")
async def resume_agent(session_id: str = Query(default=None)):
    """Continue the paused deliverable step without adding a fake user message."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required to resume.")
    agent_config = {"configurable": {"thread_id": session_id}}
    pending_next = agent_app.get_state(agent_config).next or ()
    if "tools" not in pending_next:
        raise HTTPException(status_code=409, detail="There is no pending operation to resume.")
    return _agent_stream(None, "User confirmed pending operation", session_id=session_id)

os.makedirs(os.path.join(WORKSPACE, "static"), exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Using the string reference "server:app" is more stable for uvicorn in VSCode terminals
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, workers=1)
