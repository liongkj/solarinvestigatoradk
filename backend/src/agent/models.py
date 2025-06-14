"""Pydantic models for the Solar Investigator API."""

from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel


class ProcessedEvent(BaseModel):
    """Model for investigation processing events."""

    title: str
    data: str


class Project(BaseModel):
    """Model for solar projects."""

    id: str
    name: str
    address: str
    customer: str
    status: Literal["planning", "investigation", "approved", "in-progress", "completed"]
    createdAt: str
    type: Literal["residential", "commercial", "industrial"]


class Investigation(BaseModel):
    """Model for project investigations."""

    id: str
    projectId: str
    title: str
    summary: str
    findings: List[str]
    recommendations: List[str]
    status: Literal["completed", "in-progress", "failed"]
    createdAt: str
    processedEvents: List[ProcessedEvent]
    aiResponse: Optional[str] = None


class WorkOrder(BaseModel):
    """Model for work orders."""

    id: str
    projectId: str
    title: str
    description: str
    tasks: List[str]
    timeline: str
    status: Literal["draft", "approved", "in-progress", "completed"]
    createdAt: str


class DashboardSummary(BaseModel):
    """Model for dashboard summary statistics."""

    totalProjects: int
    activeInvestigations: int
    completedInvestigations: int
    activeWorkOrders: int
    completedWorkOrders: int
