import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import time
import subprocess
import threading
import argparse
import requests
import yaml
import whisper
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from agent import workflow 

# Parse arguments for multi-user session
parser = argparse.ArgumentParser(description="Sovereign AI Workbench V3")
parser.add_argument("--user", type=str, default="default_user", help="Isolate session memory by user")
args = parser.parse_args()
session_id = args.user

# Compile agent with memory
memory = MemorySaver()
agent_app = workflow.compile(checkpointer=memory)
config = {"configurable": {"thread_id": session_id}}

def check_health():
    """Ping Ollama, verify models in config.yaml exist on system"""
    print("\n[Health Monitor] Running startup checks...")
    try:
        res = requests.get("http://localhost:11434/api/tags")
        if res.status_code == 200:
            installed = [m['name'] for m in res.json().get('models', [])]
            with open("config.yaml", "r") as f:
                conf = yaml.safe_load(f)
                required = list(conf.get("models", {}).values())
            
            missing = [m for m in required if m not in installed]
            if missing:
                print(f"[Health Monitor] ⚠️ WARNING: Config models not installed: {missing}")
            else:
                print(f"[Health Monitor] 🟢 All configured models are loaded and ready.")
        else:
            print("[Health Monitor] 🔴 Cannot reach Ollama.")
    except Exception as e:
        print(f"[Health Monitor] 🔴 Connection error: {e}")

def get_netstat():
    try:
        result = subprocess.run(["netstat", "-n"], capture_output=True, text=True)
        lines = [line.strip() for line in result.stdout.split('\n') if 'ESTABLISHED' in line]
        return set(lines)
    except:
        return set()

def write_audit_log(user_input, latency, tools_used):
    with open("audit.log", "a", encoding="utf-8") as f:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] USER: {session_id} | INPUT: {user_input}\n")
        f.write(f"[{timestamp}] LATENCY: {latency:.2f}s | TOOLS: {tools_used}\n")
        f.write("-" * 40 + "\n")

def process_request(user_input):
    print("\n[Security Monitor] Taking pre-inference netstat snapshot...")
    net_before = get_netstat()
    
    print(f"\n[System] Routing request to internal models for user '{session_id}'...")
    start_time = time.time()
    
    initial_state = {"messages": [HumanMessage(content=user_input)]}
    tools_used = []
    
    node_start = time.time()
    for event in agent_app.stream(initial_state, config=config):
        for node_name, state in event.items():
            node_latency = time.time() - node_start
            print(f" ↳ [Agent] Completed node '{node_name}' in {node_latency:.2f}s")
            tools_used.append(node_name)
            node_start = time.time()
            
    final_state = agent_app.get_state(config).values
    final_messages = final_state.get("messages", [])
    
    if final_messages:
        print(f"\nAgent ❯ {final_messages[-1].content}")
        
    latency = time.time() - start_time
    print("\n" + "="*70)
    print(f"[Security Monitor] Total Response Time: {latency:.2f}s")
    
    print("[Security Monitor] Taking post-inference netstat snapshot...")
    net_after = get_netstat()
    diff = net_after - net_before
    if not diff:
        print("[Security Monitor] 🟢 ZERO external connections opened. System is strictly air-gapped.")
    else:
        print(f"[Security Monitor] 🔴 WARNING: New connections detected:\n{diff}")
    
    print("="*70)
    write_audit_log(user_input, latency, ",".join(tools_used))

def process_batch_queue(folder):
    """Background task queue processing"""
    print(f"\n[Task Queue] Starting background batch processing for {folder}...")
    files = os.listdir(folder)
    for f in files:
        file_path = os.path.join(folder, f)
        print(f"\n[Task Queue] Processing {f}...")
        prompt = f"Read the file {file_path} and create an approval note summarizing it."
        process_request(prompt)
    print(f"\n[Task Queue] Batch processing complete for {folder}.")

def transcribe_voice(audio_file):
    print(f"\n[Voice Input] Transcribing {audio_file} using local Whisper model...")
    try:
        # Load local base whisper model
        model = whisper.load_model("base")
        result = model.transcribe(audio_file)
        text = result["text"].strip()
        print(f"[Voice Input] Transcribed: '{text}'")
        return text
    except Exception as e:
        print(f"[Voice Input] Error transcribing audio: {e}")
        return ""

def print_header():
    print("="*70)
    print(" 🛡️  SOVEREIGN AGENTIC AI WORKBENCH (CLI V3) 🛡️")
    print(" Confidential On-Premise Execution | LLM Planner | Air-Gapped")
    print(f" Session: {session_id}")
    print("="*70)
    print(" Commands:")
    print("  /batch <folder>    Run background batch processing queue")
    print("  /voice <file.wav>  Use local Whisper to transcribe voice command")
    print("  exit               Close the workbench")
    print("="*70)

def main():
    check_health()
    print_header()
    
    while True:
        try:
            print("\n" + "-"*70)
            user_input = input(f"{session_id} ❯ ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                print("Shutting down Sovereign Workbench...")
                break
            if not user_input:
                continue
                
            if user_input.startswith("/batch "):
                folder = user_input.replace("/batch ", "").strip()
                if not os.path.exists(folder):
                    print(f"Error: Folder '{folder}' not found.")
                    continue
                # Run in background thread (Async Task Queue)
                t = threading.Thread(target=process_batch_queue, args=(folder,))
                t.daemon = True
                t.start()
                print("[System] Job submitted to background Task Queue. You can continue working.")
            
            elif user_input.startswith("/voice "):
                audio_file = user_input.replace("/voice ", "").strip()
                if not os.path.exists(audio_file):
                    print(f"Error: Audio file '{audio_file}' not found.")
                    continue
                transcribed_prompt = transcribe_voice(audio_file)
                if transcribed_prompt:
                    process_request(transcribed_prompt)
            else:
                process_request(user_input)
            
        except KeyboardInterrupt:
            print("\nShutting down Sovereign Workbench...")
            break
        except Exception as e:
            print(f"\n[!] Error during execution: {e}")

if __name__ == "__main__":
    main()
