"""Simplified Investigation service leveraging Google ADK best practices"""

import logging
import asyncio
from datetime import datetime, date
from typing import List, Optional, Dict, Any, cast
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from adk.problem_finder.agent import root_agent
from adk.agents.ui_summarizer_agent import generate_ui_summary
from google.adk.events import Event, EventActions
from google.genai.types import Part, Content
from datetime import timedelta
import time

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
            plant_name=plant.plant_name if plant else "Unknown Plant",
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
            "plant_name": investigation.plant_name,
            "inverter_date_to_check": None,
            "inverter_device_id_and_capacity_peak": None,
            "date_requested": None,
            "date_today": None,
            "alarm_agent_output": None,
            "detailed_inverter_performance_agent_output": None,
            "detailed_plant_timeseries_agent_output": None,
            "daily_pr_agent_output": None,
            "problematic_detailed_inverter_performance": [],
            "problematic_five_minutes_pr": [],
        }
        # TODO: TO be retrieved using context.state later

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
                plant_name=state.get("plant_name", "Unknown Plant"),
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
            # agent = create_root_agent(
            #     investigation=investigation,
            #     # output_key="investigation_result",  # ADK will auto-save to state
            #     # after_agent_callback=self._create_ui_summary_callback(investigation.id),
            #     # # TODO: Add workorder agent when implemented later
            #     # # workorder_agent=get_workorder_agent(),
            # )  # swap to out agent

            agent = root_agent

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
            # No special RunConfig needed for text streaming - ADK events naturally provide incremental updates
            final_response = None
            event_count = 0
            accumulated_text = ""
            last_active_agent = None
            last_status_sent = None
            async for event in runner.run_async(
                user_id=self.default_user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                event_count += 1
                logger.info(
                    f"Processing ADK event #{event_count} for investigation {investigation.id}: {event.id}"
                )

                # Check for workorder agent requests
                # await self._handle_sub_agent_requests(investigation.id, event) #TODO: if got time

                # Handle streaming events for real-time updates with text accumulation
                current_text = await self._handle_streaming_event(
                    investigation.id, event, accumulated_text
                )
                if current_text is not None:
                    accumulated_text = current_text

                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or ""

                # Send status update only when agent changes (not for every event)
                if event.author != last_active_agent:
                    last_active_agent = event.author

                    # Determine meaningful status based on agent and event content
                    if event.author == "user":
                        current_status = "Processing user input"

                    elif event.get_function_calls():
                        # Agent is calling tools
                        tool_names = [call.name for call in event.get_function_calls()]
                        tool_name = tool_names[0] if tool_names else "unknown tool"
                        current_status = f"Using {tool_name}"
                        map_tool_names = {
                            "list_inverters_for_plant": "Looking up inverters for current plant..."
                        }
                        if tool_name in map_tool_names:
                            tool_name_friendly = map_tool_names[tool_name]
                            event_data = {
                                "investigation_id": investigation.id,
                                # "timestamp": datetime.now().isoformat(),
                                "type": "streaming_text_chunk",
                                "content": tool_name_friendly,
                                "full_content": tool_name_friendly,
                                "partial": True,
                            }

                            # Queue the chunk
                            await self._queue_sse_event(investigation.id, event_data)
                            state_changes = {
                                "task_status": "active",
                            }
                            # actions_with_update = EventActions(
                            #     state_delta=state_changes
                            # )
                            # system_event = Event(
                            #     invocation_id="inv_login_update",
                            #     author="system",  # Or 'agent', 'tool' etc.
                            #     actions=actions_with_update,
                            #     timestamp=time.time(),
                            #     # content might be None or represent the action taken
                            # )
                            # session = await self.session_service.get_session(
                            #     app_name=self.app_name,
                            #     user_id=self.default_user_id,
                            #     session_id=self._get_session_id(investigation.id),
                            # )
                            # await self.session_service.append_event(
                            #     session, system_event
                            # )
                            # add to event state
                    elif (
                        event.content
                        and event.content.parts
                        and event.content.parts[0].text
                    ):
                        # Agent is generating text/analysis
                        text_preview = event.content.parts[0].text[:50].strip()
                        if text_preview:
                            current_status = f"Agent {event.author} analyzing data"
                        else:
                            current_status = f"Agent {event.author} processing"
                    else:
                        current_status = f"Agent {event.author} working"

                    # Only send if status actually changed
                    if current_status != last_status_sent:
                        logger.info(
                            f"Sending progress update for {investigation.id}: '{current_status}'"
                        )
                        await self._queue_sse_event(
                            investigation.id,
                            {
                                "type": "progress_update",  # Changed from status_update
                                "investigation_id": investigation.id,
                                "current_activity": current_status,  # Descriptive status
                                "formal_status": "running",  # Keep formal status
                                "timestamp": datetime.now().isoformat(),
                            },
                        )
                        last_status_sent = current_status

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

        # async def _handle_sub_agent_requests(self, investigation_id: str, event):
        """Handle sub-agent requests like @workorder-agent"""
        try:
            if not event.content or not event.content.parts:
                return

            content = event.content.parts[0].text or ""

            # Check for workorder agent request
            if "@workorder-agent" in content.lower():
                await self._handle_workorder_request(investigation.id, content)

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

            # Broadcast deletion event before actually deleting
            await self._queue_sse_event(
                investigation_id,
                {
                    "type": "investigation_deleted",
                    "investigation_id": investigation_id,
                    "message": "Investigation has been deleted",
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Delete ADK session
            await self.session_service.delete_session(
                app_name=self.app_name,
                user_id=self.default_user_id,
                session_id=session_id,
            )

            # Clean up event queue for this investigation
            if investigation_id in self.event_queues:
                del self.event_queues[investigation_id]

            logger.info(f"Successfully deleted investigation {investigation_id}")
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
        Investigate plant based on the following details:
        
        PLANT INFORMATION:
        - Plant ID: {investigation.plant_id}
        - Plant Name: {plant_name}
        - Plant Type: {plant.type if plant else "Unknown"}
        
        INVESTIGATION SCOPE:
        - Analysis Period: {investigation.start_date} to {investigation.end_date}
        - Duration: {(investigation.end_date - investigation.start_date).days + 1} days
        
        ADDITIONAL CONTEXT:
        {investigation.additional_notes or "No additional specifications provided."}
        
        
        """

    async def continue_investigation(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Continue investigation with user input. Not implemented yet"""
        runner = self.active_runners.get(investigation_id)

        if not runner:
            # Recreate runner if needed
            agent = root_agent
            runner = Runner(
                agent=agent,
                app_name=self.app_name,
                session_service=self.session_service,
            )
            self.active_runners[investigation_id] = runner

        # Send user message
        session_id = self._get_session_id(investigation_id)
        user_content = types.Content(role="user", parts=[types.Part(text=user_message)])

        # No special RunConfig needed for text streaming - handle events naturally
        final_response = ""
        accumulated_text = ""

        async for event in runner.run_async(
            user_id=self.default_user_id,
            session_id=session_id,
            new_message=user_content,
        ):
            # Check for workorder agent requests
            await self._handle_sub_agent_requests(investigation_id, event)

            # Handle streaming events for real-time updates with text accumulation
            current_text = await self._handle_streaming_event(
                investigation_id, event, accumulated_text
            )
            if current_text is not None:
                accumulated_text = current_text

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

    async def _handle_streaming_event(
        self, investigation_id: str, event, accumulated_text: str = ""
    ):
        """Handle ADK streaming events and broadcast to SSE clients - returns updated accumulated text"""
        try:
            # Extract event details
            event_data = {
                "investigation_id": investigation_id,
                "timestamp": datetime.now().isoformat(),
                "event_id": getattr(event, "id", None),
                "author": getattr(event, "author", None),
            }

            current_accumulated = accumulated_text

            # Handle different event types - focus on text content streaming
            if event.content and event.content.parts:
                if event.get_function_calls():
                    # Tool call request
                    event_data.update(
                        {
                            "type": "tool_call_request",
                            "tool_calls": [
                                call.name for call in event.get_function_calls()
                            ],
                            "partial": False,
                        }
                    )
                elif event.get_function_responses():
                    # Tool result
                    event_data.update(
                        {
                            "type": "tool_result",
                            "tool_responses": len(event.get_function_responses()),
                            "partial": False,
                        }
                    )
                elif event.content.parts[0].text:
                    # Text message - detect streaming by comparing with accumulated text
                    text_content = event.content.parts[0].text

                    # If this text is longer than what we had before, it's a streaming chunk
                    if len(text_content) > len(
                        accumulated_text
                    ) and text_content.startswith(accumulated_text):
                        # This is a streaming chunk - send it in smaller debounced chunks
                        new_chunk = text_content[len(accumulated_text) :]
                        current_accumulated = text_content

                        # Send the new chunk in smaller pieces for better streaming UX
                        await self._send_debounced_chunks(
                            investigation_id, new_chunk, text_content
                        )

                        logger.info(
                            f"📝 Streaming chunk detected for {investigation_id}: '{new_chunk[:50]}...' (total: {len(text_content)} chars)"
                        )

                        # Don't queue the event here - it's handled by _send_debounced_chunks
                        return current_accumulated

                    elif not event.is_final_response():
                        # This might be a complete intermediate message - also debounce it
                        current_accumulated = text_content

                        # Send as debounced chunks
                        await self._send_debounced_chunks(
                            investigation_id, text_content, text_content
                        )

                        logger.info(
                            f"📝 Intermediate text for {investigation_id}: '{text_content[:50]}...' (total: {len(text_content)} chars)"
                        )

                        # Don't queue the event here - it's handled by _send_debounced_chunks
                        return current_accumulated

                    else:
                        # This is the final complete message
                        event_data.update(
                            {
                                "type": "complete_text_message",
                                "content": text_content,
                                "partial": False,
                            }
                        )
                        current_accumulated = text_content
                        logger.info(
                            f"✅ Final complete message for {investigation_id}: '{text_content[:50]}...' (total: {len(text_content)} chars)"
                        )

                else:
                    # Other content (code result, etc.)
                    event_data.update(
                        {
                            "type": "other_content",
                            "content_type": type(event.content.parts[0]).__name__,
                            "partial": False,
                        }
                    )
            elif event.actions and (
                event.actions.state_delta or event.actions.artifact_delta
            ):
                # State/Artifact Update
                event_data.update(
                    {
                        "type": "state_artifact_update",
                        "has_state_delta": bool(event.actions.state_delta),
                        "has_artifact_delta": bool(event.actions.artifact_delta),
                        "partial": False,
                    }
                )
            else:
                # Control signal or other
                event_data.update(
                    {
                        "type": "control_signal",
                        "turn_complete": getattr(event, "turn_complete", None),
                        "partial": False,
                    }
                )

            # Queue the event for SSE streaming
            await self._queue_sse_event(investigation_id, event_data)

            logger.debug(
                f"Streamed event type: {event_data['type']} for investigation {investigation_id}"
            )

            # Return the updated accumulated text
            return current_accumulated

        except Exception as e:
            logger.error(
                f"Error handling streaming event for investigation {investigation_id}: {e}"
            )
            # Send error event
            error_event = {
                "type": "streaming_error",
                "investigation_id": investigation_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "partial": False,
            }
            await self._queue_sse_event(investigation_id, error_event)
            return accumulated_text  # Return unchanged on error

    async def _send_debounced_chunks(
        self, investigation_id: str, new_text: str, full_content: str
    ):
        """Send text content in smaller debounced chunks for better streaming UX"""
        try:
            # Configuration for chunking
            CHUNK_SIZE = 20  # Send 30 characters at a time for better visual streaming
            DELAY_MS = 10  # 80ms delay between chunks

            # Split new text into chunks
            chunks = []
            for i in range(0, len(new_text), CHUNK_SIZE):
                chunk = new_text[i : i + CHUNK_SIZE]
                chunks.append(chunk)

            # Send chunks with delays
            accumulated_sent = ""
            for i, chunk in enumerate(chunks):
                accumulated_sent += chunk

                # Calculate current full content position
                full_content_so_far = full_content[
                    : len(full_content) - len(new_text) + len(accumulated_sent)
                ]

                event_data = {
                    "investigation_id": investigation_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "streaming_text_chunk",
                    "content": chunk,
                    "full_content": full_content_so_far,
                    "partial": True,
                    "chunk_info": {
                        "chunk_index": i + 1,
                        "total_chunks": len(chunks),
                        "chunk_size": len(chunk),
                    },
                }

                # Queue the chunk
                await self._queue_sse_event(investigation_id, event_data)

                # Add delay between chunks (except for the last one)
                if i < len(chunks) - 1:
                    await asyncio.sleep(DELAY_MS / 1000.0)

                # logger.debug(
                #     f"📤 Sent chunk {i + 1}/{len(chunks)} for {investigation_id}: '{chunk[:20]}...'"
                # )

            logger.info(
                f"📝 Completed debounced streaming for {investigation_id}: {len(chunks)} chunks, {len(new_text)} chars"
            )

        except Exception as e:
            logger.error(f"Error sending debounced chunks for {investigation_id}: {e}")
            # Fallback: send as single chunk
            await self._queue_sse_event(
                investigation_id,
                {
                    "investigation_id": investigation_id,
                    "timestamp": datetime.now().isoformat(),
                    "type": "streaming_text_chunk",
                    "content": new_text,
                    "full_content": full_content,
                    "partial": True,
                },
            )


# Singleton instance
_simplified_service_instance: Optional[SimplifiedInvestigationService] = None


def get_simplified_investigation_service() -> SimplifiedInvestigationService:
    """Get singleton instance"""
    global _simplified_service_instance
    if _simplified_service_instance is None:
        _simplified_service_instance = SimplifiedInvestigationService()

    return cast(SimplifiedInvestigationService, _simplified_service_instance)
