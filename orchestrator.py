from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time
import requests
import logging

class Step(BaseModel):
    id: str
    capability: str
    agent: Optional[str] = None
    tool: Optional[str] = None
    input: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)

class ExecutionPlan(BaseModel):
    plan_id: str
    objective: str
    steps: List[Step]
    deliverables: List[str] = Field(default_factory=list)

class Artifact(BaseModel):
    artifact_id: str
    session_id: str
    type: str
    created_by: str
    source_files: List[str] = Field(default_factory=list)
    status: str
    content: Any
    provenance: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = 0.0

import json
import os

class ArtifactStore:
    def __init__(self):
        self.persist_dir = os.path.join(os.getcwd(), "workspace", "sessions")
        os.makedirs(self.persist_dir, exist_ok=True)
        self.artifacts: Dict[str, Artifact] = {}
        self._load_all()

    def _get_path(self, session_id: str) -> str:
        return os.path.join(self.persist_dir, f"artifactory_{session_id}.json")

    def _load_all(self):
        if not os.path.exists(self.persist_dir):
            return
        for fname in os.listdir(self.persist_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(self.persist_dir, fname), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for aid, adata in data.items():
                            self.artifacts[aid] = Artifact(**adata)
                except Exception as e:
                    logging.error(f"[ArtifactStore] Error loading {fname}: {e}")

    def save(self, artifact: Artifact):
        artifact.timestamp = time.time()
        self.artifacts[artifact.artifact_id] = artifact
        logging.info(f"[ArtifactStore] Saved artifact {artifact.artifact_id} of type {artifact.type}")
        self._persist(artifact.session_id)

    def _persist(self, session_id: str):
        path = self._get_path(session_id)
        data = {aid: a.model_dump() for aid, a in self.artifacts.items() if a.session_id == session_id}
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"[ArtifactStore] Error persisting to {path}: {e}")

    def get(self, artifact_id: str) -> Optional[Artifact]:
        return self.artifacts.get(artifact_id)

    def list_by_session(self, session_id: str) -> List[Artifact]:
        return [a for a in self.artifacts.values() if a.session_id == session_id]

class ModelLifecycleManager:
    @staticmethod
    def acquire_model(model_name: str):
        if not model_name:
            return
        logging.info(f"[ModelLifecycle] Acquiring model: {model_name}")
        # Could preload model here using ollama API if needed
        # requests.post("http://127.0.0.1:11434/api/generate", json={"model": model_name, "keep_alive": "5m"}, timeout=2)

    @staticmethod
    def release_model(model_name: str):
        if not model_name:
            return
        logging.info(f"[ModelLifecycle] Releasing model: {model_name}")
        try:
            requests.post("http://127.0.0.1:11434/api/generate", json={"model": model_name, "keep_alive": 0}, timeout=2)
        except Exception as e:
            logging.error(f"[ModelLifecycle] Failed to release model {model_name}: {e}")

class ExecutionController:
    def __init__(self, store: ArtifactStore = None):
        # BUG-21 FIX: Accept an existing store to avoid double construction
        self.store = store if store is not None else ArtifactStore()
        
    def log_stage_start(self, step: Step):
        logging.info(f"[STAGE STARTED] {step.id}")
        logging.info(f"Capability: {step.capability}")
        logging.info(f"Agent: {step.agent}")
        logging.info(f"Input: {step.input}")
        ModelLifecycleManager.acquire_model(step.agent)

    def log_stage_end(self, step: Step, status: str, artifact_id: Optional[str] = None):
        logging.info(f"[STAGE {status}] {step.id}")
        if artifact_id:
            logging.info(f"Artifact: {artifact_id}")
        ModelLifecycleManager.release_model(step.agent)

# Global instances for the backend
# BUG-21 FIX: Create one ArtifactStore and pass it in to avoid double disk scan
global_artifact_store = ArtifactStore()
global_execution_controller = ExecutionController()
global_execution_controller.store = global_artifact_store  # share the single instance
