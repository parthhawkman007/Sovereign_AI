import json
import logging
import os
from langchain_ollama import ChatOllama
from model_router import router

logging.basicConfig(level=logging.INFO)

class NeuronAgent:
    """A Dynamic Neuron that acts as the routing brain using a fast LLM."""
    def __init__(self):
        logging.info("Initializing Dynamic LLM NeuronAgent")
        
        self.action_classes = [
            "rag_engineering", "rag_commercial", "rag_compliance",
            "document_tools", "vision", "coding", "memory", "reasoning", "file_editing",
            "rag_workspace", "rag_codebase", "rag_formulas", "rag_symbol_legend", 
            "rag_defect_history", "rag_meeting_minutes", "rag_hr_policy", "rag_table_extractor"
        ]
        
        # Use the fastest available model locked to JSON
        self.router_llm = ChatOllama(model=router.get_reasoning_model(), format="json", temperature=0.0)
        
        self.system_prompt = f"""You are the central routing neuron of an AI workbench.
Your job is to analyze the user's prompt and determine which agents must be activated simultaneously to complete the task.

AVAILABLE AGENTS:
{", ".join(self.action_classes)}

GUIDELINES:
- If they ask for math, calculation, or writing scripts, assign "coding".
- If they attach or mention an image (png/jpg/jpeg) or P&ID/blueprint, assign "vision".
- If they mention PDFs, Excel, CSV, or documents, assign "document_tools".
- If they ask to modify/edit a file, assign "file_editing".
- If they ask to search specifications, assign "rag_engineering" (or similar RAGs).
- You can assign MULTIPLE agents if the prompt is complex (e.g., ["vision", "coding"]).
- If no specific tool is needed, just assign ["reasoning"].

You must ALSO output a primary model (e.g., "vision" for vision, "qwen" for coding, "document" for docs, "phi" for reasoning) and a sentiment ("casual", "urgent", "frustrated", "curious").

You MUST return EXACTLY this JSON format and nothing else:
{{
    "actions": ["agent1", "agent2"],
    "model": "model_choice",
    "sentiment": "sentiment_choice"
}}
"""

    def route_intent(self, text: str) -> tuple[list[str], str, str]:
        cleaned = text.strip().lower()
        
        # Direct file-presence shortcut for images to avoid hallucination if LLM misses it
        vision_shortcut = False
        if any(ext in cleaned for ext in [".png", ".jpg", ".jpeg"]):
            uploads_dir = os.path.join("workspace", "uploads")
            if os.path.exists(uploads_dir):
                for fname in os.listdir(uploads_dir):
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg')) and fname.lower() in cleaned:
                        vision_shortcut = True
                        break
        
        try:
            response = self.router_llm.invoke([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text}
            ])
            data = json.loads(response.content.strip())
            
            actions = data.get("actions", ["reasoning"])
            model_choice = data.get("model", "phi")
            sentiment_choice = data.get("sentiment", "casual")
            
            # Ensure valid actions
            actions = [a for a in actions if a in self.action_classes]
            if not actions:
                actions = ["reasoning"]
                
            if vision_shortcut and "vision" not in actions:
                actions.append("vision")
                
            logging.info(f"[Neuron] Dynamic Actions Triggered: {actions} | Main Model: {model_choice} | Sentiment: {sentiment_choice}")
            return actions, model_choice, sentiment_choice
            
        except Exception as e:
            logging.error(f"[Neuron] LLM Routing failed: {e}. Falling back to default.")
            actions = ["vision"] if vision_shortcut else ["reasoning"]
            return actions, "phi", "casual"

    def extract_args(self, text: str, action: str) -> str:
        """Extract specific structured arguments from the text based on the assigned action."""
        if action == "reasoning":
            return text
            
        prompt = f"""You are an argument extractor. The user wants to perform the action '{action}'.
Given their message, extract ONLY the specific arguments needed for that action (e.g., filename, search query, parameters, equipment ID).
If the action is file-related, extract the filepath. If it's a RAG query, extract the specific search terms.
Do NOT reply with a sentence. Reply ONLY with the extracted argument string.

User message: {text}"""
        
        try:
            # Use a lightweight model for extraction if possible, fallback to router_llm
            response = self.router_llm.invoke([{"role": "user", "content": prompt}])
            extracted = response.content.strip()
            
            # If the LLM hallucinated a full sentence, fallback to original text
            if len(extracted.split()) > 15: 
                return text
            return extracted
        except Exception as e:
            logging.error(f"[Neuron] Argument extraction failed: {e}")
            return text
