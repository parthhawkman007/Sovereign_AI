import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import json
import re
from typing import TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from tools import (
    create_approval_note, execute_python_code, analyze_image, 
    create_excel_report, read_excel_file, create_presentation,
    read_local_file, read_pdf_file, ocr_image, analyze_engineering_drawing,
    extract_table_to_excel, compare_documents
)
from rag import LocalKnowledgeBase
from model_router import router
from memory import LongTermMemory
from plugin_loader import load_plugins

# Initialize domain-specific KBs
kbs = {
    "engineering": None,
    "commercial": None,
    "compliance": None
}

def get_kb(domain):
    if kbs[domain] is None:
        kbs[domain] = LocalKnowledgeBase(domain=domain)
    return kbs[domain]

ltm = LongTermMemory()
plugins = load_plugins()

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    extracted_data: str
    next_action: str
    tool_args: str
    error_count: int
    user_role: str
    selected_model: str # The dynamically chosen model by the multiplexer

def multiplexer_node(state: AgentState):
    print("--- MULTIPLEXER NODE (Neural Orchestrator) ---")
    messages = state.get("messages", [])
    if not messages:
        return {"next_action": "finish"}
        
    user_input = messages[-1].content
    extracted = state.get("extracted_data", "")
    
    # Multiplexer always runs on a fast reasoning model
    planner_llm = ChatOllama(model=router.get_reasoning_model(), temperature=0.0)
    memory_context = ltm.get_context_string()
    model_descriptions = router.get_model_descriptions()
    
    sys_prompt = f"""You are the Neural Multiplexer Agent (Master Orchestrator) for an industrial AI workbench.
Memory Context: {memory_context}

Your job is twofold:
1. Decide the SINGLE next best action (Node) to take.
2. Dynamically assign the best LLM Model for the downstream node to use for that task.

Available LLM Models on the server:
{model_descriptions}

Available Nodes (Actions):
- 'rag_engineering': Search P&IDs, equipment manuals, technical specs. (args: search query)
- 'rag_commercial': Search financials, vendor negotiations, approval notes. (args: search query)
- 'rag_compliance': Search company policies, SOPs, safety guidelines. (args: search query)
- 'document_tools': Read specific local files. (args: file path)
- 'vision': Extract text/data from scans or images. (args: image path)
- 'coding': Write and execute python to calculate math/formulas. (args: calculation description)
- 'reasoning': Draft the final response or document once data is gathered. (args: formatting instructions)
- 'finish': If the task is completely done.

Output a strict JSON object: {{"next_action": "<action>", "args": "<args>", "selected_model": "<exact_model_name_from_list>"}}"""

    prompt = [
        {"role": "system", "content": sys_prompt}, 
        {"role": "user", "content": f"User Request: {user_input}\n\nGathered Data So Far:\n{extracted if extracted else 'None'}"}
    ]
    
    response = planner_llm.invoke(prompt).content.strip()
    
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != 0:
            decision = json.loads(response[start:end])
            action = decision.get("next_action", "reasoning")
            args = decision.get("args", "")
            sel_model = decision.get("selected_model", router.get_reasoning_model())
        else:
            action = "reasoning"
            args = ""
            sel_model = router.get_reasoning_model()
    except json.JSONDecodeError:
        action = "reasoning"
        args = ""
        sel_model = router.get_reasoning_model()
        
    print(f"Multiplexer Decision: {action} | Model Assigned: {sel_model} | Args: {args}")
    
    if action == "finish" and not extracted:
        action = "reasoning"
        
    return {"next_action": action, "tool_args": str(args), "selected_model": sel_model}

def rag_engineering_node(state: AgentState):
    print("--- RAG AGENT (ENGINEERING) ---")
    kb = get_kb("engineering")
    query = state.get("tool_args", state["messages"][-1].content)
    role = state.get("user_role", "engineer")
    context = kb.search(query, user_role=role)
    current_data = state.get("extracted_data", "")
    return {"extracted_data": current_data + f"\n\n[Engineering Context for '{query}']: {context}".strip()}

def rag_commercial_node(state: AgentState):
    print("--- RAG AGENT (COMMERCIAL) ---")
    kb = get_kb("commercial")
    query = state.get("tool_args", state["messages"][-1].content)
    role = state.get("user_role", "engineer")
    context = kb.search(query, user_role=role)
    current_data = state.get("extracted_data", "")
    return {"extracted_data": current_data + f"\n\n[Commercial Context for '{query}']: {context}".strip()}

def rag_compliance_node(state: AgentState):
    print("--- RAG AGENT (COMPLIANCE) ---")
    kb = get_kb("compliance")
    query = state.get("tool_args", state["messages"][-1].content)
    role = state.get("user_role", "engineer")
    context = kb.search(query, user_role=role)
    current_data = state.get("extracted_data", "")
    return {"extracted_data": current_data + f"\n\n[Compliance Context for '{query}']: {context}".strip()}

def document_tools_node(state: AgentState):
    print("--- DOCUMENT TOOLS NODE ---")
    args = state.get("tool_args", "")
    user_input = state["messages"][-1].content
    paths = re.findall(r'([A-Za-z0-9_\\/\.-]+\.(?:txt|docx|pdf|csv|xlsx))', args + " " + user_input)
    content = "No file paths found to read."
    if paths:
        path = paths[0]
        if path.endswith(".pdf"): content = read_pdf_file.invoke({"filepath": path})
        elif path.endswith(".xlsx"): content = read_excel_file.invoke({"filepath": path})
        else: content = read_local_file.invoke({"filepath": path})
            
    current_data = state.get("extracted_data", "")
    new_data = current_data + f"\n\n[File Data from {paths[0] if paths else 'unknown'}]:\n{content}"
    return {"extracted_data": new_data.strip()}

def vision_node(state: AgentState):
    print(f"--- VISION NODE (Model: {state.get('selected_model', 'default')}) ---")
    args = state.get("tool_args", "")
    user_input = state["messages"][-1].content
    paths = re.findall(r'([A-Za-z0-9_\\/\.-]+\.(?:png|jpg|jpeg))', args + " " + user_input)
    image_path = paths[0] if paths else "unknown.png"
    
    # We dynamically pass the selected model to the tools if they support it
    # For now, analyze_image has it hardcoded to OLLAMA_MODEL_VISION in tools.py,
    # but we will assume the tool picks up the active model from context or we pass it
    # To properly inject it, we could pass it via args.
    
    if "ocr" in args.lower() or "text" in args.lower(): result = ocr_image.invoke({"image_path": image_path})
    elif "table" in args.lower() or "excel" in args.lower(): result = extract_table_to_excel.invoke({"image_path": image_path})
    elif "drawing" in args.lower() or "p&id" in args.lower() or "pid" in args.lower(): result = analyze_engineering_drawing.invoke({"image_path": image_path})
    else: result = analyze_image.invoke({"image_path": image_path, "prompt": args if args else "Extract key information."})
        
    current_data = state.get("extracted_data", "")
    new_data = current_data + f"\n\n[Vision Data]:\n{result}"
    return {"extracted_data": new_data.strip()}

def coding_node(state: AgentState):
    sel_model = state.get("selected_model", router.get_coding_model())
    print(f"--- CODING NODE (Model: {sel_model}) ---")
    args = state.get("tool_args", state["messages"][-1].content)
    
    coder_llm = ChatOllama(model=sel_model, temperature=0)
    system_prompt = "You are a senior python developer. Write pure python code to solve the engineering/math problem. Output pure python code only. No markdown. Use print() to output results."
    prompt_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Data context: {state.get('extracted_data', '')}\n\nTask: {args}"}
    ]
    response = coder_llm.invoke(prompt_messages)
    code = response.content.replace("```python", "").replace("```", "").strip()
    result = execute_python_code.invoke({"code": code})
    
    current_data = state.get("extracted_data", "")
    new_data = current_data + f"\n\n[Calculation Result]:\nCode executed:\n{code}\nOutput:\n{result}"
    return {"extracted_data": new_data.strip()}

def reasoning_node(state: AgentState):
    sel_model = state.get("selected_model", router.get_reasoning_model())
    print(f"--- REASONING NODE (Model: {sel_model}) ---")
    messages = state["messages"]
    args = state.get("tool_args", "")
    
    llm = ChatOllama(model=sel_model, temperature=0.1)
    memory_context = ltm.get_context_string()
    
    system_prompt = f"""You are a secure, air-gapped AI assistant. 
Memory Context: {memory_context}
CRITICAL INSTRUCTION: You MUST cite your sources exactly using the Source filenames provided in the RAG Context."""

    if "excel" in args.lower() or "csv" in args.lower():
        system_prompt += " Output ONLY comma-separated values (CSV) with a header row. No markdown."
    elif "presentation" in args.lower() or "ppt" in args.lower():
        system_prompt += " Output ONLY slide content. Separate slides with '---'. Line 1 is title, rest are bullets."
    elif "approval" in args.lower() or "document" in args.lower():
        system_prompt += " Format the information into a professional Engineering Report or Approval Note. CITE YOUR SOURCES."
        
    prompt_messages = [{"role": "system", "content": system_prompt}]
    
    extracted = state.get("extracted_data", "")
    if extracted:
         prompt_messages.append({"role": "user", "content": f"Data gathered from tools:\n{extracted}\n\nPlease synthesize this into the final response for the user request: {messages[-1].content}"})
    else:
         prompt_messages.append({"role": "user", "content": messages[-1].content})
    
    response = llm.invoke(prompt_messages)
    msgs = [AIMessage(content=response.content.strip())]
    return {"extracted_data": response.content.strip(), "messages": msgs}

def tool_execution_node(state: AgentState):
    print("--- DELIVERABLE TOOLS NODE ---")
    user_input = state["messages"][0].content if state["messages"] else ""
    data = state.get("extracted_data", "")
    
    if "excel" in user_input.lower() or "spreadsheet" in user_input.lower():
        create_excel_report.invoke({"data": data})
    elif "presentation" in user_input.lower() or "ppt" in user_input.lower():
        create_presentation.invoke({"content": data})
    elif "approval" in user_input.lower() or "word" in user_input.lower() or "docx" in user_input.lower() or "document" in user_input.lower():
        create_approval_note.invoke({"content": data})
        
    return {}

def route_multiplexer(state: AgentState) -> str:
    action = state.get("next_action", "finish")
    valid_actions = ["rag_engineering", "rag_commercial", "rag_compliance", "document_tools", "vision", "coding", "reasoning"]
    if action in valid_actions:
        return action
    return END

def route_reasoning(state: AgentState) -> str:
    user_input = state["messages"][0].content.lower() if state["messages"] else ""
    if any(keyword in user_input for keyword in ["excel", "spreadsheet", "presentation", "ppt", "approval", "word", "docx", "document"]):
        return "tools"
    return END

workflow = StateGraph(AgentState)

workflow.add_node("multiplexer", multiplexer_node)
workflow.add_node("rag_engineering", rag_engineering_node)
workflow.add_node("rag_commercial", rag_commercial_node)
workflow.add_node("rag_compliance", rag_compliance_node)
workflow.add_node("document_tools", document_tools_node)
workflow.add_node("vision", vision_node)
workflow.add_node("coding", coding_node)
workflow.add_node("reasoning", reasoning_node)
workflow.add_node("tools", tool_execution_node)

workflow.add_edge(START, "multiplexer")

workflow.add_edge("rag_engineering", "multiplexer")
workflow.add_edge("rag_commercial", "multiplexer")
workflow.add_edge("rag_compliance", "multiplexer")
workflow.add_edge("document_tools", "multiplexer")
workflow.add_edge("vision", "multiplexer")
workflow.add_edge("coding", "multiplexer")

workflow.add_conditional_edges("multiplexer", route_multiplexer)
workflow.add_conditional_edges("reasoning", route_reasoning)
workflow.add_edge("tools", END)

memory = MemorySaver()

# Compile with HITL on "tools" node
app = workflow.compile(checkpointer=memory, interrupt_before=["tools"])

if __name__ == "__main__":
    print("Sovereign AI Workbench - Neural Multiplexer Workflow Ready")
