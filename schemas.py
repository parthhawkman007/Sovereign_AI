from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

class Provenance(BaseModel):
    source: str = Field(...)
    evidence: str = Field(...)
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = Field(default="MEDIUM")
    extraction_method: Literal["LLM", "REGEX", "HUMAN"] = Field(default="LLM")

class Equipment(BaseModel):
    id: str = Field(description="Equipment tag (e.g., T-101).")
    name: str = Field(description="Name of the equipment.")
    location: Optional[str] = Field(default=None)
    provenance: Provenance

class Measurement(BaseModel):
    id: str = Field(...)
    raw_value: str = Field(...)
    normalized_value: float = Field(...)
    unit: str = Field(...)
    target: str = Field(...)
    provenance: Provenance

class Finding(BaseModel):
    id: str = Field(...)
    description: str = Field(...)
    target: str = Field(...)
    severity: Literal["LOW", "MEDIUM", "HIGH"] = Field(...)
    provenance: Provenance

class Action(BaseModel):
    id: str = Field(...)
    description: str = Field(...)
    finding_id: Optional[str] = Field(default=None)
    target: str = Field(...)
    timeframe: str = Field(...)
    provenance: Provenance

class Relationship(BaseModel):
    source_id: str = Field(description="Source entity ID (e.g., equipment or instrument).")
    target_id: str = Field(description="Target entity ID.")
    type: Literal['CONNECTED_TO', 'FEEDS', 'CONTROLLED_BY', 'MEASURES', 'VENTS_TO', 'DRAINS_TO', 'STANDBY_FOR']
    provenance: Provenance

class CanonicalDocument(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    equipment: List[Equipment] = Field(default_factory=list)
    measurements: List[Measurement] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
