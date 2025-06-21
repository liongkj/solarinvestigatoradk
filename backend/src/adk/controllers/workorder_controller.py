"""Workorder management API controllers for Solar Investigator ADK"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
import logging

from adk.models.workorder import (
    Workorder,
    WorkorderAgentRequest,
    WorkorderAgentResponse,
)
from adk.services.workorder_service import WorkorderService
from adk.services.investigation_service_simplified import SimplifiedInvestigationService

logger = logging.getLogger(__name__)

# Router for workorder management endpoints
router = APIRouter(prefix="/api/investigations", tags=["workorder-management"])


@router.post("/{investigation_id}/workorders/agent", response_model=dict)
async def create_workorder_with_agent(
    investigation_id: str,
    request: WorkorderAgentRequest,
    workorder_service: WorkorderService = Depends(WorkorderService),
    investigation_service: SimplifiedInvestigationService = Depends(
        SimplifiedInvestigationService
    ),
):
    """
    Create a workorder using Google ADK agent processing

    This endpoint:
    1. Processes the todo summary with the workorder agent
    2. Creates a workorder with agent recommendations
    3. Adds agent messages to investigation chat history
    """
    try:
        logger.info(
            f"Creating workorder with agent for investigation {investigation_id}"
        )

        # Verify investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        # Process workorder with agent
        workorder_response, chat_messages = (
            await workorder_service.create_workorder_with_agent(
                investigation_id=investigation_id, request=request
            )
        )

        # Note: chat_messages are returned for logging/reference but are managed
        # internally by the workorder service and ADK session framework

        return {
            "message": "Workorder processed successfully with agent",
            "workorder": workorder_response.dict(),
            "chat_messages_added": len(chat_messages),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error creating workorder with agent for investigation {investigation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{investigation_id}/workorders", response_model=List[Workorder])
async def get_workorders(
    investigation_id: str,
    workorder_service: WorkorderService = Depends(WorkorderService),
    investigation_service: SimplifiedInvestigationService = Depends(
        SimplifiedInvestigationService
    ),
):
    """
    Get all workorders for a specific investigation
    """
    try:
        # Verify investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        workorders = await workorder_service.get_workorders_by_investigation(
            investigation_id
        )
        return workorders

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting workorders for investigation {investigation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{investigation_id}/workorders/manual", response_model=dict)
async def create_manual_workorder(
    investigation_id: str,
    request: dict,  # {"description": "Work order details", "priority": "medium"}
    workorder_service: WorkorderService = Depends(WorkorderService),
    investigation_service: SimplifiedInvestigationService = Depends(
        SimplifiedInvestigationService
    ),
):
    """
    Create a manual workorder (existing functionality enhanced)
    """
    try:
        # Verify investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        description = request.get("description", "")
        if not description:
            raise HTTPException(
                status_code=400, detail="Workorder description is required"
            )

        priority = request.get("priority", "medium")

        # Create manual workorder
        workorder = await workorder_service.create_manual_workorder(
            investigation_id=investigation_id,
            description=description,
            priority=priority,
        )

        return {
            "message": "Manual workorder created successfully",
            "workorder": workorder.dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error creating manual workorder for investigation {investigation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
