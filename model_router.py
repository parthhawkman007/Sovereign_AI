import requests
import yaml
import os

class ModelRouter:
    def __init__(self):
        self.models = self._fetch_installed_models()
        self.config = self._load_config()

    def _load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f).get("models", {})
        return {}

    def _fetch_installed_models(self):
        try:
            res = requests.get("http://localhost:11434/api/tags", timeout=3)
            if res.status_code == 200:
                return [m["name"] for m in res.json().get("models", [])]
        except Exception:
            pass
        return []

    def get_reasoning_model(self, fallback=None):
        fallback = fallback or self.config.get("reasoning", "phi4-mini")
        for m in self.models:
            if "phi4" in m or "llama3" in m or "mixtral" in m:
                return m
        return fallback

    def get_coding_model(self, fallback=None):
        fallback = fallback or self.config.get("coding", "qwen2.5-coder:3b")
        for m in self.models:
            if "coder" in m or "starcoder" in m or "deepseek-coder" in m:
                return m
        return self.get_reasoning_model(fallback=fallback)

    def get_vision_model(self, fallback=None):
        fallback = fallback or self.config.get("vision", "granite3.2-vision:2b")
        for m in self.models:
            if "granite3.2-vision" in m or "granite" in m or "vision" in m:
                return m
        return fallback

    def get_embedding_model(self, fallback=None):
        fallback = fallback or self.config.get("embedding", "nomic-embed-text")
        for m in self.models:
            if "embed" in m:
                return m
        return fallback

    def get_document_model(self, fallback=None):
        return self.get_reasoning_model(fallback=fallback)

    def resolve_model(self, requested_name: str) -> str:
        if not requested_name:
            return self.get_reasoning_model()
            
        req = str(requested_name).strip().lower()

        # Semantic overrides to protect specific model roles
        if req == "qwen" or "coder" in req or "code" in req:
            return self.get_coding_model()
        if "vision" in req or "granite" in req or "image" in req:
            return self.get_vision_model()
        if req == "document":
            return self.get_document_model()
        if req == "phi" or "reason" in req:
            return self.get_reasoning_model()

        # 1. Exact match
        for m in self.models:
            if m.lower() == req:
                return m
                
        # 2. Match without tag or prefix match
        base_req = req.split(':')[0]
        for m in self.models:
            if m.lower().split(':')[0] == base_req or req in m.lower():
                return m
            
        return self.get_reasoning_model()

    def get_model_descriptions(self):
        """Returns a prompt-friendly string of available models and their capabilities."""
        if not self.models:
            # Mock models if Ollama isn't running
            return "- phi4-mini: Fast, general reasoning and text summarization.\n- qwen2.5-coder:3b: Specialized for writing Python code and calculations.\n- granite3.2-vision:2b: Multimodal vision model for analyzing images, scans, and P&IDs."
        
        desc = ""
        for m in self.models:
            if "coder" in m or "starcoder" in m:
                desc += f"- {m}: Specialized for writing Python code and calculations.\n"
            elif "granite" in m or "vision" in m or "llava" in m:
                desc += f"- {m}: Multimodal vision model for analyzing images, scans, and P&IDs.\n"
            elif "embed" in m:
                pass # Don't expose embedding models to the multiplexer
            else:
                desc += f"- {m}: General reasoning, document summarization, and RAG synthesis.\n"
        return desc if desc else "No models detected."

# Global instance for easy import
router = ModelRouter()
