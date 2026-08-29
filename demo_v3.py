import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import time
from langchain_core.messages import HumanMessage
from agent import workflow
from cli import check_health, process_request

print("="*80)
print(" === SOVEREIGN AI WORKBENCH - V3 VENUE DEMO SCRIPT === ")
print("="*80)

# Check health first
check_health()
print("\n[Demo] Beginning automated run-through of V3 Capabilities...")
time.sleep(2)

print("\n\n" + "="*80)
print(" DEMO 1: Multimodal Inspection Report Analysis with Engineering P&ID Prompts")
print("="*80)
print("[Narration] The user provides a scanned inspection report image.")
print("[Narration] The agent must use the planner to detect a vision task, analyze it, and save it as an Excel Table.")

# Ensure we have the mock image
if not os.path.exists("inspection_report.jpg"):
    import mock_inspection_report
    mock_inspection_report.create_mock_report()

prompt1 = "Extract the table of thickness readings from inspection_report.jpg and save it to an Excel file."
print(f"\nPrompt: '{prompt1}'\n")
time.sleep(2)
process_request(prompt1)


print("\n\n" + "="*80)
print(" DEMO 2: RAG Source Citation & Multi-Step Memory")
print("="*80)
print("[Narration] We ask a regulatory question. The LLM Planner routes it to RAG, then Reasoning.")
print("[Narration] The response will explicitly cite the source file from the local knowledge base.")

# Ensure RAG is built
from rag import LocalKnowledgeBase
kb = LocalKnowledgeBase()
kb.ingest_documents("sops_data")

prompt2 = "What is the maximum allowable pressure according to the SOPs? Give me the source citation."
print(f"\nPrompt: '{prompt2}'\n")
time.sleep(2)
process_request(prompt2)


print("\n\n" + "="*80)
print(" DEMO 3: Sandboxed Coding with Security Hardening")
print("="*80)
print("[Narration] We ask the agent to write a script. We will deliberately ask it to import 'os' to prove the sandbox blocks it.")

prompt3 = "Write a python script that imports os and deletes all text files."
print(f"\nPrompt: '{prompt3}'\n")
time.sleep(2)
process_request(prompt3)

print("\n[Demo] End of V3 Venue Demo Script.")
print("="*80)
