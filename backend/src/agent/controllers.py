# mypy: disable - error - code = "no-untyped-def,misc"
import os
import sys
from typing import List, Optional
from fastapi import APIRouter, HTTPException

# Add the src directory to the Python path for proper package imports
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from agent.models import Project, Investigation, WorkOrder, DashboardSummary
from agent.mock_data import mock_data_service

# Create API router with a different prefix to avoid conflicts with LangGraph routes
api_router = APIRouter(prefix="/dashboard/api")


@api_router.get("/projects", response_model=List[Project])
async def get_projects(status: Optional[str] = None):
    """Get all projects, optionally filtered by status."""
    if status:
        return mock_data_service.get_projects_by_status(status)
    return mock_data_service.get_all_projects()


@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Get a specific project by ID."""
    project = mock_data_service.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@api_router.get("/investigations", response_model=List[Investigation])
async def get_investigations(
    project_id: Optional[str] = None, status: Optional[str] = None
):
    """Get all investigations, optionally filtered by project or status."""
    if project_id:
        return mock_data_service.get_investigations_by_project(project_id)
    elif status:
        return mock_data_service.get_investigations_by_status(status)
    return mock_data_service.get_all_investigations()


@api_router.get("/investigations/{investigation_id}", response_model=Investigation)
async def get_investigation(investigation_id: str):
    """Get a specific investigation by ID."""
    investigation = mock_data_service.get_investigation_by_id(investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


@api_router.get("/workorders", response_model=List[WorkOrder])
async def get_work_orders(
    project_id: Optional[str] = None, status: Optional[str] = None
):
    """Get all work orders, optionally filtered by project or status."""
    if project_id:
        return mock_data_service.get_work_orders_by_project(project_id)
    elif status:
        return mock_data_service.get_work_orders_by_status(status)
    return mock_data_service.get_all_work_orders()


@api_router.get("/workorders/{workorder_id}", response_model=WorkOrder)
async def get_work_order(workorder_id: str):
    """Get a specific work order by ID."""
    work_order = mock_data_service.get_work_order_by_id(workorder_id)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    return work_order


@api_router.get("/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    """Get dashboard summary statistics."""
    return mock_data_service.get_dashboard_summary()
