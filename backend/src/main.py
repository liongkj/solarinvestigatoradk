"""
Main FastAPI application for Solar Investigator ADK
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging

from google.adk.cli.fast_api import get_fast_api_app
from adk.config import settings
from adk.controllers import investigation_management_router
from adk.controllers.plant_controller import router as plant_router

# WebSocket removed for simplified SSE-only architecture
# from adk.controllers.websocket_controller import router as websocket_router


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting Solar Investigator ADK application...")

    # ADK services initialization is handled by get_fast_api_app

    yield

    logger.info("Shutting down Solar Investigator ADK application...")


# Create ADK FastAPI app with built-in agent endpoints and DatabaseSessionService
app = get_fast_api_app(
    agents_dir="adk/agents",  # Directory containing our agents
    web=False,  # Set to True if you want ADK's built-in web interface
    session_service_uri=settings.database_url,  # Use PostgreSQL for persistent sessions
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include our custom investigation routers
app.include_router(investigation_management_router)
app.include_router(plant_router)
# WebSocket router removed for simplified SSE-only architecture


# Add our custom endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Solar Investigator ADK Backend",
        "version": settings.app_version,
        "status": "running",
        "adk_enabled": True,
    }


# Health check endpoint for production
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring"""
    return {"status": "healthy", "service": "solar-investigator-backend"}


@app.post("/api/investigate")
async def start_investigation(request: dict):
    """
    Test endpoint to start a solar investigation using our ADK agent.
    This is a simple test implementation.
    """
    try:
        from adk.agents import create_solar_agent

        # Create the agent
        agent = create_solar_agent()

        # For now, return a mock response
        # In the full implementation, this would use ADK's Runner
        return {
            "status": "investigation_started",
            "agent": agent.name,
            "query": request.get("query", "No query provided"),
            "message": "Solar investigation agent created successfully!",
            "next_steps": [
                "Connect to ADK Runner",
                "Stream events via SSE",
                "Process investigation workflow",
            ],
        }
    except Exception as e:
        logger.error(f"Failed to start investigation: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to start investigation", "details": str(e)},
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info" if not settings.debug else "debug",
    )
