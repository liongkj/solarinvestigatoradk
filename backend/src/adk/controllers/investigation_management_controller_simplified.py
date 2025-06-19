"""Simplified Investigation Management Controller using ADK best practices"""

from fastapi import APIRouter, Depends, HTTPException
from typing import List
import logging

from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
)
from adk.services.investigation_service_simplified import (
    get_simplified_investigation_service,
    SimplifiedInvestigationService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.post("/", response_model=Investigation)
async def create_investigation(
    request: InvestigationRequest,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Create and start a new solar investigation"""
    try:
        return await service.start_investigation(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating investigation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[Investigation])
async def list_investigations(
    limit: int = 50,
    offset: int = 0,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """List all investigations"""
    try:
        return await service.list_investigations(limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"Error listing investigations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{investigation_id}", response_model=Investigation)
async def get_investigation(
    investigation_id: str,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Get investigation by ID"""
    try:
        investigation = await service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return investigation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting investigation {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{investigation_id}/continue")
async def continue_investigation(
    investigation_id: str,
    message: dict,  # {"message": "user message"}
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Continue investigation with user input"""
    try:
        investigation = await service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        user_message = message.get("message", "")
        if not user_message:
            raise HTTPException(status_code=400, detail="Message is required")

        response = await service.continue_investigation(investigation_id, user_message)
        return {"response": response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error continuing investigation {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{investigation_id}/chat", response_model=List[AgentMessage])
async def get_chat_history(
    investigation_id: str,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Get chat history for investigation"""
    try:
        investigation = await service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        return await service.get_chat_history(investigation_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history for {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{investigation_id}")
async def delete_investigation(
    investigation_id: str,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Delete an investigation"""
    try:
        success = await service.delete_investigation(investigation_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Investigation not found or could not be deleted",
            )
        return {"message": "Investigation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting investigation {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{investigation_id}/status")
async def update_investigation_status(
    investigation_id: str,
    status_update: dict,  # {"status": "completed", "error_message": "optional"}
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Update investigation status (for admin/debugging)"""
    try:
        investigation = await service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        status_str = status_update.get("status")
        error_message = status_update.get("error_message")

        try:
            status = InvestigationStatus(status_str)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_str}")

        await service._update_status(investigation_id, status, error_message)
        return {"message": f"Status updated to {status.value}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating investigation status {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
