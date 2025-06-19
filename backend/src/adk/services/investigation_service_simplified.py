"""Simplified Investigation service leveraging Google ADK best practices"""

import logging
import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any, cast
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

from adk.agents.solar_investigation_agent import get_solar_investigation_agent
from adk.agents.ui_summarizer_agent import generate_ui_summary
from adk.config.settings import get_settings
from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
)
from adk.services.plant_service import PlantService
from adk.services.broadcast_service import broadcast_service

logger = logging.getLogger(__name__)


class SimplifiedInvestigationService:
    """Simplified service leveraging ADK session management and callbacks"""

    def __init__(self):
        settings = get_settings()

        # Use ADK session service as primary storage
        self.session_service = DatabaseSessionService(db_url=settings.database_url)

        # Application constants
        self.app_name = "solar_investigation_api"
        self.default_user_id = "api_user"

        # Dependencies
        self.plant_service = PlantService()

        # Single runner instance per investigation (no complex runner management)
        self.active_runners: Dict[str, Runner] = {}

        logger.info(
            f"Initialized SimplifiedInvestigationService with ADK: {settings.database_url}"
        )

    def _get_session_id(self, investigation_id: str) -> str:
        """Generate session ID for investigation"""
        return f"investigation_{investigation_id}"

    def _create_ui_summary_callback(self, investigation_id: str):
        """Create after_agent_callback for UI summary generation"""

        async def after_agent_callback(callback_context, agent_output):
            """Process agent output and generate UI summary"""
            try:
                if not agent_output or not agent_output.parts:
                    return None

                # Get the full agent response
                full_content = agent_output.parts[0].text if agent_output.parts else ""

                # Generate UI summary using the summarizer agent
                try:
                    ui_summary = await generate_ui_summary(full_content)
                    logger.info(
                        f"Generated UI summary for investigation {investigation_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to generate UI summary: {e}, using fallback"
                    )
                    # Fallback to simple truncation
                    ui_summary = (
                        f"Summary: {full_content[:100]}..."
                        if len(full_content) > 100
                        else full_content
                    )

                # Store UI summary in session state using ADK best practices
                callback_context.state["ui_summary"] = ui_summary
                callback_context.state["full_content"] = full_content
                callback_context.state["last_update"] = datetime.now().isoformat()

                # Broadcast to WebSocket clients
                await self._broadcast_ui_update(
                    investigation_id, ui_summary, full_content
                )

                logger.info(
                    f"UI callback completed for investigation {investigation_id}"
                )

                # Return None to use original agent output
                return None

            except Exception as e:
                logger.error(f"Error in after_agent_callback: {e}")
                return None

        return after_agent_callback

    async def create_investigation(
        self, request: InvestigationRequest
    ) -> Investigation:
        """Create new investigation using ADK session"""
        # Validate plant exists
        plant = await self.plant_service.get_plant_by_id(request.plant_id)
        if not plant:
            raise ValueError(f"Plant with ID {request.plant_id} not found")

        # Validate date range
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
            parent_id=request.parent_id,
            ui_summary=None,  # Will be populated by callback
        )

        # Use ADK session state for investigation metadata
        session_id = self._get_session_id(investigation.id)
        initial_state = {
            "investigation_id": investigation.id,
            "plant_id": investigation.plant_id,
            "start_date": investigation.start_date.isoformat(),
            "end_date": investigation.end_date.isoformat(),
            "additional_notes": investigation.additional_notes,
            "status": investigation.status.value,
            "created_at": investigation.created_at.isoformat(),
            "updated_at": investigation.updated_at.isoformat(),
        }

        # Create ADK session (this handles all storage automatically)
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=self.default_user_id,
            session_id=session_id,
            state=initial_state,
        )

        logger.info(f"Created investigation {investigation.id}")
        return investigation

    async def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get investigation from ADK session"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if not session:
                return None

            # Reconstruct Investigation from ADK session state
            state = session.state

            investigation = Investigation(
                id=state["investigation_id"],
                plant_id=state["plant_id"],
                start_date=date.fromisoformat(state["start_date"]),
                end_date=date.fromisoformat(state["end_date"]),
                additional_notes=state.get("additional_notes"),
                status=InvestigationStatus(state["status"]),
                created_at=datetime.fromisoformat(state["created_at"]),
                updated_at=datetime.fromisoformat(state["updated_at"]),
                completed_at=(
                    datetime.fromisoformat(state["completed_at"])
                    if state.get("completed_at")
                    else None
                ),
                # Add UI data from session state
                ui_summary=state.get("ui_summary"),
                result=state.get("result"),
                error_message=state.get("error_message"),
            )

            return investigation

        except Exception as e:
            logger.error(f"Error retrieving investigation {investigation_id}: {e}")
            return None

    async def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Start investigation with background processing"""
        # Create investigation
        investigation = await self.create_investigation(request)

        # Start background processing
        asyncio.create_task(self._process_investigation_async(investigation))

        return investigation

    async def _process_investigation_async(self, investigation: Investigation) -> None:
        """Process investigation using ADK best practices"""
        try:
            # Update status to running
            await self._update_status(investigation.id, InvestigationStatus.RUNNING)

            # Create agent with after_agent_callback for UI processing
            agent = get_solar_investigation_agent(
                output_key="investigation_result",  # ADK will auto-save to state
                after_agent_callback=self._create_ui_summary_callback(investigation.id),
            )

            # Create runner
            runner = Runner(
                agent=agent,
                app_name=self.app_name,
                session_service=self.session_service,
            )

            # Store runner
            self.active_runners[investigation.id] = runner

            # Get plant info and create prompt
            plant = await self.plant_service.get_plant_by_id(investigation.plant_id)
            initial_prompt = self._create_investigation_prompt(investigation, plant)

            # Run agent - ADK handles everything automatically
            session_id = self._get_session_id(investigation.id)
            user_content = types.Content(
                role="user", parts=[types.Part(text=initial_prompt)]
            )

            # Process with ADK (handles events, state, callbacks automatically)
            final_response = None
            async for event in runner.run_async(
                user_id=self.default_user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                # Broadcast real-time updates
                await self._broadcast_event(investigation.id, event)

                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or ""

            # Determine final status
            if final_response and len(final_response.strip()) > 10:
                await self._update_status(
                    investigation.id, InvestigationStatus.COMPLETED
                )
            else:
                await self._update_status(
                    investigation.id, InvestigationStatus.REQUIRES_ATTENTION
                )

            logger.info(f"Completed investigation {investigation.id}")

        except Exception as e:
            await self._update_status(
                investigation.id, InvestigationStatus.FAILED, str(e)
            )
            logger.error(f"Failed investigation {investigation.id}: {e}")
        finally:
            # Cleanup
            if investigation.id in self.active_runners:
                del self.active_runners[investigation.id]

    async def continue_investigation(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Continue investigation with user input"""
        runner = self.active_runners.get(investigation_id)
        if not runner:
            # Recreate runner if needed
            agent = get_solar_investigation_agent(
                output_key="investigation_result",
                after_agent_callback=self._create_ui_summary_callback(investigation_id),
            )
            runner = Runner(
                agent=agent,
                app_name=self.app_name,
                session_service=self.session_service,
            )
            self.active_runners[investigation_id] = runner

        # Send user message
        session_id = self._get_session_id(investigation_id)
        user_content = types.Content(role="user", parts=[types.Part(text=user_message)])

        final_response = ""
        async for event in runner.run_async(
            user_id=self.default_user_id,
            session_id=session_id,
            new_message=user_content,
        ):
            await self._broadcast_event(investigation_id, event)

            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text or ""

        return final_response or ""

    async def get_chat_history(self, investigation_id: str) -> List[AgentMessage]:
        """Get chat history from ADK session events"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if not session:
                return []

            messages = []
            for event in session.events:
                if (
                    event.content
                    and event.content.parts
                    and event.content.parts[0].text
                ):
                    message_type = (
                        AgentMessageType.USER
                        if event.author == "user"
                        else AgentMessageType.AGENT
                    )
                    content = event.content.parts[0].text or ""

                    message = AgentMessage(
                        id=event.id,
                        investigation_id=investigation_id,
                        message_type=message_type,
                        content=content,
                        timestamp=(
                            datetime.fromtimestamp(event.timestamp)
                            if event.timestamp
                            else datetime.now()
                        ),
                        metadata={"author": event.author},
                        ui_summary=None,  # Can be populated later if needed
                        ui_state=None,
                        show_full_content=False,
                    )
                    messages.append(message)

            return messages

        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def list_investigations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Investigation]:
        """List investigations from ADK sessions"""
        try:
            sessions_response = await self.session_service.list_sessions(
                app_name=self.app_name,
                user_id=self.default_user_id,
            )

            investigations = []
            for session_summary in sessions_response.sessions:
                session = await self.session_service.get_session(
                    app_name=self.app_name,
                    user_id=session_summary.user_id,
                    session_id=session_summary.id,
                )

                if session and session.state.get("investigation_id"):
                    investigation = await self.get_investigation(
                        session.state["investigation_id"]
                    )
                    if investigation:
                        investigations.append(investigation)

            investigations.sort(key=lambda x: x.created_at, reverse=True)
            return investigations[offset : offset + limit]

        except Exception as e:
            logger.error(f"Error listing investigations: {e}")
            return []

    async def delete_investigation(self, investigation_id: str) -> bool:
        """Delete investigation"""
        try:
            session_id = self._get_session_id(investigation_id)

            # Remove active runner
            if investigation_id in self.active_runners:
                del self.active_runners[investigation_id]

            # Delete ADK session
            await self.session_service.delete_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            return True
        except Exception as e:
            logger.error(f"Error deleting investigation: {e}")
            return False

    async def _update_status(
        self,
        investigation_id: str,
        status: InvestigationStatus,
        error_message: Optional[str] = None,
    ):
        """Update investigation status using ADK session state"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                # Update state directly (ADK will handle persistence)
                session.state["status"] = status.value
                session.state["updated_at"] = datetime.now().isoformat()
                if error_message:
                    session.state["error_message"] = error_message
                if status == InvestigationStatus.COMPLETED:
                    session.state["completed_at"] = datetime.now().isoformat()

                # Broadcast status update
                await broadcast_service.broadcast_status_update(
                    investigation_id, status.value
                )

        except Exception as e:
            logger.error(f"Error updating status: {e}")

    async def _broadcast_event(self, investigation_id: str, event):
        """Broadcast ADK event to WebSocket clients"""
        try:
            if event.content and event.content.parts:
                message = {
                    "id": event.id,
                    "investigation_id": investigation_id,
                    "message_type": "agent" if event.author != "user" else "user",
                    "content": event.content.parts[0].text,
                    "timestamp": datetime.now().isoformat(),
                }
                await broadcast_service.broadcast_new_message(investigation_id, message)
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")

    async def _broadcast_ui_update(
        self, investigation_id: str, ui_summary: str, full_content: str
    ):
        """Broadcast UI summary update"""
        try:
            await broadcast_service.broadcast_ui_summary_update(
                investigation_id, ui_summary, full_content
            )
        except Exception as e:
            logger.error(f"Error broadcasting UI update: {e}")

    def _create_investigation_prompt(self, investigation: Investigation, plant) -> str:
        """Create investigation prompt"""
        plant_name = plant.plant_name if plant else "Unknown Plant"

        return f"""
        Please begin a comprehensive solar installation feasibility investigation for:
        
        PLANT INFORMATION:
        - Plant ID: {investigation.plant_id}
        - Plant Name: {plant_name}
        - Plant Type: {plant.type if plant else "Unknown"}
        
        INVESTIGATION SCOPE:
        - Analysis Period: {investigation.start_date} to {investigation.end_date}
        - Duration: {(investigation.end_date - investigation.start_date).days + 1} days
        
        ADDITIONAL CONTEXT:
        {investigation.additional_notes or "No additional specifications provided."}
        
        Please provide a comprehensive solar feasibility assessment including site analysis, 
        technical assessment, financial analysis, implementation roadmap, and clear recommendations.
        """

    async def handle_decision(
        self, investigation_id: str, decision: str, decision_type: str = "continue"
    ) -> str:
        """Handle human decision during investigation - simplified wrapper"""
        return await self.continue_investigation(
            investigation_id, f"Decision ({decision_type}): {decision}"
        )

    async def run_investigation_step(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Run investigation step - alias for continue_investigation"""
        return await self.continue_investigation(investigation_id, user_message)

    async def add_thinking_message(
        self, investigation_id: str, thinking_content: str, step_name: str = "Thinking"
    ):
        """Add thinking message - simplified implementation using session state"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                # Store thinking message in session state for later retrieval
                thinking_messages = session.state.get("thinking_messages", [])
                thinking_messages.append(
                    {
                        "step_name": step_name,
                        "content": thinking_content,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                session.state["thinking_messages"] = thinking_messages

                logger.info(
                    f"Added thinking message for investigation {investigation_id}: {step_name}"
                )

        except Exception as e:
            logger.error(f"Error adding thinking message: {e}")

    async def update_investigation_status(
        self,
        investigation_id: str,
        status: InvestigationStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update investigation status - wrapper for _update_status"""
        try:
            await self._update_status(investigation_id, status, error_message)
            return True
        except Exception as e:
            logger.error(f"Error updating investigation status: {e}")
            return False


# Singleton instance
_simplified_service_instance: Optional[SimplifiedInvestigationService] = None


def get_simplified_investigation_service() -> SimplifiedInvestigationService:
    """Get singleton instance"""
    global _simplified_service_instance
    if _simplified_service_instance is None:
        _simplified_service_instance = SimplifiedInvestigationService()

    return cast(SimplifiedInvestigationService, _simplified_service_instance)
