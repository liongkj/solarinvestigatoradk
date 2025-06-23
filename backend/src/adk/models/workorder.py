"""Workorder models for the investigation system"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


class WorkorderPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class WorkorderStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Workorder(BaseModel):
    id: str
    investigation_id: str
    title: str
    description: str
    priority: WorkorderPriority = WorkorderPriority.MEDIUM
    status: WorkorderStatus = WorkorderStatus.PENDING
    equipment_id: Optional[str] = None
    location: Optional[str] = None
    estimated_duration_hours: Optional[float] = None
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WorkorderRequest(BaseModel):
    title: str
    description: str
    priority: WorkorderPriority = WorkorderPriority.MEDIUM
    equipment_id: Optional[str] = None
    location: Optional[str] = None
    estimated_duration_hours: Optional[float] = None
    due_date: Optional[datetime] = None


class WorkorderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[WorkorderPriority] = None
    status: Optional[WorkorderStatus] = None
    equipment_id: Optional[str] = None
    location: Optional[str] = None
    estimated_duration_hours: Optional[float] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
