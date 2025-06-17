"""Data models for Solar Investigation management"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
import uuid


class InvestigationStatus(str, Enum):
    """Investigation status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    REQUIRES_ATTENTION = "requires_attention"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMessageType(str, Enum):
    """Agent message type enumeration"""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class AgentMessage(BaseModel):
    """Agent message model for chat history with UI state support"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    message_type: AgentMessageType
    content: str  # Full content
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    # UI State fields for frontend display
    ui_summary: Optional[str] = Field(
        None, description="10-word UI summary for display"
    )
    ui_state: Optional[Dict[str, Any]] = Field(
        None, description="UI-specific state data"
    )
    show_full_content: bool = Field(
        False, description="Whether to show full content by default"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class InvestigationRequest(BaseModel):
    """Request model for starting new investigation"""

    plant_id: str = Field(..., description="ID of the plant to investigate")
    start_date: date = Field(..., description="Start date for investigation period")
    end_date: date = Field(..., description="End date for investigation period")
    additional_notes: Optional[str] = Field(
        None, description="Additional notes or requirements"
    )
    parent_id: Optional[str] = Field(
        None, description="ID of parent investigation if this is a retry"
    )


class Investigation(BaseModel):
    """Investigation data model"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plant_id: str
    start_date: date
    end_date: date
    additional_notes: Optional[str] = None
    status: InvestigationStatus = InvestigationStatus.PENDING
    session_id: Optional[str] = None
    user_id: str = "api_user"
    parent_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    agent_stats: Optional[Dict[str, Any]] = None  # Rich ADK agent interaction stats

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }


class InvestigationResponse(BaseModel):
    """Response model for investigation endpoints"""

    investigation: Investigation
    message: str


class InvestigationListResponse(BaseModel):
    """Response model for investigation list"""

    investigations: List[Investigation]
    total: int
    page: int
    size: int


class ChatHistoryResponse(BaseModel):
    """Response model for chat history"""

    investigation_id: str
    messages: List[AgentMessage]
    total_messages: int


class DecisionRequest(BaseModel):
    """Request model for human decisions during investigation"""

    decision: str = Field(..., description="Human decision or response")
    decision_type: str = Field(
        default="continue", description="Type of decision (continue, stop, modify)"
    )
    additional_data: Optional[Dict[str, Any]] = None


class DecisionResponse(BaseModel):
    """Response model for decision handling"""

    investigation_id: str
    decision_accepted: bool
    message: str
    next_steps: Optional[List[str]] = None
