"""Simplified Investigation service leveraging Google ADK best practices"""

import logging
import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any, cast
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

# from google.genai.adk import RunConfig, StreamingMode
from google.genai import types

from adk.agents.solar_investigation_agent import get_solar_investigation_agent
from adk.agents.ui_summarizer_agent import generate_ui_summary

# TODO: implement this
# from adk.agents.workorder_agent import get_workorder_agent
from adk.config.settings import get_settings
from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
)
from adk.services.plant_service import PlantService

# WebSocket support removed - using SSE-only for simpler architecture
# from adk.services.broadcast_service import broadcast_service

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

        # Event queues for SSE streaming
        self.event_queues: Dict[str, asyncio.Queue] = {}

        logger.info(
            f"Initialized SimplifiedInvestigationService with ADK: {settings.database_url}"
        )

    def _get_session_id(self, investigation_id: str) -> str:
        """Generate session ID for investigation"""
        return f"investigation_{investigation_id}"

    def _create_ui_summary_callback(self, investigation_id: str):
        """Create after_agent_callback for UI summary generation"""

        async def after_agent_callback(*args, **kwargs):
            """Process agent output and generate UI summary - flexible signature"""
            try:
                # Handle different callback signatures that Google ADK might use
                callback_context = None
                agent_output = None

                # Try to extract parameters from args
                if len(args) >= 1:
                    callback_context = args[0]
                if len(args) >= 2:
                    agent_output = args[1]

                # Try kwargs
                if not agent_output:
                    agent_output = kwargs.get("agent_output") or kwargs.get("output")
                if not callback_context:
                    callback_context = kwargs.get("callback_context") or kwargs.get(
                        "context"
                    )

                # If still no agent_output, try to extract from callback_context
                if not agent_output and callback_context:
                    agent_output = getattr(
                        callback_context, "agent_output", None
                    ) or getattr(callback_context, "output", None)

                logger.debug(
                    f"Callback called with args: {len(args)}, kwargs: {list(kwargs.keys())}"
                )

                if (
                    not agent_output
                    or not hasattr(agent_output, "parts")
                    or not agent_output.parts
                ):
                    logger.warning(
                        f"No valid agent output available for UI summary generation in investigation {investigation_id}"
                    )
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
                if callback_context and hasattr(callback_context, "state"):
                    callback_context.state["ui_summary"] = ui_summary
                    callback_context.state["full_content"] = full_content
                    callback_context.state["last_update"] = datetime.now().isoformat()
                else:
                    logger.warning(
                        f"No callback_context.state available for investigation {investigation_id}"
                    )

                # Broadcast to SSE clients (WebSocket removed)
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

    async def _process_investigation_async(
        self, investigation: Investigation
    ) -> None:  # TODO: add agent here
        """Process investigation using ADK best practices"""
        try:
            # Send initial investigation started event
            await self._queue_sse_event(
                investigation.id,
                {
                    "type": "investigation_started",
                    "investigation_id": investigation.id,
                    "message": "Investigation processing started",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Update status to running
            await self._update_status(investigation.id, InvestigationStatus.RUNNING)

            # Create agent with after_agent_callback for UI processing
            # AND workorder agent as sub-agent
            agent = get_solar_investigation_agent(
                output_key="investigation_result",  # ADK will auto-save to state
                after_agent_callback=self._create_ui_summary_callback(investigation.id),
                # TODO: Add workorder agent when implemented later
                # workorder_agent=get_workorder_agent(),
            )  # swap to out agent

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

            # Create RunConfig for SSE streaming (word-by-word)
            # run_config = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=200)

            # Process with ADK (handles events, state, callbacks automatically)
            final_response = None
            event_count = 0
            async for event in runner.run_async(
                user_id=self.default_user_id,
                session_id=session_id,
                new_message=user_content,
                # run_config=run_config,
            ):
                event_count += 1
                logger.info(
                    f"Processing ADK event #{event_count} for investigation {investigation.id}: {event.id}"
                )

                # Check for workorder agent requests
                # await self._handle_sub_agent_requests(investigation.id, event) #TODO: if got time

                # Broadcast real-time updates
                await self._broadcast_event(investigation.id, event)

                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or ""

            logger.info(
                f"Completed ADK processing for investigation {investigation.id}, processed {event_count} events"
            )

            # Determine final status
            if final_response and len(final_response.strip()) > 10:
                await self._update_status(
                    investigation.id, InvestigationStatus.COMPLETED
                )
            else:
                await self._update_status(
                    investigation.id, InvestigationStatus.REQUIRES_ATTENTION
                )

            # Send completion event
            await self._queue_sse_event(
                investigation.id,
                {
                    "type": "completion",
                    "investigation_id": investigation.id,
                    "status": (
                        InvestigationStatus.COMPLETED.value
                        if final_response and len(final_response.strip()) > 10
                        else InvestigationStatus.REQUIRES_ATTENTION.value
                    ),
                    "result": final_response if final_response else None,
                    "timestamp": datetime.now().isoformat(),
                },
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

    async def _handle_sub_agent_requests(self, investigation_id: str, event):
        """Handle sub-agent requests like @workorder-agent"""
        try:
            if not event.content or not event.content.parts:
                return

            content = event.content.parts[0].text or ""

            # Check for workorder agent request
            if "@workorder-agent" in content.lower():
                await self._handle_workorder_request(investigation_id, content)

        except Exception as e:
            logger.error(f"Error handling sub-agent request: {e}")

    async def _handle_workorder_request(self, investigation_id: str, content: str):
        """Handle workorder agent request"""
        try:
            # Broadcast workorder request
            await self._broadcast_workorder_status(
                investigation_id,
                "workorder_requested",
                "Main agent requesting workorder creation...",
            )

            # TODO: implement this when workorder agent is ready
            # workorder_result = await self._call_workorder_agent(investigation_id, content)

            # For now, simulate workorder creation
            workorder_result = (
                "workorder created and assigned to maintenance team #MT-001"
            )

            # Store in session state
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                workorders = session.state.get("workorders", [])
                workorders.append(
                    {
                        "id": f"WO-{len(workorders) + 1}",
                        "status": "created",
                        "description": content,
                        "assigned_to": "maintenance team #MT-001",
                        "created_at": datetime.now().isoformat(),
                    }
                )

                # ADK best practice: Update state directly, let ADK persist
                session.state["workorders"] = workorders

            # Broadcast workorder completion
            await self._broadcast_workorder_status(
                investigation_id, "workorder_created", workorder_result
            )

            # Continue investigation with workorder result
            await self.continue_investigation(
                investigation_id, f"Workorder agent result: {workorder_result}"
            )

        except Exception as e:
            logger.error(f"Error handling workorder request: {e}")
            await self._broadcast_workorder_status(
                investigation_id,
                "workorder_failed",
                f"Failed to create workorder: {str(e)}",
            )

    async def _broadcast_workorder_status(
        self, investigation_id: str, status: str, message: str
    ):
        """Queue workorder status updates for SSE (WebSocket removed for simplicity)"""
        try:
            # Queue for SSE only
            await self._queue_sse_event(
                investigation_id,
                {
                    "type": "workorder_status",
                    "investigation_id": investigation_id,
                    "status": status,
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Error broadcasting workorder status: {e}")

    async def create_workorder_manually(
        self, investigation_id: str, workorder_request: str
    ) -> str:
        """Allow user to create workorder manually via UI button"""
        try:
            # TODO: implement this when workorder agent is ready
            # return await self._call_workorder_agent(investigation_id, workorder_request)

            # For now, simulate workorder creation
            workorder_result = (
                f"workorder created manually: {workorder_request[:100]}..."
            )

            # Store in session state
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                workorders = session.state.get("workorders", [])
                workorders.append(
                    {
                        "id": f"WO-MANUAL-{len(workorders) + 1}",
                        "status": "created",
                        "description": workorder_request,
                        "type": "manual",
                        "created_at": datetime.now().isoformat(),
                    }
                )

                # ADK best practice: Update state directly, let ADK persist
                session.state["workorders"] = workorders

            # Broadcast manual workorder creation
            await self._broadcast_workorder_status(
                investigation_id, "manual_workorder_created", workorder_result
            )

            return workorder_result

        except Exception as e:
            logger.error(f"Error creating manual workorder: {e}")
            raise ValueError(f"Failed to create workorder: {str(e)}")

    async def get_workorders(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Get all workorders for an investigation"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                return session.state.get("workorders", [])
            return []

        except Exception as e:
            logger.error(f"Error getting workorders: {e}")
            return []

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
        """Update investigation status using proper ADK event pattern"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            if session:
                # According to ADK docs, update session state directly
                # The session service handles persistence automatically
                session.state["status"] = status.value
                session.state["updated_at"] = datetime.now().isoformat()
                if error_message:
                    session.state["error_message"] = error_message
                if status == InvestigationStatus.COMPLETED:
                    session.state["completed_at"] = datetime.now().isoformat()

                logger.info(
                    f"Updated investigation {investigation_id} status to {status.value}"
                )

                # Queue status update for SSE
                await self._queue_sse_event(
                    investigation_id,
                    {
                        "type": "status_update",
                        "investigation_id": investigation_id,
                        "status": status.value,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Error updating status: {e}")

    async def _broadcast_event(self, investigation_id: str, event):
        """Queue ADK event for SSE streams (WebSocket removed for simplicity)"""
        try:
            if event.content and event.content.parts:
                message = {
                    "id": event.id,
                    "investigation_id": investigation_id,
                    "message_type": "agent" if event.author != "user" else "user",
                    "content": event.content.parts[0].text,
                    "timestamp": datetime.now().isoformat(),
                }

                # Queue for SSE only
                await self._queue_sse_event(
                    investigation_id,
                    {
                        "type": "message",
                        "investigation_id": investigation_id,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")

    async def _broadcast_ui_update(
        self, investigation_id: str, ui_summary: str, full_content: str
    ):
        """Queue UI summary update for SSE (WebSocket removed for simplicity)"""
        try:
            # Queue for SSE only
            await self._queue_sse_event(
                investigation_id,
                {
                    "type": "ui_update",
                    "investigation_id": investigation_id,
                    "ui_summary": ui_summary,
                    "full_content": full_content,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Error broadcasting UI update: {e}")

    def _create_investigation_prompt(self, investigation: Investigation, plant) -> str:
        """Create investigation prompt with workorder agent capability
        #TODO: update orchestrator prompt
        """
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
        
        AVAILABLE CAPABILITIES:
        - If you need to create work orders for maintenance or installation tasks, you can request @workorder-agent
        - You can pause the investigation at any time to wait for external information
        - You can request human decisions when needed
        
        Please provide a comprehensive solar feasibility assessment including site analysis, 
        technical assessment, financial analysis, implementation roadmap, and clear recommendations.
        
        If you identify any maintenance needs or installation requirements that need work orders, 
        please mention @workorder-agent with the specific requirements.
        """

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

        # Create RunConfig for SSE streaming (word-by-word)
        # run_config = RunConfig(streaming_mode=StreamingMode.SSE, max_llm_calls=200)

        final_response = ""
        async for event in runner.run_async(
            user_id=self.default_user_id,
            session_id=session_id,
            new_message=user_content,
            # run_config=run_config,
        ):
            # Check for workorder agent requests
            await self._handle_sub_agent_requests(investigation_id, event)

            await self._broadcast_event(investigation_id, event)

            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text or ""

        return final_response or ""

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

                # ADK best practice: Update state directly, let ADK persist
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

    async def get_event_stream(self, investigation_id: str):
        """Get async generator for SSE events"""
        # Create event queue for this investigation if not exists
        if investigation_id not in self.event_queues:
            self.event_queues[investigation_id] = asyncio.Queue()

        queue = self.event_queues[investigation_id]

        # Send initial connection event
        initial_event = {
            "type": "connected",
            "investigation_id": investigation_id,
            "timestamp": datetime.now().isoformat(),
            "message": "SSE stream connected successfully",
        }

        try:
            # Send the initial event first
            yield initial_event

            while True:
                # Wait for next event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event

                    # Break on completion events
                    if event.get("type") == "completion":
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat on timeout
                    yield {
                        "type": "heartbeat",
                        "investigation_id": investigation_id,
                        "timestamp": datetime.now().isoformat(),
                    }
        finally:
            # Cleanup queue when done
            if investigation_id in self.event_queues:
                del self.event_queues[investigation_id]

    async def _queue_sse_event(self, investigation_id: str, event_data: Dict[str, Any]):
        """Queue an event for SSE streaming"""
        if investigation_id in self.event_queues:
            try:
                await self.event_queues[investigation_id].put(event_data)
            except Exception as e:
                logger.error(f"Error queuing SSE event: {e}")


# Singleton instance
_simplified_service_instance: Optional[SimplifiedInvestigationService] = None


def get_simplified_investigation_service() -> SimplifiedInvestigationService:
    """Get singleton instance"""
    global _simplified_service_instance
    if _simplified_service_instance is None:
        _simplified_service_instance = SimplifiedInvestigationService()

    return cast(SimplifiedInvestigationService, _simplified_service_instance)
