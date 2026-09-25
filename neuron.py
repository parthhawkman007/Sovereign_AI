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
            "rag_defect_history", "rag_meeting_minutes", "rag_hr_policy", "rag_table_extractor",
            "structured_extraction", "validation", "tools"
        ]
        
        self.router_llm = ChatOllama(model=router.get_reasoning_model(), format="json", temperature=0.0)
        
        self.system_prompt = f"""You are the central routing neuron of an AI workbench.
Your job is to understand what the user truly wants and route their request to the correct specialized agents.

AVAILABLE AGENTS:
- "reasoning" (phi4-mini) -> For general chat, questions, summaries, and explaining things.
- "coding" (qwen2.5-coder:3b) -> For writing python scripts, math, calculations, and data processing.
- "vision" / "document_tools" (granite3.2-vision:2b) -> For reading uploaded PDFs, images, Excel sheets, and documents.

FILE GENERATION:
- "structured_extraction", "validation", "tools" -> ONLY add these sequentially at the END if the user explicitly asks you to CREATE a new Word document (DOCX), Excel file (XLSX), or PowerPoint (PPTX).

GUIDELINES:
1. Always write down your logic in the "thought" field first.
2. If the user just wants to chat or ask a basic question -> route ONLY to "reasoning".
3. If the user wants you to write code or a script -> route to "coding".
4. If the user wants you to analyze a document/report and generate an Excel file -> route to "document_tools", then "structured_extraction", then "validation", then "tools".

You MUST return EXACTLY this JSON format and nothing else.
Here is an example for a complex request ("analyze my inspection report and give me an excel file"):
{{
    "thought": "The user wants me to read an inspection report and output an Excel file. I need to use document_tools to read it, extract the data, validate it, and use tools to create the XLSX.",
    "plan_id": "plan_001",
    "objective": "Analyze report and generate Excel",
    "steps": [
        {{
            "id": "step_1",
            "capability": "document_tools",
            "agent": "granite3.2-vision:2b",
            "input": ["Read the inspection report"],
            "depends_on": []
        }},
        {{
            "id": "step_2",
            "capability": "structured_extraction",
            "agent": "granite3.2-vision:2b",
            "input": ["artifact:step_1"],
            "depends_on": ["step_1"]
        }},
        {{
            "id": "step_3",
            "capability": "validation",
            "agent": "system",
            "input": ["artifact:step_2"],
            "depends_on": ["step_2"]
        }},
        {{
            "id": "step_4",
            "capability": "tools",
            "agent": "system",
            "input": ["artifact:step_3"],
            "depends_on": ["step_3"]
        }}
    ],
    "deliverables": ["XLSX"]
}}

Here is an example for a coding request ("write a python script for a calculator"):
{{
    "thought": "The user is asking for a python script. I must route this to the coding agent.",
    "plan_id": "plan_002",
    "objective": "Write calculator script",
    "steps": [
        {{
            "id": "step_1",
            "capability": "coding",
            "agent": "qwen2.5-coder:3b",
            "input": ["Write a python script for a calculator"],
            "depends_on": []
        }}
    ],
    "deliverables": []
}}

Here is an example for a simple question ("what is python?"):
{{
    "thought": "The user is just asking a general question. I will route this to the reasoning agent.",
    "plan_id": "plan_003",
    "objective": "Answer question",
    "steps": [
        {{
            "id": "step_1",
            "capability": "reasoning",
            "agent": "phi4-mini",
            "input": ["what is python?"],
            "depends_on": []
        }}
    ],
    "deliverables": []
}}
"""

    @staticmethod
    def _is_equipment_spreadsheet_request(text: str) -> bool:
        """Identify the high-value CSV inspection extraction path without LLM ambiguity.
        IMPORTANT: If the user wants to *write a script* to process the CSV, route to
        coding instead — even if the filename contains 'equipment' or 'inspection'.
        """
        lowered = text.lower()
        is_tabular_source = ".csv" in lowered or ".xlsx" in lowered
        asks_to_extract = any(term in lowered for term in ("extract", "equipment", "inspection"))
        # Do NOT intercept if user explicitly wants code/script
        wants_code = any(term in lowered for term in (
            "write a script", "write a python", "create a script", "write code",
            "python script", "write me a", "create a function", "write a function"
        ))
        return is_tabular_source and asks_to_extract and not wants_code

    @staticmethod
    def _file_deliverables(text: str) -> list[str]:
        """Return only output formats the workbench can generate locally."""
        lowered = text.lower()
        formats = []
        if any(term in lowered for term in ("word", "docx", "approval note")):
            formats.append("DOCX")
        if any(term in lowered for term in ("excel", "xlsx", "spreadsheet", "workbook")):
            formats.append("XLSX")
        if any(term in lowered for term in ("powerpoint", "pptx", "presentation", "slides")):
            formats.append("PPTX")
        return formats

    @classmethod
    def _is_file_deliverable_request(cls, text: str) -> bool:
        lowered = text.lower()
        has_supported_source = any(ext in lowered for ext in (
            ".txt", ".csv", ".xlsx", ".docx", ".pdf", ".ppt", ".pptx",
            ".png", ".jpg", ".jpeg",
        ))
        return has_supported_source and bool(cls._file_deliverables(text))

    @classmethod
    def _file_deliverable_plan(cls, text: str) -> dict:
        """Keep uploaded-file generation on Granite, never the coding model."""
        lowered = text.lower()
        is_image = any(ext in lowered for ext in (".png", ".jpg", ".jpeg"))
        source_capability = "vision" if is_image else "document_tools"
        return {
            "plan_id": "granite_file_deliverable",
            "objective": "Extract the uploaded file with Granite and generate the requested deliverable",
            "steps": [
                {"id": "step_1", "capability": source_capability, "agent": "granite3.2-vision:2b", "input": [text], "depends_on": []},
                {"id": "step_2", "capability": "structured_extraction", "agent": "granite3.2-vision:2b", "input": ["artifact:step_1"], "depends_on": ["step_1"]},
                {"id": "step_3", "capability": "validation", "agent": "system", "input": ["artifact:step_2"], "depends_on": ["step_2"]},
                {"id": "step_4", "capability": "tools", "agent": "system", "input": ["artifact:step_3"], "depends_on": ["step_3"]},
            ],
            "deliverables": cls._file_deliverables(text),
        }

    @staticmethod
    def _equipment_spreadsheet_plan(text: str) -> dict:
        """Use Granite for inspection-table extraction and create an XLSX artifact."""
        return {
            "plan_id": "inspection_equipment_xlsx",
            "objective": "Extract equipment from the inspection spreadsheet and generate Excel",
            "steps": [
                {"id": "step_1", "capability": "document_tools", "agent": "granite3.2-vision:2b", "input": [text], "depends_on": []},
                {"id": "step_2", "capability": "structured_extraction", "agent": "granite3.2-vision:2b", "input": ["artifact:step_1"], "depends_on": ["step_1"]},
                {"id": "step_3", "capability": "validation", "agent": "system", "input": ["artifact:step_2"], "depends_on": ["step_2"]},
                {"id": "step_4", "capability": "tools", "agent": "system", "input": ["artifact:step_3"], "depends_on": ["step_3"]},
            ],
            "deliverables": ["XLSX"],
        }

    def _get_workspace_inventory(self) -> str:
        uploads_dir = os.path.join("workspace", "uploads")
        if not os.path.exists(uploads_dir):
            return "AVAILABLE WORKSPACE FILES: (None)"
            
        files = os.listdir(uploads_dir)
        if not files:
            return "AVAILABLE WORKSPACE FILES: (None)"
            
        inventory = "AVAILABLE WORKSPACE FILES:\n"
        for f in files:
            inventory += f"- {f}\n"
        return inventory

    def route_intent(self, text: str) -> tuple[list[str], str, str]:
        # Legacy compatibility method - we should use generate_plan instead
        plan = self.generate_plan(text)
        actions = [step.get("capability") for step in plan.get("steps", [])]
        if not actions:
            actions = ["reasoning"]
            
        # Extract a default model and sentiment based on the first step
        model_choice = "phi"
        if actions:
            model_choice = plan.get("steps", [])[0].get("agent", "phi")
        
        return actions, model_choice, "casual"

    def generate_plan(self, text: str, messages: list = None) -> dict:
        cleaned = text.strip().lower()

        # Image files ALWAYS go to vision — check this FIRST before any other routing.
        # This prevents PNG/JPG/WebP files being accidentally routed to document_tools.
        _image_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff')
        if any(ext in cleaned for ext in _image_exts):
            return {
                "intent": "vision",
                "steps": [{"id": "step_1", "capability": "vision", "agent": "granite3.2-vision:2b", "args": text}],
                "sentiment": "casual",
                "selected_model": "granite3.2-vision:2b",
            }

        # Any supported uploaded-file request that asks for a generated
        # deliverable is a Granite-only extraction workflow.  Do this before
        # invoking the planner so an ambiguous request cannot drift to Qwen.
        if self._is_file_deliverable_request(text):
            return self._file_deliverable_plan(text)

        # CSV equipment extraction should never be delegated to the coding
        # model: it is a document/vision extraction workflow.
        if self._is_equipment_spreadsheet_request(text):
            return self._equipment_spreadsheet_plan(text)

        inventory = self._get_workspace_inventory()
        
        context = ""
        if messages and len(messages) > 1:
            context = "RECENT CONVERSATION CONTEXT:\n"
            for msg in messages[-5:-1]:
                role = "User" if msg.type == "human" else "System"
                context += f"{role}: {msg.content}\n"
        
        full_prompt = f"{inventory}\n\n{context}\n\nUSER REQUEST:\n{text}"
        
        try:
            response = self.router_llm.invoke([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": full_prompt}
            ])
            data = json.loads(response.content.strip())
            
            logging.info(f"[Neuron] Generated Plan: {json.dumps(data, indent=2)}")
            return data
            
        except Exception as e:
            logging.error(f"[Neuron] LLM Planning failed: {e}. Falling back to default plan.")
            # Fallback reasoning plan
            return {
                "plan_id": "plan_fallback",
                "objective": "Fallback reasoning",
                "steps": [
                    {
                        "id": "step_1",
                        "capability": "reasoning",
                        "agent": "phi4-mini",
                        "input": [text],
                        "depends_on": []
                    }
                ],
                "deliverables": []
            }

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
            response = self.router_llm.invoke([{"role": "user", "content": prompt}])
            extracted = response.content.strip()
            
            if len(extracted.split()) > 15: 
                return text
            return extracted
        except Exception as e:
            logging.error(f"[Neuron] Argument extraction failed: {e}")
            return text
