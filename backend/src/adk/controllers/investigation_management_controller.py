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
from adk.services.investigation_service import (
    get_investigation_service,
    InvestigationService,
)

logger = logging.getLogger(__name__)

# Router for investigation management endpoints
router = APIRouter(prefix="/api/investigations", tags=["investigation-management"])


@router.get("/", response_model=InvestigationListResponse)
async def list_investigations(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
):
    """
    List all investigations with pagination.

    Returns a paginated list of all solar investigations.
    """
    investigation_service = get_investigation_service()
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


@router.post("/{investigation_id}/simulate-thinking")
async def simulate_agent_thinking(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Simulate agent thinking process for testing the UI.
    This endpoint adds sample thinking messages to demonstrate the system of thought.
    """
    try:
        # Check if investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        # Add simulated thinking messages
        await investigation_service.add_thinking_message(
            investigation_id,
            "🤔 Analyzing user request",
            "Starting comprehensive analysis of solar production anomalies",
            "major",
            "reasoning",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "📊 Loading historical data",
            "Retrieving production data from June 10-14, 2025 for Plant-002",
            "detailed",
            "tool_call",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "⚠️ Anomaly detected",
            "Production dropped 15% on June 12th. Need to investigate root cause.",
            "major",
            "decision",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "🌤️ Checking weather correlation",
            "Calling weather API to determine if weather caused the production drop",
            "detailed",
            "tool_call",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "🔄 Transferring to Alert Agent",
            "Weather was clear. Handing off to Alert Agent for equipment failure analysis",
            "major",
            "handoff",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "🔧 Equipment diagnostic initiated",
            "Alert Agent is running diagnostic checks on inverters and panels",
            "detailed",
            "agent_processing",
        )

        await investigation_service.add_thinking_message(
            investigation_id,
            "✅ Analysis complete",
            "All agents have completed their analysis. Generating final report.",
            "major",
            "completion",
        )

        return {
            "investigation_id": investigation_id,
            "message": "Simulated thinking process added successfully",
            "thinking_messages_added": 7,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error simulating thinking for {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to simulate thinking: {str(e)}"
        )


@router.post("/{investigation_id}/retry", response_model=InvestigationResponse)
async def retry_investigation(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Retry a failed or cancelled investigation.

    Marks the original investigation as FAILED and creates a new investigation
    with the same parameters but linked as a retry.
    """
    try:
        # Get the original investigation
        original_investigation = await investigation_service.get_investigation(
            investigation_id
        )
        if not original_investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        # Mark original investigation as failed
        success = await investigation_service.update_investigation_status(
            investigation_id,
            InvestigationStatus.FAILED,
            "Marked as failed due to retry",
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update original investigation status",
            )

        # Create retry request with same parameters
        retry_request = InvestigationRequest(
            plant_id=original_investigation.plant_id,
            start_date=original_investigation.start_date,
            end_date=original_investigation.end_date,
            additional_notes=original_investigation.additional_notes,
            parent_id=investigation_id,  # Link to original investigation
        )

        # Start the retry investigation
        retry_investigation = await investigation_service.start_investigation(
            retry_request
        )

        return InvestigationResponse(
            investigation=retry_investigation,
            message=f"Investigation retried successfully. Original investigation {investigation_id} marked as failed.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying investigation {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retry investigation: {str(e)}"
        )


@router.delete("/{investigation_id}")
async def delete_investigation(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Delete a specific investigation by ID.

    Removes the investigation and all associated session data.
    If the investigation is running, it will be stopped first.
    """
    try:
        # Check if investigation exists
        investigation = await investigation_service.get_investigation(investigation_id)
        if not investigation:
            raise HTTPException(
                status_code=404, detail=f"Investigation {investigation_id} not found"
            )

        # Delete the investigation
        success = await investigation_service.delete_investigation(investigation_id)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete investigation {investigation_id}",
            )

        return {
            "success": True,
            "message": f"Investigation {investigation_id} deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting investigation {investigation_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete investigation: {str(e)}"
        )


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
            "investigations_count": await investigation_service.get_investigations_count(),
            "active_sessions": len(investigation_service.runners),
        }

    except Exception as e:
        logger.error(f"Investigation service health check failed: {e}")
        raise HTTPException(
            status_code=503, detail=f"Investigation service unhealthy: {str(e)}"
        )


@router.get("/{investigation_id}/ui-summary")
async def get_investigation_ui_summary(
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    Get UI summary for an investigation.

    Returns the latest UI summary and full content for the investigation.
    """
    try:
        # Get session to access UI state
        session_id = investigation_service._get_session_id(investigation_id)
        session = await investigation_service.session_service.get_session(
            app_name=investigation_service.app_name,
            user_id=investigation_service.default_user_id,
            session_id=session_id,
        )

        if not session:
            raise HTTPException(status_code=404, detail="Investigation not found")

        ui_state = session.state.get("ui_state", {})

        return {
            "investigation_id": investigation_id,
            "ui_summary": ui_state.get("latest_ui_summary", "No summary available"),
            "full_content": ui_state.get("latest_full_content", "No content available"),
            "last_update": ui_state.get("last_summary_update"),
            "has_ui_data": bool(ui_state.get("latest_ui_summary")),
        }

    except Exception as e:
        logger.error(
            f"Error getting UI summary for investigation {investigation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to get UI summary")
