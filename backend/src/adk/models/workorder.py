"""Workorder models for Solar Investigation ADK"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class WorkorderStatus(str, Enum):
    """Workorder status enumeration"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkorderType(str, Enum):
    """Workorder type enumeration"""

    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    REPAIR = "repair"
    ANALYSIS = "analysis"


class WorkorderAgentRequest(BaseModel):
    """Request model for workorder agent processing"""

    todo_summary: str = Field(
        ..., description="Summary of maintenance/work requirements"
    )
    priority: str = Field(
        default="medium", description="Priority level: low, medium, high"
    )


class WorkorderAgentResponse(BaseModel):
    """Response model for workorder agent processing"""

    workorder_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    todo_summary: str
    agent_response: str = Field(
        ..., description="Free-form agent analysis and recommendations"
    )
    priority: str
    status: WorkorderStatus = Field(default=WorkorderStatus.COMPLETED)
    workorder_type: WorkorderType = Field(default=WorkorderType.ANALYSIS)
    created_at: datetime = Field(default_factory=datetime.now)


class Workorder(BaseModel):
    """Complete workorder model"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    type: WorkorderType = Field(default=WorkorderType.MAINTENANCE)
    description: str
    agent_response: Optional[str] = None
    priority: str = Field(default="medium")
    status: WorkorderStatus = Field(default=WorkorderStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
