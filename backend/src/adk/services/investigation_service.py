"""Investigation service using pure database storage via Google ADK DatabaseSessionService"""

import logging
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
import json
import asyncio

from adk.agents.solar_investigation_agent import get_solar_investigation_agent
from adk.config.settings import get_settings
from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
)
from adk.services.plant_service import PlantService

logger = logging.getLogger(__name__)


class InvestigationService:
    """Service for managing solar investigations using pure database storage"""

    def __init__(self):
        # Get application settings
        settings = get_settings()

        # Use persistent database storage for everything
        self.session_service = DatabaseSessionService(db_url=settings.database_url)

        # Application constants
        self.app_name = "solar_investigation_api"

        # Service dependencies
        self.plant_service = PlantService()

        # In-memory cache for active runners only
        self.runners: Dict[str, Runner] = {}

        logger.info(
            f"Initialized InvestigationService with pure database storage: {settings.database_url}"
        )

    def _get_session_id(self, investigation_id: str) -> str:
        """Generate consistent session ID for investigation"""
        return f"session_{investigation_id}"

    async def _create_investigation(
        self, request: InvestigationRequest
    ) -> Investigation:
        """Create a new solar investigation and store in database"""
        # Validate that the plant exists
        plant = await self.plant_service.get_plant_by_id(request.plant_id)
        if not plant:
            raise ValueError(f"Plant with ID {request.plant_id} not found")

        # Validate date range (max 5 days)
        date_diff = (request.end_date - request.start_date).days
        if date_diff < 0:
            raise ValueError("End date must be after start date")
        if date_diff > 5:
            raise ValueError("Date range cannot exceed 5 days")

        # Create investigation object
        investigation = Investigation(
            plant_id=request.plant_id,
            start_date=request.start_date,
            end_date=request.end_date,
            additional_notes=request.additional_notes,
            status=InvestigationStatus.PENDING,
        )

        # Store investigation metadata in session state
        session_id = self._get_session_id(investigation.id)
        investigation_data = {
            "investigation": {
                "id": investigation.id,
                "plant_id": investigation.plant_id,
                "start_date": investigation.start_date.isoformat(),
                "end_date": investigation.end_date.isoformat(),
                "additional_notes": investigation.additional_notes,
                "status": investigation.status.value,
                "user_id": investigation.user_id,
                "created_at": investigation.created_at.isoformat(),
                "updated_at": investigation.updated_at.isoformat(),
                "completed_at": None,
                "result": None,
                "error_message": None,
                "session_id": session_id,
            }
        }

        # Create session in database with investigation metadata
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=investigation.user_id,
            session_id=session_id,
            state=investigation_data,
        )

        logger.info(
            f"Created investigation {investigation.id} for plant: {request.plant_id} "
            f"({request.start_date} to {request.end_date})"
        )
        return investigation

    async def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get investigation by ID from database"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id="api_user",  # Default user for now
                session_id=session_id,
            )

            if not session or not session.state.get("investigation"):
                return None

            # Reconstruct Investigation object from session state
            inv_data = session.state["investigation"]
            investigation = Investigation(
                id=inv_data["id"],
                plant_id=inv_data["plant_id"],
                start_date=date.fromisoformat(inv_data["start_date"]),
                end_date=date.fromisoformat(inv_data["end_date"]),
                additional_notes=inv_data.get("additional_notes"),
                status=InvestigationStatus(inv_data["status"]),
                user_id=inv_data["user_id"],
                created_at=datetime.fromisoformat(inv_data["created_at"]),
                updated_at=datetime.fromisoformat(inv_data["updated_at"]),
                completed_at=(
                    datetime.fromisoformat(inv_data["completed_at"])
                    if inv_data.get("completed_at")
                    else None
                ),
                result=inv_data.get("result"),
                error_message=inv_data.get("error_message"),
                session_id=inv_data["session_id"],
            )

            return investigation

        except Exception as e:
            logger.error(f"Error retrieving investigation {investigation_id}: {e}")
            return None

    async def list_investigations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Investigation]:
        """List all investigations from database"""
        try:
            # List all sessions for our app
            sessions_response = await self.session_service.list_sessions(
                app_name=self.app_name,
                user_id="api_user",
            )

            investigations = []
            for session_summary in sessions_response.sessions:
                # Get full session to access state
                session = await self.session_service.get_session(
                    app_name=self.app_name,
                    user_id=session_summary.user_id,
                    session_id=session_summary.id,
                )

                if session and session.state.get("investigation"):
                    inv_data = session.state["investigation"]
                    investigation = Investigation(
                        id=inv_data["id"],
                        plant_id=inv_data["plant_id"],
                        start_date=date.fromisoformat(inv_data["start_date"]),
                        end_date=date.fromisoformat(inv_data["end_date"]),
                        additional_notes=inv_data.get("additional_notes"),
                        status=InvestigationStatus(inv_data["status"]),
                        user_id=inv_data["user_id"],
                        created_at=datetime.fromisoformat(inv_data["created_at"]),
                        updated_at=datetime.fromisoformat(inv_data["updated_at"]),
                        completed_at=(
                            datetime.fromisoformat(inv_data["completed_at"])
                            if inv_data.get("completed_at")
                            else None
                        ),
                        result=inv_data.get("result"),
                        error_message=inv_data.get("error_message"),
                        session_id=inv_data["session_id"],
                    )
                    investigations.append(investigation)

            # Sort by creation time (newest first)
            investigations.sort(key=lambda x: x.created_at, reverse=True)
            return investigations[offset : offset + limit]

        except Exception as e:
            logger.error(f"Error listing investigations: {e}")
            return []

    async def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Start running the investigation using Google ADK agent"""
        # Create investigation
        investigation = await self._create_investigation(request)

        try:
            # Update status to running
            await self._update_investigation_status(
                investigation.id, InvestigationStatus.RUNNING
            )

            # Create agent and runner
            agent = get_solar_investigation_agent()
            runner = Runner(
                agent=agent,
                app_name=self.app_name,
                session_service=self.session_service,
            )

            # Store runner for this investigation
            self.runners[investigation.id] = runner

            # Get plant information for initial message
            plant = await self.plant_service.get_plant_by_id(investigation.plant_id)
            plant_name = plant.plant_name if plant else "Unknown Plant"

            # The initial system message will be automatically stored in the database
            # when we send it through the runner, so no manual chat history management needed

            logger.info(f"Started investigation {investigation.id}")
            investigation.status = InvestigationStatus.RUNNING

        except Exception as e:
            await self._update_investigation_status(
                investigation.id, InvestigationStatus.FAILED, error_message=str(e)
            )
            logger.error(f"Failed to start investigation {investigation.id}: {e}")
            raise

        return investigation

    async def run_investigation_step(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Run a step of the investigation with user message"""
        investigation = await self.get_investigation(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        runner = self.runners.get(investigation_id)
        if not runner:
            # Recreate runner if not in memory
            agent = get_solar_investigation_agent()
            runner = Runner(
                agent=agent,
                app_name=self.app_name,
                session_service=self.session_service,
            )
            self.runners[investigation_id] = runner

        try:
            # Prepare query for agent
            plant = await self.plant_service.get_plant_by_id(investigation.plant_id)
            query = {
                "plant_id": investigation.plant_id,
                "plant_name": plant.plant_name if plant else "Unknown Plant",
                "plant_type": plant.type if plant else "Unknown",
                "start_date": investigation.start_date.isoformat(),
                "end_date": investigation.end_date.isoformat(),
                "additional_notes": investigation.additional_notes,
                "user_message": user_message,
            }

            # Send to agent - ADK will automatically store messages in database
            user_content = types.Content(
                role="user", parts=[types.Part(text=json.dumps(query))]
            )

            final_response = "No response received"
            session_id = investigation.session_id or self._get_session_id(
                investigation_id
            )

            async for event in runner.run_async(
                user_id=investigation.user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or "Empty response"

            # Update investigation timestamp
            await self._update_investigation_status(
                investigation_id, investigation.status
            )

            return final_response

        except Exception as e:
            logger.error(
                f"Error running investigation step for {investigation_id}: {e}"
            )
            raise

    async def complete_investigation(
        self, investigation_id: str, result: Dict[str, Any]
    ) -> Investigation:
        """Mark investigation as completed with results"""
        investigation = await self.get_investigation(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # Update investigation in database
        await self._update_investigation_status(
            investigation_id,
            InvestigationStatus.COMPLETED,
            result=result,
            completed_at=datetime.now(),
        )

        # Clean up runner
        if investigation_id in self.runners:
            del self.runners[investigation_id]

        logger.info(f"Completed investigation {investigation_id}")

        # Return updated investigation
        return await self.get_investigation(investigation_id)

    async def get_chat_history(self, investigation_id: str) -> List[AgentMessage]:
        """Get chat history for an investigation from database events"""
        try:
            session_id = self._get_session_id(investigation_id)

            # Get session with events
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id="api_user",
                session_id=session_id,
            )

            if not session:
                return []

            # Convert ADK events to our AgentMessage format
            messages = []
            for event in session.events:
                # Determine message type based on event author
                if event.author == "user":
                    message_type = AgentMessageType.USER
                elif event.author == "agent":
                    message_type = AgentMessageType.AGENT
                elif event.author == "system":
                    message_type = AgentMessageType.SYSTEM
                else:
                    message_type = AgentMessageType.THINKING

                # Extract content from event
                content = ""
                if (
                    event.content
                    and hasattr(event.content, "parts")
                    and event.content.parts
                ):
                    content = event.content.parts[0].text or ""

                message = AgentMessage(
                    id=event.id,
                    investigation_id=investigation_id,
                    message_type=message_type,
                    content=content,
                    metadata={
                        "event_author": event.author,
                        "timestamp": event.timestamp,
                    },
                    timestamp=event.timestamp,
                )
                messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"Error retrieving chat history for {investigation_id}: {e}")
            return []

    async def handle_decision(
        self, investigation_id: str, decision: str, decision_type: str
    ) -> str:
        """Handle human decision during investigation"""
        investigation = await self.get_investigation(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # The decision will be automatically stored when we send it through the runner
        runner = self.runners.get(investigation_id)
        if runner:
            decision_content = types.Content(
                role="user",
                parts=[types.Part(text=f"Decision ({decision_type}): {decision}")],
            )

            # Send decision through ADK - it will store automatically
            session_id = investigation.session_id or self._get_session_id(
                investigation_id
            )
            async for event in runner.run_async(
                user_id=investigation.user_id,
                session_id=session_id,
                new_message=decision_content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    return event.content.parts[0].text or "Decision acknowledged"

        return "Decision received"

    async def _update_investigation_status(
        self,
        investigation_id: str,
        status: InvestigationStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update investigation status in database"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id="api_user",
                session_id=session_id,
            )

            if session and session.state.get("investigation"):
                # Update investigation data in session state
                inv_data = session.state["investigation"]
                inv_data["status"] = status.value
                inv_data["updated_at"] = datetime.now().isoformat()

                if error_message:
                    inv_data["error_message"] = error_message
                if result:
                    inv_data["result"] = result
                if completed_at:
                    inv_data["completed_at"] = completed_at.isoformat()

                # Update session state - ADK will persist this
                session.state["investigation"] = inv_data

        except Exception as e:
            logger.error(
                f"Error updating investigation status for {investigation_id}: {e}"
            )

    async def add_thinking_message(
        self,
        investigation_id: str,
        title: str,
        description: str,
        level: str = "major",  # "major" or "detailed"
        step_type: str = "reasoning",  # "reasoning", "decision", "handoff", "tool_call", etc.
    ) -> AgentMessage:
        """Add a thinking/reasoning message to show agent's thought process"""
        # For database-only approach, thinking messages are handled by ADK automatically
        # We can optionally send them through the runner if needed
        try:
            runner = self.runners.get(investigation_id)
            if runner:
                content = f"{title}: {description}"
                thinking_content = types.Content(
                    role="user",  # ADK will classify this appropriately
                    parts=[types.Part(text=f"[THINKING] {content}")],
                )

                session_id = self._get_session_id(investigation_id)
                async for event in runner.run_async(
                    user_id="api_user",
                    session_id=session_id,
                    new_message=thinking_content,
                ):
                    # Just process the event - ADK stores it automatically
                    pass

            # Return a mock AgentMessage for compatibility
            return AgentMessage(
                investigation_id=investigation_id,
                message_type=AgentMessageType.THINKING,
                content=f"{title}: {description}",
                metadata={
                    "thinking": True,
                    "level": level,
                    "step_type": step_type,
                    "title": title,
                },
            )

        except Exception as e:
            logger.error(f"Error adding thinking message: {e}")
            # Return a basic message even if storing fails
            return AgentMessage(
                investigation_id=investigation_id,
                message_type=AgentMessageType.THINKING,
                content=f"{title}: {description}",
                metadata={"error": str(e)},
            )

    @property
    def investigations(self) -> Dict[str, Investigation]:
        """Legacy compatibility property - returns empty dict since we use database"""
        logger.warning(
            "investigations property accessed - this is legacy, use list_investigations() instead"
        )
        return {}

    async def get_investigations_count(self) -> int:
        """Get total count of investigations"""
        try:
            sessions_response = await self.session_service.list_sessions(
                app_name=self.app_name,
                user_id="api_user",
            )
            return len(sessions_response.sessions)
        except Exception as e:
            logger.error(f"Error getting investigations count: {e}")
            return 0
