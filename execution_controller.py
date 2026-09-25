from typing import Any
from orchestrator import global_execution_controller, Step, Artifact
import time
import uuid

def execution_controller_node(state):
    print("--- EXECUTION CONTROLLER ---")
    plan = state.get("execution_plan", {})
    completed = set(state.get("completed_steps", []))
    failed = set(state.get("failed_steps", []))
    steps = plan.get("steps", [])
    
    if not steps:
        print("[ExecutionController] No plan. Routing to legacy extraction.")
        return {"next_action": ["structured_extraction"]}
        
    next_step = None
    for step_dict in steps:
        step_id = step_dict.get("id")
        if step_id in completed or step_id in failed:
            continue
            
        deps = step_dict.get("depends_on", [])
        if all(d in completed for d in deps):
            next_step = step_dict
            break
            
    if not next_step:
        print("[ExecutionController] All steps completed or deadlocked.")
        capabilities_executed = [s.get("capability") for s in steps if s.get("id") in completed]
        
        # Only RAG-only workflows need a Phi synthesis step.  Specialist
        # nodes already produce their own user-facing output, so appending
        # Phi would cross the selected model boundary.
        if "step_final_reasoning" not in completed:
            specialist_completed = any(c in capabilities_executed for c in ["coding", "file_editing", "vision", "document_tools"])
            if not specialist_completed and not any(c in capabilities_executed for c in ["reasoning", "tools", "structured_extraction", "validation"]):
                print("[ExecutionController] Injecting final reasoning step to generate response.")
                return {
                    "next_action": ["reasoning"], 
                    "active_step_id": "step_final_reasoning", 
                    "active_step_capability": "reasoning"
                }
                
        return {"next_action": ["finish"]}
            
    step_id = next_step.get("id")
    capability = next_step.get("capability")
    inputs = next_step.get("input", [])
    
    print(f"[ExecutionController] Selected step {step_id}: {capability}")
    global_execution_controller.log_stage_start(Step(**next_step))
    
    # Artifact-based state passing
    injected_data = ""
    for inp in inputs:
        if inp.startswith("artifact:"):
            art_id = inp.split(":")[1]
            artifact = global_execution_controller.store.get(art_id)
            if artifact:
                injected_data += f"[Data from {art_id} ({artifact.type})]:\n{artifact.content}\n\n"
    
    state_updates = {
        "next_action": [capability], 
        "active_step_id": step_id, 
        "active_step_capability": capability
    }
    
    if injected_data:
        state_updates["extracted_data"] = injected_data.strip()
    
    return state_updates

def mark_step_complete(state, artifact_id=None):
    active_step = state.get("active_step_id")
    if active_step:
        print(f"[ExecutionController] Marked {active_step} as COMPLETED.")
        global_execution_controller.log_stage_end(Step(id=active_step, capability=state.get("active_step_capability", "")), "COMPLETED", artifact_id)
        return {"completed_steps": [active_step], "active_step_id": ""}
    return {}
