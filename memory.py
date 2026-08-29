import json
import os

class LongTermMemory:
    def __init__(self, persist_file="memory.json"):
        self.persist_file = persist_file
        self.memory = self._load()

    def _load(self):
        if os.path.exists(self.persist_file):
            with open(self.persist_file, "r") as f:
                return json.load(f)
        return {"preferences": {}, "project_context": ""}

    def _save(self):
        with open(self.persist_file, "w") as f:
            json.dump(self.memory, f)

    def set_preference(self, key, value):
        self.memory["preferences"][key] = value
        self._save()

    def update_context(self, context):
        self.memory["project_context"] += "\n" + context
        self._save()

    def get_context_string(self):
        prefs = ", ".join([f"{k}: {v}" for k, v in self.memory["preferences"].items()])
        ctx = self.memory["project_context"]
        return f"User Preferences: {prefs}\nLong-term Project Context: {ctx}"
