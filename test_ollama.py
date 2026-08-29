import requests
import json
import time

OLLAMA_API = "http://localhost:11434/api/generate"

def query_model(model_name, prompt):
    print(f"\n[{model_name}] Processing...")
    start = time.time()
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_API, json=payload)
        response.raise_for_status()
        
        result = response.json()['response'].strip()
        latency = time.time() - start
        
        print(f"Response: {result}")
        print(f"⏱️ Time taken: {latency:.2f} seconds")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to Ollama. Make sure the Ollama app is running!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=== Sovereign AI: Local Model Router Test ===")
    print("Testing connection to local Ollama server...")
    
    # Test 1: General reasoning
    query_model("qwen2.5:3b", "What is the primary benefit of an air-gapped network?")
    
    # Test 2: Coding (force switch)
    query_model("qwen2.5-coder:1.5b", "Write a python function to print hello world")
