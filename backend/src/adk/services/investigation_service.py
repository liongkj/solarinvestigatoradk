"""Investigation service using pure database storage via Google ADK DatabaseSessionService"""

import logging
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.events import Event, EventActions
from google.genai import types
import json
import asyncio
import time

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
        self.default_user_id = "api_user"  # Consistent user ID for all investigations

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
            parent_id=request.parent_id,
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
                "parent_id": investigation.parent_id,
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
            user_id=self.default_user_id,  # Use consistent user ID
            session_id=session_id,
            state=investigation_data,
        )

        logger.info(
            f"Created investigation {investigation.id} for plant: {request.plant_id} "
            f"({request.start_date} to {request.end_date})"
        )
        return investigation

    async def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get investigation by ID from database with rich ADK session data"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
                session_id=session_id,
            )

            if not session or not session.state.get("investigation"):
                return None

            # Reconstruct Investigation object from session state
            inv_data = session.state["investigation"]

            # Extract additional metadata from ADK session
            agent_stats = self._calculate_agent_stats(session)

            investigation = Investigation(
                id=inv_data["id"],
                plant_id=inv_data["plant_id"],
                start_date=date.fromisoformat(inv_data["start_date"]),
                end_date=date.fromisoformat(inv_data["end_date"]),
                additional_notes=inv_data.get("additional_notes"),
                status=InvestigationStatus(inv_data["status"]),
                user_id=inv_data["user_id"],
                parent_id=inv_data.get("parent_id"),
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
                # Add agent stats for frontend display
                agent_stats=agent_stats,
            )

            return investigation

        except Exception as e:
            logger.error(f"Error retrieving investigation {investigation_id}: {e}")
            return None

    def _calculate_agent_stats(self, session) -> Dict[str, Any]:
        """Calculate agent interaction statistics from ADK session events"""
        stats = {
            "total_events": len(session.events),
            "user_messages": 0,
            "agent_responses": 0,
            "thinking_steps": 0,
            "tool_calls": 0,
            "tools_used": [],
            "total_agents": set(),
            "session_duration": None,
            "last_activity": None,
            "progress_steps": [],
        }

        first_event_time = None
        last_event_time = None

        for event in session.events:
            # Track timing
            if event.timestamp:
                if first_event_time is None:
                    first_event_time = event.timestamp
                last_event_time = event.timestamp

            # Count by author
            if event.author == "user":
                stats["user_messages"] += 1
            elif event.author == "agent":
                stats["agent_responses"] += 1
                if hasattr(event, "agent_name") and event.agent_name:
                    stats["total_agents"].add(event.agent_name)
            elif event.author == "system":
                pass  # System messages don't count towards thinking
            else:
                stats["thinking_steps"] += 1

            # Count tool usage
            if hasattr(event, "tool_calls") and event.tool_calls:
                for tool_call in event.tool_calls:
                    stats["tool_calls"] += 1
                    tool_name = (
                        getattr(tool_call.function, "name", str(tool_call))
                        if hasattr(tool_call, "function")
                        else str(tool_call)
                    )
                    if tool_name not in stats["tools_used"]:
                        stats["tools_used"].append(tool_name)

            # Track progress steps
            if hasattr(event, "step") and event.step:
                step_info = {
                    "step_number": getattr(
                        event.step, "number", len(stats["progress_steps"]) + 1
                    ),
                    "step_name": getattr(
                        event.step, "name", f"Step {len(stats['progress_steps']) + 1}"
                    ),
                    "timestamp": event.timestamp,
                    "completed": getattr(event, "turn_complete", False),
                }
                stats["progress_steps"].append(step_info)

        # Calculate session duration
        if first_event_time and last_event_time:
            # Assuming timestamps are datetime objects or can be converted
            try:
                if isinstance(first_event_time, (int, float)):
                    duration = last_event_time - first_event_time
                    stats["session_duration"] = duration
                    stats["last_activity"] = last_event_time
                else:
                    # Handle string timestamps or other formats
                    stats["last_activity"] = str(last_event_time)
            except Exception as e:
                logger.warning(f"Could not calculate session duration: {e}")

        # Convert set to list for JSON serialization
        stats["total_agents"] = list(stats["total_agents"])

        return stats

    async def list_investigations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Investigation]:
        """List all investigations from database"""
        try:
            # List all sessions for our app
            sessions_response = await self.session_service.list_sessions(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
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
        """Start a new solar investigation with immediate ADK agent initialization"""
        # Create the investigation record and session
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

            initial_prompt = f"""
                Please begin a comprehensive solar installation feasibility investigation for the following solar plant:

                PLANT INFORMATION:
                - Plant ID: {investigation.plant_id}
                - Plant Name: {plant_name}
                - Plant Type: {plant.type if plant else "Unknown"}
                - Location: {getattr(plant, 'location', 'Location data unavailable')}

                INVESTIGATION SCOPE:
                - Analysis Period: {investigation.start_date.isoformat()} to {investigation.end_date.isoformat()}
                - Duration: {(investigation.end_date - investigation.start_date).days + 1} days
                - Focus: Solar installation feasibility and optimization

                ADDITIONAL CONTEXT:
                {investigation.additional_notes or "No additional specifications provided."}

                REQUIRED ANALYSIS:
                Please provide a comprehensive solar feasibility assessment that includes:

                1. SITE SUITABILITY ANALYSIS
                - Solar irradiation potential for the specified period
                - Physical site constraints and opportunities
                - Environmental factors affecting installation

                2. TECHNICAL ASSESSMENT
                - Estimated solar system size and configuration
                - Expected energy production potential
                - Equipment recommendations and specifications

                3. FINANCIAL ANALYSIS
                - Installation cost estimates
                - Projected energy savings and payback period
                - Available incentives, rebates, and financing options

                4. IMPLEMENTATION ROADMAP
                - Key milestones and timeline
                - Permit and regulatory requirements
                - Risk assessment and mitigation strategies

                5. RECOMMENDATIONS
                - Clear go/no-go recommendation with reasoning
                - Alternative options or optimizations
                - Next steps for proceeding

                Please start your investigation now and provide your initial findings.
            """

            # Send initial prompt to agent - ADK will automatically store this conversation
            user_content = types.Content(
                role="user", parts=[types.Part(text=initial_prompt)]
            )

            session_id = self._get_session_id(investigation.id)

            # Process agent response with retry logic
            max_retries = 1
            for attempt in range(max_retries + 1):
                try:
                    final_response = "No response received"
                    async for event in runner.run_async(
                        user_id=self.default_user_id,  # Use consistent user ID
                        session_id=session_id,
                        new_message=user_content,
                    ):
                        if (
                            event.is_final_response()
                            and event.content
                            and event.content.parts
                        ):
                            final_response = (
                                event.content.parts[0].text or "Empty response"
                            )

                    # Determine final status based on agent response
                    if final_response and len(final_response.strip()) > 10:
                        # Check if response indicates completion or needs attention
                        response_lower = final_response.lower()
                        if any(
                            keyword in response_lower
                            for keyword in ["complete", "concluded", "final", "summary"]
                        ):
                            investigation.status = InvestigationStatus.COMPLETED
                            await self._update_investigation_status(
                                investigation.id, InvestigationStatus.COMPLETED
                            )
                        else:
                            # Default to requiring attention for user follow-up
                            investigation.status = (
                                InvestigationStatus.REQUIRES_ATTENTION
                            )
                            await self._update_investigation_status(
                                investigation.id, InvestigationStatus.REQUIRES_ATTENTION
                            )
                    else:
                        # Empty or minimal response - requires attention
                        investigation.status = InvestigationStatus.REQUIRES_ATTENTION
                        await self._update_investigation_status(
                            investigation.id, InvestigationStatus.REQUIRES_ATTENTION
                        )

                    logger.info(
                        f"Successfully started investigation {investigation.id} with status {investigation.status.value}"
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    logger.error(
                        f"Attempt {attempt + 1} failed for investigation {investigation.id}: {e}"
                    )
                    if attempt == max_retries:
                        # Final attempt failed - notify frontend
                        await self._update_investigation_status(
                            investigation.id,
                            InvestigationStatus.FAILED,
                            error_message=f"Failed to start investigation after {max_retries + 1} attempts: {str(e)}",
                        )
                        raise
                    # Wait before retry
                    await asyncio.sleep(1)

            logger.info(f"Started investigation {investigation.id}")

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
            # Send user message directly to agent - ADK will automatically store messages
            user_content = types.Content(
                role="user", parts=[types.Part(text=user_message)]
            )

            final_response = "No response received"
            session_id = investigation.session_id or self._get_session_id(
                investigation_id
            )

            async for event in runner.run_async(
                user_id=self.default_user_id,  # Use consistent user ID
                session_id=session_id,
                new_message=user_content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or "Empty response"

            # Update investigation timestamp using proper ADK events
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
        updated_investigation = await self.get_investigation(investigation_id)
        if not updated_investigation:
            raise ValueError(
                f"Investigation {investigation_id} not found after completion"
            )
        return updated_investigation

    async def get_chat_history(self, investigation_id: str) -> List[AgentMessage]:
        """Get rich chat history for investigation from DatabaseSessionService with full ADK event data"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
                session_id=session_id,
            )

            if not session:
                logger.info(f"No session found for investigation {investigation_id}")
                return []

            messages = []
            for event in session.events:
                # Extract rich metadata from ADK event
                event_metadata = self._extract_event_metadata(event)

                # Determine message type with more granular classification
                message_type = self._determine_message_type(event, event_metadata)

                # Extract content with rich formatting
                content = self._extract_event_content(event, event_metadata)

                # Build comprehensive metadata including ADK-specific data
                comprehensive_metadata = {
                    "event_id": event.id,
                    "event_author": event.author,
                    "timestamp": event.timestamp,
                    "event_type": getattr(event, "event_type", None),
                    "is_final_response": getattr(
                        event, "is_final_response", lambda: False
                    )(),
                    "turn_complete": getattr(event, "turn_complete", False),
                    "interrupted": getattr(event, "interrupted", False),
                    "partial": getattr(event, "partial", False),
                    "tool_calls": event_metadata.get("tool_calls", []),
                    "thinking_content": event_metadata.get("thinking_content"),
                    "action_taken": event_metadata.get("action_taken"),
                    "agent_name": event_metadata.get("agent_name"),
                    "step_info": event_metadata.get("step_info"),
                    "state_delta": event_metadata.get("state_delta", {}),
                }

                message = AgentMessage(
                    id=f"{event.id}_{len(messages)}",  # Ensure unique IDs
                    investigation_id=investigation_id,
                    message_type=message_type,
                    content=content,
                    metadata=comprehensive_metadata,
                    timestamp=(
                        datetime.fromtimestamp(event.timestamp)
                        if isinstance(event.timestamp, (int, float))
                        else datetime.now()
                    ),
                )
                messages.append(message)

            logger.info(
                f"Retrieved {len(messages)} rich agent messages for investigation {investigation_id}"
            )
            return messages

        except Exception as e:
            logger.error(f"Error retrieving chat history for {investigation_id}: {e}")
            return []

    def _extract_event_metadata(self, event) -> Dict[str, Any]:
        """Extract rich metadata from ADK event"""
        metadata = {}

        # Extract tool calls if present
        if hasattr(event, "tool_calls") and event.tool_calls:
            metadata["tool_calls"] = [
                {
                    "tool_name": (
                        tool_call.function.name
                        if hasattr(tool_call, "function")
                        else str(tool_call)
                    ),
                    "arguments": (
                        getattr(tool_call.function, "arguments", {})
                        if hasattr(tool_call, "function")
                        else {}
                    ),
                    "result": getattr(tool_call, "result", None),
                }
                for tool_call in event.tool_calls
            ]

        # Extract thinking content if it's a thinking event
        if hasattr(event, "thinking") and event.thinking:
            metadata["thinking_content"] = event.thinking

        # Extract agent name if available
        if hasattr(event, "agent_name") and event.agent_name:
            metadata["agent_name"] = event.agent_name

        # Extract action information
        if hasattr(event, "action") and event.action:
            metadata["action_taken"] = str(event.action)

        # Extract step information for multi-step processes
        if hasattr(event, "step") and event.step:
            metadata["step_info"] = {
                "step_number": getattr(event.step, "number", None),
                "step_name": getattr(event.step, "name", None),
                "step_description": getattr(event.step, "description", None),
            }

        # Extract state delta for state changes
        if hasattr(event, "state_delta") and event.state_delta:
            metadata["state_delta"] = dict(event.state_delta)

        return metadata

    def _determine_message_type(
        self, event, metadata: Dict[str, Any]
    ) -> AgentMessageType:
        """Determine message type with rich ADK event classification"""
        if event.author == "user":
            return AgentMessageType.USER
        elif event.author == "system":
            return AgentMessageType.SYSTEM
        elif event.author == "agent":
            # For agent messages, determine if it's thinking, tool use, or response
            if metadata.get("thinking_content"):
                return AgentMessageType.THINKING
            elif metadata.get("tool_calls"):
                return AgentMessageType.AGENT  # Tool usage
            else:
                return AgentMessageType.AGENT  # Regular agent response
        else:
            # Default to thinking for unknown authors that might be internal ADK processes
            return AgentMessageType.THINKING

    def _extract_event_content(self, event, metadata: Dict[str, Any]) -> str:
        """Extract rich content from ADK event with proper formatting"""
        content_parts = []

        # Primary content from event
        if event.content and hasattr(event.content, "parts") and event.content.parts:
            primary_content = event.content.parts[0].text or ""
            if primary_content:
                content_parts.append(primary_content)

        # Add thinking content if present
        if metadata.get("thinking_content"):
            content_parts.append(f"🤔 **Thinking**: {metadata['thinking_content']}")

        # Add tool call information
        if metadata.get("tool_calls"):
            for tool_call in metadata["tool_calls"]:
                tool_info = f"🔧 **Tool Used**: {tool_call['tool_name']}"
                if tool_call.get("arguments"):
                    tool_info += f" with arguments: {json.dumps(tool_call['arguments'], indent=2)}"
                if tool_call.get("result"):
                    tool_info += f"\n📊 **Result**: {tool_call['result']}"
                content_parts.append(tool_info)

        # Add step information
        if metadata.get("step_info") and metadata["step_info"].get("step_name"):
            step_info = metadata["step_info"]
            content_parts.append(
                f"📋 **Step {step_info.get('step_number', '?')}**: {step_info['step_name']}"
            )

        # Add action information
        if metadata.get("action_taken"):
            content_parts.append(f"⚡ **Action**: {metadata['action_taken']}")

        # Join all content parts
        final_content = (
            "\n\n".join(content_parts) if content_parts else "No content available"
        )

        return final_content

    async def handle_decision(
        self, investigation_id: str, decision: str, decision_type: str
    ) -> str:
        """Handle human decision during investigation"""
        investigation = await self.get_investigation(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # Send decision as user message to ADK
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
                user_id=self.default_user_id,  # Use consistent user ID
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
        """Update investigation status using proper ADK event handling"""
        try:
            session_id = self._get_session_id(investigation_id)
            session = await self.session_service.get_session(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
                session_id=session_id,
            )

            if not session:
                logger.error(f"Session not found for investigation {investigation_id}")
                return

            # Create state changes following ADK pattern
            current_time = time.time()
            investigation_data = session.state.get("investigation", {})
            investigation_data["status"] = status.value
            investigation_data["updated_at"] = datetime.now().isoformat()

            if error_message:
                investigation_data["error_message"] = error_message
            if result:
                investigation_data["result"] = result
            if completed_at:
                investigation_data["completed_at"] = completed_at.isoformat()

            state_changes: Dict[str, Any] = {"investigation": investigation_data}

            # Create Event with EventActions for state update
            actions_with_update = EventActions(state_delta=state_changes)
            status_event = Event(
                invocation_id=f"inv_status_update_{investigation_id}",
                author="system",
                actions=actions_with_update,
                timestamp=current_time,
                content=types.Content(
                    role="system",
                    parts=[
                        types.Part(
                            text=f"Investigation status updated to {status.value}"
                        )
                    ],
                ),
            )

            # Apply the event to update state
            await self.session_service.append_event(session, status_event)

            logger.info(
                f"Updated investigation {investigation_id} status to {status.value}"
            )

        except Exception as e:
            logger.error(
                f"Error updating investigation status for {investigation_id}: {e}"
            )

    async def update_investigation_status(
        self,
        investigation_id: str,
        status: InvestigationStatus,
        error_message: Optional[str] = None,
    ) -> bool:
        """Update the status of an investigation using proper ADK events"""
        try:
            # Use the internal method that follows ADK patterns
            await self._update_investigation_status(
                investigation_id, status, error_message=error_message
            )
            return True

        except Exception as e:
            logger.error(f"Error updating investigation {investigation_id} status: {e}")
            return False

    async def delete_investigation(self, investigation_id: str) -> bool:
        """Delete an investigation and its associated session data"""
        try:
            session_id = self._get_session_id(investigation_id)

            # Remove runner if it's active
            if investigation_id in self.runners:
                try:
                    del self.runners[investigation_id]
                    logger.info(
                        f"Removed active runner for investigation {investigation_id}"
                    )
                except Exception as e:
                    logger.warning(f"Error removing runner for {investigation_id}: {e}")

            # Delete session from database
            await self.session_service.delete_session(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
                session_id=session_id,
            )

            logger.info(f"Successfully deleted investigation {investigation_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting investigation {investigation_id}: {e}")
            return False

    async def get_investigations_count(self) -> int:
        """Get total count of investigations"""
        try:
            sessions_response = await self.session_service.list_sessions(
                app_name=self.app_name,
                user_id=self.default_user_id,  # Use consistent user ID
            )
            return len(sessions_response.sessions)
        except Exception as e:
            logger.error(f"Error getting investigations count: {e}")
            return 0
