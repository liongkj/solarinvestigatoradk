"""Investigation Management API Controllers for Solar Investigator ADK"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List
import logging

from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationListResponse,
    InvestigationStatus,
    ChatHistoryResponse,
    DecisionRequest,
    DecisionResponse,
)
from adk.services.investigation_service import InvestigationService

logger = logging.getLogger(__name__)

# Router for investigation management endpoints
router = APIRouter(prefix="/api/investigations", tags=["investigation-management"])


@router.get("/", response_model=InvestigationListResponse)
async def list_investigations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    List all investigations with pagination.

    Returns a paginated list of all solar investigations.
    """
    try:
        offset = (page - 1) * size
        investigations = await investigation_service.list_investigations(
            limit=size, offset=offset
        )

        # Get total count (for simplicity, using len of all investigations)
        all_investigations = await investigation_service.list_investigations(
            limit=1000, offset=0
        )
        total = len(all_investigations)

        return InvestigationListResponse(
            investigations=investigations, total=total, page=page, size=size
        )

    except Exception as e:
        logger.error(f"Error listing investigations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list investigations: {str(e)}"
        )


@router.post("/", response_model=InvestigationResponse)
async def start_new_investigation(
    request: InvestigationRequest,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Start a new solar investigation.

    Creates a new investigation and triggers the Google ADK agent to begin
    the solar feasibility analysis process.
    """
    try:

        # Start the investigation process
        investigation = await investigation_service.start_investigation(request)

        return InvestigationResponse(
            investigation=investigation,
            message=f"Investigation started for plant {request.plant_id} "
            f"from {request.start_date} to {request.end_date}",
        )

    except ValueError as e:
        logger.error(f"Validation error starting investigation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting investigation: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start investigation: {str(e)}"
        )


@router.get("/{investigation_id}")
async def get_investigation(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Get a specific investigation by ID.

    Returns the investigation details including current status and results.
    """
    try:
        investigation = await investigation_service.get_investigation(investigation_id)

        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        return investigation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting investigation {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get investigation: {str(e)}"
        )


@router.get("/{investigation_id}/chat", response_model=ChatHistoryResponse)
async def get_investigation_chat_history(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Get agent chat history for an investigation.

    Returns the complete chat history between the user and the ADK agent
    for this investigation, including tool calls and system messages.
    """
    try:
        # Check if investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        # Get chat history
        messages = await investigation_service.get_chat_history(investigation_id)

        return ChatHistoryResponse(
            investigation_id=investigation_id,
            messages=messages,
            total_messages=len(messages),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat history for {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get chat history: {str(e)}"
        )


@router.post("/{investigation_id}/decide", response_model=DecisionResponse)
async def handle_human_decision(
    investigation_id: str,
    request: DecisionRequest,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Handle human decisions during investigation.

    Allows humans to provide input, decisions, or modifications to the
    ongoing investigation process. The ADK agent will process the decision
    and continue accordingly.
    """
    try:
        # Check if investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        # Check if investigation is in a state that can accept decisions
        if investigation.status not in [
            InvestigationStatus.RUNNING,
            InvestigationStatus.PENDING,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Investigation {investigation_id} is not active (status: {investigation.status})",
            )

        # Handle the decision
        response_message = await investigation_service.handle_decision(
            investigation_id, request.decision, request.decision_type
        )

        # If it's a continue decision, run the next step
        if request.decision_type == "continue":
            try:
                agent_response = await investigation_service.run_investigation_step(
                    investigation_id, request.decision
                )
                response_message = agent_response
            except Exception as e:
                logger.warning(f"Could not run investigation step: {e}")
                response_message = f"Decision received: {request.decision}. Agent processing may continue asynchronously."

        return DecisionResponse(
            investigation_id=investigation_id,
            decision_accepted=True,
            message=response_message,
            next_steps=(
                ["Check chat history for agent responses"]
                if request.decision_type == "continue"
                else None
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling decision for {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to handle decision: {str(e)}"
        )


@router.post("/{investigation_id}/message")
async def send_message_to_investigation(
    investigation_id: str,
    message: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Send a message to the investigation agent.

    Allows sending messages directly to the running investigation agent.
    """
    try:
        # Check if investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        if investigation.status != InvestigationStatus.RUNNING:
            raise HTTPException(
                status_code=400,
                detail=f"Investigation {investigation_id} is not running",
            )

        # Send message to agent
        response = await investigation_service.run_investigation_step(
            investigation_id, message
        )

        return {
            "investigation_id": investigation_id,
            "message_sent": message,
            "agent_response": response,
            "timestamp": investigation.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message to investigation {investigation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


# Health check endpoint specifically for investigation service
@router.get("/health/service")
async def investigation_service_health(
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """Health check for the investigation service"""
    try:
        # Just verify the service can handle the request structure
        return {
            "status": "healthy",
            "service": "investigation_service",
            "investigations_count": len(investigation_service.investigations),
            "active_sessions": len(investigation_service.runners),
        }

    except Exception as e:
        logger.error(f"Investigation service health check failed: {e}")
        raise HTTPException(
            status_code=503, detail=f"Investigation service unhealthy: {str(e)}"
        )
