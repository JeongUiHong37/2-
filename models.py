from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    message: str
    type: str  # "concept", "confirmation", "analysis", "error", "info"
    metadata: Dict[str, Any] = {}

class MetricRequest(BaseModel):
    session_id: str
    metric: str

class ResetRequest(BaseModel):
    session_id: str

class ChatSession(BaseModel):
    session_id: str
    chat_history: List[Dict[str, Any]] = []
    current_state: str = "idle"  # "idle", "awaiting_confirmation", "confirmed"
    pending_intent: Optional[List[str]] = None
    created_at: datetime

    class Config:
        arbitrary_types_allowed = True
