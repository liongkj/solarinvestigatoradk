"""Investigation API Controllers for Solar Investigator ADK - Simplified"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import json
from datetime import datetime
import uuid
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from adk.agents.solar_investigation_agent import get_solar_investigation_agent

logger = logging.getLogger(__name__)

# Router for investigation endpoints
router = APIRouter(prefix="/api/investigations", tags=["investigations"])

# Global session service for the API
session_service = InMemorySessionService()


# Request Models
class SolarInvestigationRequest(BaseModel):
    """Request model for solar investigation."""

    address: str
    monthly_usage: float
    property_type: str = "residential"


@router.post("/solar-feasibility")
async def investigate_solar_feasibility(request: SolarInvestigationRequest):
    """
    Investigate solar installation feasibility for a property.

    This endpoint uses the simplified solar investigation agent to analyze
    feasibility and provide recommendations.
    """
    try:
        # Create agent and runner
        agent = get_solar_investigation_agent()
        runner = Runner(
            agent=agent,
            app_name="solar_investigation_api",
            session_service=session_service,
        )

        # Create a session for this request
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        user_id = "api_user"

        await session_service.create_session(
            app_name="solar_investigation_api", user_id=user_id, session_id=session_id
        )

        # Prepare the query in the expected format
        query = {
            "address": request.address,
            "monthly_usage": request.monthly_usage,
            "property_type": request.property_type,
        }

        # Send query to agent
        user_content = types.Content(
            role="user", parts=[types.Part(text=json.dumps(query))]
        )

        final_response = "No response received"
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text

        return {
            "success": True,
            "investigation_id": session_id,
            "result": final_response,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error in solar feasibility investigation: {e}")
        raise HTTPException(status_code=500, detail=f"Investigation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for the investigation service."""
    try:
        # Test that we can create an agent
        agent = get_solar_investigation_agent()
        return {
            "status": "healthy",
            "agent_name": agent.name,
            "tools_available": len(agent.tools),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/demo")
async def demo_investigation():
    """Demo endpoint to test the solar investigation agent."""
    demo_request = SolarInvestigationRequest(
        address="123 Main St, San Jose, CA 95120",
        monthly_usage=850,
        property_type="residential",
    )

    return await investigate_solar_feasibility(demo_request)
