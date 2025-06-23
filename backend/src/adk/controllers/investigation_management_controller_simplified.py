"""Simplified Investigation Management Controller using ADK best practices"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List
import logging
import json
import asyncio

from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatus,
    AgentMessage,
)
from adk.services.investigation_service_simplified import (
    get_simplified_investigation_service,
    SimplifiedInvestigationService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.post("/", response_model=InvestigationResponse)
async def create_investigation(
    request: InvestigationRequest,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Create and start a new solar investigation"""
    try:
        investigation = await service.start_investigation(request)
        return InvestigationResponse(
            investigation=investigation,
            message=f"Investigation started for plant {request.plant_id} from {request.start_date} to {request.end_date}",
        )
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


# @router.post("/{investigation_id}/continue")
# async def continue_investigation(
#     investigation_id: str,
#     message: dict,  # {"message": "user message"}
#     service: SimplifiedInvestigationService = Depends(
#         get_simplified_investigation_service
#     ),
# ):
#     """Continue investigation with user input"""
#     try:
#         investigation = await service.get_investigation(investigation_id)
#         if not investigation:
#             raise HTTPException(status_code=404, detail="Investigation not found")

#         user_message = message.get("message", "")
#         if not user_message:
#             raise HTTPException(status_code=400, detail="Message is required")

#         response = await service.continue_investigation(investigation_id, user_message)
#         return {"response": response}
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error continuing investigation {investigation_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")


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
        return {"success": True, "message": "Investigation deleted successfully"}
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

@router.post("/{investigation_id}/message")
async def post_message(
    investigation_id: str,
    message: dict,  # {"message": "user message"}
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Post a message to the investigation chat"""
    try:
        # check if there is @workorder, if there is redirect to workorder agent
        if "@workorder-agent" in message["content"]:
            await service.redirect_to_workorder_agent(investigation_id, message["content"])
        else:
            await service.continue_investigation(investigation_id, message["content"])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error posting message for investigation {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{investigation_id}/stream")
async def stream_investigation_events(
    investigation_id: str,
    service: SimplifiedInvestigationService = Depends(
        get_simplified_investigation_service
    ),
):
    """Stream investigation events using Server-Sent Events (SSE)"""
    try:
        # Check if investigation exists
        investigation = await service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")

        async def event_generator():
            """Generate SSE events for investigation progress"""
            try:
                # Send initial status
                initial_data = {
                    "type": "status",
                    "investigation_id": investigation_id,
                    "status": investigation.status.value,
                    "timestamp": investigation.updated_at.isoformat(),
                    "ui_summary": investigation.ui_summary,
                }
                yield f"data: {json.dumps(initial_data)}\n\n"

                # Stream events from the service
                async for event in service.get_event_stream(investigation_id):
                    yield f"data: {json.dumps(event)}\n\n"

            except Exception as e:
                logger.error(f"Error in SSE event generator: {e}")
                from datetime import datetime

                error_data = {
                    "type": "error",
                    "investigation_id": investigation_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error setting up SSE stream for investigation {investigation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")

