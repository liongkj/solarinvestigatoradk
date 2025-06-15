"""Data models for Solar Investigation management"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class InvestigationStatus(str, Enum):
    """Investigation status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentMessageType(str, Enum):
    """Agent message type enumeration"""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class AgentMessage(BaseModel):
    """Agent message model for chat history"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    message_type: AgentMessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class InvestigationRequest(BaseModel):
    """Request model for starting new investigation"""

    address: str = Field(..., description="Property address to investigate")
    monthly_usage: float = Field(..., description="Monthly electricity usage in kWh")
    property_type: str = Field(
        default="residential", description="Property type (residential/commercial)"
    )
    budget_range: Optional[str] = Field(
        None, description="Budget range for solar installation"
    )
    additional_notes: Optional[str] = Field(
        None, description="Additional notes or requirements"
    )


class Investigation(BaseModel):
    """Investigation data model"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    monthly_usage: float
    property_type: str
    budget_range: Optional[str] = None
    additional_notes: Optional[str] = None
    status: InvestigationStatus = InvestigationStatus.PENDING
    session_id: Optional[str] = None
    user_id: str = "api_user"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


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
