import sys
import requests
from langchain_core.messages import HumanMessage
from agent import app

def download_sample_image():
    # Download a sample engineering drawing or use a placeholder
    # For demo purposes, we'll download a simple schematic if it doesn't exist
    import os
    if not os.path.exists("sample_scan.jpg"):
        print("Downloading sample scan...")
        with open("sample_scan.jpg", "wb") as f:
            # A tiny 1x1 pixel just to test the pipeline doesn't crash on file-not-found
            # (In a real demo, user provides their own scan)
            import base64
            f.write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="))

if __name__ == "__main__":
    print("=== Demo 1: Multimodal Agentic Task ===")
    download_sample_image()
    
    print("User Request: 'Analyze the scanned image at sample_scan.jpg and draft an approval note based on it.'")
    
    initial_state = {
        "messages": [HumanMessage(content="Analyze the scanned image at sample_scan.jpg and draft an approval note based on the findings.")]
    }
    
    print("\n--- Invoking Agent ---")
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Tool Result ---")
    print(final_state.get("tool_results", "No tool result"))
