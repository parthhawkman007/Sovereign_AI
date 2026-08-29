import requests

class ModelRouter:
    def __init__(self):
        self.models = self._fetch_installed_models()

    def _fetch_installed_models(self):
        try:
            res = requests.get("http://localhost:11434/api/tags", timeout=3)
            if res.status_code == 200:
                return [m["name"] for m in res.json().get("models", [])]
        except Exception:
            pass
        return []

    def get_reasoning_model(self, fallback="phi4-mini"):
        for m in self.models:
            if "phi4" in m or "llama3" in m or "mixtral" in m:
                return m
        return fallback

    def get_coding_model(self, fallback="qwen2.5-coder:3b"):
        for m in self.models:
            if "coder" in m or "starcoder" in m or "deepseek-coder" in m:
                return m
        return self.get_reasoning_model(fallback=fallback)

    def get_vision_model(self, fallback="gemma3:4b"):
        for m in self.models:
            if "gemma3" in m or "llava" in m or "bakllava" in m:
                return m
        return fallback

    def get_embedding_model(self, fallback="nomic-embed-text"):
        for m in self.models:
            if "embed" in m:
                return m
        return fallback

    def get_model_descriptions(self):
        """Returns a prompt-friendly string of available models and their capabilities."""
        if not self.models:
            # Mock models if Ollama isn't running
            return "- phi4-mini: Fast, general reasoning and text summarization.\n- qwen2.5-coder:3b: Specialized for writing Python code and calculations.\n- gemma3:4b: Multimodal vision model for analyzing images and scans."
        
        desc = ""
        for m in self.models:
            if "coder" in m or "starcoder" in m:
                desc += f"- {m}: Specialized for writing Python code and calculations.\n"
            elif "gemma3" in m or "llava" in m:
                desc += f"- {m}: Multimodal vision model for analyzing images, scans, and P&IDs.\n"
            elif "embed" in m:
                pass # Don't expose embedding models to the multiplexer
            else:
                desc += f"- {m}: General reasoning, document summarization, and RAG synthesis.\n"
        return desc if desc else "No models detected."

# Global instance for easy import
router = ModelRouter()
