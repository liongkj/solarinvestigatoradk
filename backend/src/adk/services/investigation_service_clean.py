"""Investigation service for managing solar investigations"""

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
    """Service for managing solar investigations"""

    def __init__(self):
        # Get application settings
        settings = get_settings()

        # Use persistent database storage for sessions
        self.session_service = DatabaseSessionService(db_url=settings.database_url)

        # Simple file-based persistence for investigations (quick fix)
        self.investigations_file = "investigations_data.json"

        # In-memory cache loaded from file
        self.investigations: Dict[str, Investigation] = {}
        self.chat_histories: Dict[str, List[AgentMessage]] = {}
        self.runners: Dict[str, Runner] = {}
        self.plant_service = PlantService()

        # Load existing investigations from file
        self._load_investigations_from_file()

        logger.info(
            f"Initialized InvestigationService with database: {settings.database_url}"
        )
        logger.info(
            f"Loaded {len(self.investigations)} investigations from file storage"
        )

    def _load_investigations_from_file(self):
        """Load investigations and chat histories from JSON file"""
        try:
            import os

            if os.path.exists(self.investigations_file):
                with open(self.investigations_file, "r") as f:
                    data = json.load(f)
                    for inv_id, inv_data in data.items():
                        # Load investigation data
                        investigation_data = inv_data.get("investigation", inv_data)

                        # Convert ISO strings back to datetime/date objects
                        investigation_data["created_at"] = datetime.fromisoformat(
                            investigation_data["created_at"]
                        )
                        investigation_data["updated_at"] = datetime.fromisoformat(
                            investigation_data["updated_at"]
                        )
                        if investigation_data["completed_at"]:
                            investigation_data["completed_at"] = datetime.fromisoformat(
                                investigation_data["completed_at"]
                            )
                        investigation_data["start_date"] = datetime.fromisoformat(
                            investigation_data["start_date"]
                        ).date()
                        investigation_data["end_date"] = datetime.fromisoformat(
                            investigation_data["end_date"]
                        ).date()
                        investigation_data["status"] = InvestigationStatus(
                            investigation_data["status"]
                        )

                        investigation = Investigation(**investigation_data)
                        self.investigations[inv_id] = investigation

                        # Load chat history if present
                        chat_data = inv_data.get("chat_history", [])
                        messages = []
                        for msg_data in chat_data:
                            # Convert timestamp back to datetime
                            msg_data["timestamp"] = datetime.fromisoformat(
                                msg_data["timestamp"]
                            )
                            msg_data["message_type"] = AgentMessageType(
                                msg_data["message_type"]
                            )
                            messages.append(AgentMessage(**msg_data))

                        self.chat_histories[inv_id] = messages

        except Exception as e:
            logger.error(f"Error loading investigations from file: {e}")

    def _save_investigations_to_file(self):
        """Save investigations and chat histories to JSON file"""
        try:
            data = {}
            for inv_id, investigation in self.investigations.items():
                # Save investigation data
                inv_dict = investigation.model_dump()
                # Convert datetime objects to ISO strings for JSON serialization
                inv_dict["created_at"] = investigation.created_at.isoformat()
                inv_dict["updated_at"] = investigation.updated_at.isoformat()
                if investigation.completed_at:
                    inv_dict["completed_at"] = investigation.completed_at.isoformat()
                else:
                    inv_dict["completed_at"] = None
                inv_dict["start_date"] = investigation.start_date.isoformat()
                inv_dict["end_date"] = investigation.end_date.isoformat()
                inv_dict["status"] = investigation.status.value

                # Save chat history
                chat_history = []
                for message in self.chat_histories.get(inv_id, []):
                    msg_dict = message.model_dump()
                    msg_dict["timestamp"] = message.timestamp.isoformat()
                    msg_dict["message_type"] = message.message_type.value
                    chat_history.append(msg_dict)

                data[inv_id] = {"investigation": inv_dict, "chat_history": chat_history}

            with open(self.investigations_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving investigations to file: {e}")

    async def _create_investigation(
        self, request: InvestigationRequest
    ) -> Investigation:
        """Create a new solar investigation"""
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

        investigation = Investigation(
            plant_id=request.plant_id,
            start_date=request.start_date,
            end_date=request.end_date,
            additional_notes=request.additional_notes,
            status=InvestigationStatus.PENDING,
        )

        # Store investigation in memory and file
        self.investigations[investigation.id] = investigation
        self.chat_histories[investigation.id] = []
        self._save_investigations_to_file()

        logger.info(
            f"Created investigation {investigation.id} for plant: {request.plant_id} "
            f"({request.start_date} to {request.end_date})"
        )
        return investigation

    async def get_investigation(self, investigation_id: str) -> Optional[Investigation]:
        """Get investigation by ID"""
        return self.investigations.get(investigation_id)

    async def list_investigations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Investigation]:
        """List all investigations with pagination"""
        investigations = list(self.investigations.values())
        # Sort by creation time (newest first)
        investigations.sort(key=lambda x: x.created_at, reverse=True)
        return investigations[offset : offset + limit]

    async def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Start running the investigation using Google ADK agent"""
        # Create investigation
        investigation = await self._create_investigation(request)
        investigation_id = investigation.id

        if investigation.status != InvestigationStatus.PENDING:
            raise ValueError(
                f"Investigation {investigation_id} is not in pending status"
            )

        try:
            # Update status to running
            investigation.status = InvestigationStatus.RUNNING
            investigation.updated_at = datetime.now()
            self._save_investigations_to_file()

            # Create agent and runner following ADK best practices
            agent = get_solar_investigation_agent()
            runner = Runner(
                agent=agent,
                app_name="solar_investigation_api",
                session_service=self.session_service,
            )

            # Store runner for this investigation
            self.runners[investigation_id] = runner

            # Create session following ADK pattern
            session_id = f"session_{investigation_id}"
            investigation.session_id = session_id

            session = await self.session_service.create_session(
                app_name="solar_investigation_api",
                user_id=investigation.user_id,
                session_id=session_id,
            )

            # Get plant information
            plant = await self.plant_service.get_plant_by_id(investigation.plant_id)
            plant_name = plant.plant_name if plant else "Unknown Plant"

            # Add initial system message
            await self._add_agent_message(
                investigation_id,
                AgentMessageType.SYSTEM,
                f"Starting solar investigation for {plant_name} "
                f"from {investigation.start_date} to {investigation.end_date}",
            )

            # Save updated investigation
            self._save_investigations_to_file()

            # Automatically start the agent execution following ADK patterns
            await self._execute_agent_automatically(
                investigation_id, investigation, plant, runner, session
            )

            logger.info(
                f"Started investigation {investigation_id} with automatic agent execution"
            )

        except Exception as e:
            investigation.status = InvestigationStatus.FAILED
            investigation.error_message = str(e)
            investigation.updated_at = datetime.now()
            self._save_investigations_to_file()
            logger.error(f"Failed to start investigation {investigation_id}: {e}")
            raise

        return investigation

    async def run_investigation_step(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Run a step of the investigation with user message and capture agent reasoning"""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        runner = self.runners.get(investigation_id)
        if not runner:
            raise ValueError(f"No active runner for investigation {investigation_id}")

        try:
            # Add user message to chat history
            await self._add_agent_message(
                investigation_id, AgentMessageType.USER, user_message
            )

            # Add initial reasoning step
            await self._add_thinking_message(
                investigation_id,
                "🤔 Starting analysis of user request",
                f"Processing request: {user_message}",
                "major",
                "request_analysis",
            )

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

            await self._add_thinking_message(
                investigation_id,
                "📋 Preparing investigation context",
                f"Plant: {plant.plant_name if plant else 'Unknown'}, Period: {investigation.start_date} to {investigation.end_date}",
                "detailed",
                "context_preparation",
            )

            # Send to agent
            user_content = types.Content(
                role="user", parts=[types.Part(text=json.dumps(query))]
            )

            await self._add_thinking_message(
                investigation_id,
                "🚀 Initiating agent execution",
                "Sending context to agent and monitoring reasoning process",
                "major",
                "agent_handoff",
            )

            final_response = "No response received"
            session_id = investigation.session_id
            if not session_id:
                raise ValueError(
                    f"No session found for investigation {investigation_id}"
                )

            # Process agent events and capture reasoning
            await self._process_agent_events(
                investigation_id, runner, session_id, user_content
            )

            # Get the final response from the last agent message
            recent_messages = self.chat_histories.get(investigation_id, [])
            agent_messages = [
                msg
                for msg in recent_messages
                if msg.message_type == AgentMessageType.AGENT
            ]
            if agent_messages:
                final_response = agent_messages[-1].content

            # Update investigation
            investigation.updated_at = datetime.now()
            self._save_investigations_to_file()

            return final_response

        except Exception as e:
            logger.error(
                f"Error running investigation step for {investigation_id}: {e}"
            )
            await self._add_agent_message(
                investigation_id, AgentMessageType.SYSTEM, f"Error: {str(e)}"
            )
            raise

    async def complete_investigation(
        self, investigation_id: str, result: Dict[str, Any]
    ) -> Investigation:
        """Mark investigation as completed with results"""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        investigation.status = InvestigationStatus.COMPLETED
        investigation.result = result
        investigation.completed_at = datetime.now()
        investigation.updated_at = datetime.now()

        # Clean up runner
        if investigation_id in self.runners:
            del self.runners[investigation_id]

        # Save to file
        self._save_investigations_to_file()

        logger.info(f"Completed investigation {investigation_id}")
        return investigation

    async def get_chat_history(self, investigation_id: str) -> List[AgentMessage]:
        """Get chat history for an investigation"""
        return self.chat_histories.get(investigation_id, [])

    async def handle_decision(
        self, investigation_id: str, decision: str, decision_type: str
    ) -> str:
        """Handle human decision during investigation"""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # Add decision to chat history
        await self._add_agent_message(
            investigation_id,
            AgentMessageType.USER,
            f"Decision ({decision_type}): {decision}",
        )

        # TODO: implement decision handling logic
        # For now, just acknowledge the decision
        response = f"Decision received: {decision}"

        await self._add_agent_message(
            investigation_id, AgentMessageType.SYSTEM, response
        )

        return response

    async def _add_agent_message(
        self,
        investigation_id: str,
        message_type: AgentMessageType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Add a message to the chat history and persist it"""
        message = AgentMessage(
            investigation_id=investigation_id,
            message_type=message_type,
            content=content,
            metadata=metadata,
        )

        if investigation_id not in self.chat_histories:
            self.chat_histories[investigation_id] = []

        self.chat_histories[investigation_id].append(message)

        # Save to file immediately to persist chat history
        self._save_investigations_to_file()

        logger.info(
            f"Added {message_type.value} message to investigation {investigation_id}: {content[:100]}..."
        )
        return message

    async def add_thinking_message(
        self,
        investigation_id: str,
        title: str,
        description: str,
        level: str = "major",  # "major" or "detailed"
        step_type: str = "reasoning",  # "reasoning", "decision", "handoff", "tool_call", etc.
    ) -> AgentMessage:
        """Public method to add a thinking/reasoning message to show agent's thought process"""
        return await self._add_thinking_message(
            investigation_id, title, description, level, step_type
        )

    async def _add_thinking_message(
        self,
        investigation_id: str,
        title: str,
        description: str,
        level: str = "major",  # "major" or "detailed"
        step_type: str = "reasoning",  # "reasoning", "decision", "handoff", "tool_call", etc.
    ) -> AgentMessage:
        """Add a thinking/reasoning message to show agent's thought process"""
        metadata = {
            "thinking": True,
            "level": level,
            "step_type": step_type,
            "title": title,
        }

        content = f"{title}: {description}"

        message = await self._add_agent_message(
            investigation_id,
            AgentMessageType.THINKING,
            content,
            metadata=metadata,
        )

        logger.info(f"Added thinking message ({level}): {title}")
        return message

    async def _process_agent_events(
        self,
        investigation_id: str,
        runner: Runner,
        session_id: str,
        user_content: types.Content,
    ) -> None:
        """Process agent events and capture reasoning process following ADK best practices"""

        event_count = 0
        tool_calls_processed = 0
        events_async = None

        logger.info(f"Starting agent execution for investigation {investigation_id}")
        logger.info(
            f"User message: {user_content.parts[0].text if user_content.parts else 'No content'}"
        )

        try:
            # Use ADK runner.run_async pattern from official documentation
            events_async = runner.run_async(
                user_id=self.investigations[investigation_id].user_id,
                session_id=session_id,
                new_message=user_content,
            )

            logger.info("Agent execution started, processing events...")

            # Process events as they come from the agent
            async for event in events_async:
                try:
                    event_count += 1

                    # Enhanced logging for debugging Gemini API calls
                    logger.info(
                        f"Event {event_count}: author={event.author}, "
                        f"final={event.is_final_response()}, "
                        f"content_type={type(event.content) if event.content else 'None'}, "
                        f"content_available={bool(event.content and event.content.parts)}"
                    )

                    # Log event content for debugging
                    if event.content and event.content.parts:
                        content_preview = (
                            event.content.parts[0].text[:200]
                            if event.content.parts[0].text
                            else "No text"
                        )
                        logger.debug(f"Event content preview: {content_preview}...")

                    # Capture agent reasoning based on event type
                    await self._capture_event_reasoning(
                        investigation_id, event, event_count
                    )

                    # Process tool calls if present
                    if event.content and hasattr(event, "get_function_calls"):
                        calls = event.get_function_calls()
                        if calls:
                            logger.info(f"Processing {len(calls)} function calls")
                            for call in calls:
                                tool_calls_processed += 1
                                await self._capture_tool_call_reasoning(
                                    investigation_id, call, tool_calls_processed
                                )

                    # Process tool responses if present
                    if event.content and hasattr(event, "get_function_responses"):
                        responses = event.get_function_responses()
                        if responses:
                            logger.info(
                                f"Processing {len(responses)} function responses"
                            )
                            for response in responses:
                                await self._capture_tool_response_reasoning(
                                    investigation_id, response
                                )

                    # Handle final response from agent
                    if event.is_final_response():
                        logger.info("Received final response from agent")
                        if event.content and event.content.parts:
                            final_text = event.content.parts[0].text or "Empty response"
                            logger.info(
                                f"Final response length: {len(final_text)} characters"
                            )

                            await self._add_agent_message(
                                investigation_id, AgentMessageType.AGENT, final_text
                            )

                            await self._add_thinking_message(
                                investigation_id,
                                "✅ Investigation step completed",
                                f"Processed {event_count} events, {tool_calls_processed} tool calls. Agent provided final response.",
                                "major",
                                "completion",
                            )
                        else:
                            logger.warning("Final response event has no content")
                            await self._add_thinking_message(
                                investigation_id,
                                "⚠️ Investigation completed with empty response",
                                f"Processed {event_count} events, {tool_calls_processed} tool calls. No final content received.",
                                "major",
                                "completion",
                            )
                        break

                except GeneratorExit:
                    # Handle generator exit gracefully at event level
                    logger.info("Agent event generator was closed gracefully")
                    break
                except Exception as event_error:
                    logger.error(
                        f"Error processing individual event {event_count}: {event_error}"
                    )
                    # Continue processing other events
                    continue

            logger.info(
                f"Agent execution completed. Total events: {event_count}, Tool calls: {tool_calls_processed}"
            )

        except GeneratorExit:
            # Handle generator exit at the top level - this suppresses the OpenTelemetry warnings
            logger.info("Agent execution was terminated gracefully (GeneratorExit)")
        except Exception as e:
            logger.error(
                f"Error processing agent events for investigation {investigation_id}: {e}"
            )
            await self._add_thinking_message(
                investigation_id,
                "❌ Agent execution error",
                f"Error occurred during agent execution: {str(e)}",
                "major",
                "error",
            )
            # Re-raise to be handled by caller
            raise
        finally:
            # Ensure proper cleanup of async generator to avoid OpenTelemetry context issues
            if events_async is not None:
                try:
                    # Try to close the generator cleanly
                    if hasattr(events_async, "aclose"):
                        await events_async.aclose()
                except Exception as cleanup_error:
                    logger.debug(
                        f"Generator cleanup completed with minor issue: {cleanup_error}"
                    )
                    # This is expected and can be ignored

    async def _capture_event_reasoning(
        self, investigation_id: str, event, event_count: int
    ) -> None:
        """Capture reasoning based on event type and content"""

        # Agent handoff detection
        if hasattr(event, "actions") and event.actions:
            if (
                hasattr(event.actions, "transfer_to_agent")
                and event.actions.transfer_to_agent
            ):
                await self._add_thinking_message(
                    investigation_id,
                    "🔄 Agent handoff detected",
                    f"Transferring to: {event.actions.transfer_to_agent}",
                    "major",
                    "handoff",
                )

            if hasattr(event.actions, "escalate") and event.actions.escalate:
                await self._add_thinking_message(
                    investigation_id,
                    "⚠️ Escalation triggered",
                    "Agent is escalating the issue for human review",
                    "major",
                    "escalation",
                )

        # Decision point detection (based on author changes)
        if event.author and event.author != "user":
            await self._add_thinking_message(
                investigation_id,
                f"🧠 {event.author} processing",
                f"Agent {event.author} is analyzing the situation",
                "detailed",
                "agent_processing",
            )

    async def _capture_tool_call_reasoning(
        self, investigation_id: str, call, tool_number: int
    ) -> None:
        """Capture reasoning for tool calls"""
        tool_name = call.name if hasattr(call, "name") else "Unknown tool"
        args = call.args if hasattr(call, "args") else {}

        # Explain why this tool is being called
        reasoning_text = f"Tool {tool_number}: {tool_name}"
        if args:
            reasoning_text += f" with parameters: {str(args)[:200]}..."

        await self._add_thinking_message(
            investigation_id,
            "🔧 Tool execution initiated",
            reasoning_text,
            "major",
            "tool_call",
        )

    async def _capture_tool_response_reasoning(
        self, investigation_id: str, response
    ) -> None:
        """Capture reasoning for tool responses"""
        tool_name = response.name if hasattr(response, "name") else "Unknown tool"
        result = response.response if hasattr(response, "response") else {}

        # Analyze the tool result
        result_summary = (
            str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
        )

        await self._add_thinking_message(
            investigation_id,
            f"📊 {tool_name} completed",
            f"Tool result: {result_summary}",
            "detailed",
            "tool_result",
        )

    async def _execute_agent_automatically(
        self,
        investigation_id: str,
        investigation: Investigation,
        plant,
        runner: Runner,
        session,
    ) -> None:
        """Execute the agent automatically following ADK best practices"""
        try:
            await self._add_thinking_message(
                investigation_id,
                "🚀 Initializing solar investigation agent",
                f"Starting automatic analysis for {plant.plant_name if plant else investigation.plant_id}",
                "major",
                "agent_initialization",
            )

            # Prepare comprehensive query for the solar agent
            query_data = {
                "address": (
                    plant.plant_name if plant else f"Plant {investigation.plant_id}"
                ),
                "monthly_usage": 850.0,  # TODO: get from plant data
                "property_type": "commercial",  # TODO: determine from plant type
                "investigation_period": {
                    "start_date": investigation.start_date.isoformat(),
                    "end_date": investigation.end_date.isoformat(),
                },
                "additional_context": investigation.additional_notes
                or "Standard solar feasibility analysis",
                "request": "Please analyze this property for solar installation potential and provide comprehensive recommendations.",
            }

            await self._add_thinking_message(
                investigation_id,
                "📨 Preparing query for Gemini AI",
                f"Plant: {query_data['address']}, Usage: {query_data['monthly_usage']} kWh/month",
                "detailed",
                "query_preparation",
            )

            # Create ADK-compliant user message for the agent
            user_content = types.Content(
                role="user", parts=[types.Part(text=json.dumps(query_data, indent=2))]
            )

            await self._add_thinking_message(
                investigation_id,
                "🧠 Calling Gemini AI via ADK runner",
                "Initiating agent execution with structured query",
                "major",
                "agent_handoff",
            )

            # Use the unified event processing method
            await self._process_agent_events(
                investigation_id, runner, session.id, user_content
            )

            # Update investigation status
            investigation.updated_at = datetime.now()
            self._save_investigations_to_file()

        except Exception as e:
            logger.error(
                f"Failed to execute agent automatically for {investigation_id}: {e}"
            )
            await self._add_thinking_message(
                investigation_id,
                "❌ Agent execution failed",
                f"Error during automatic execution: {str(e)}",
                "major",
                "error",
            )

    async def _process_agent_actions(self, investigation_id: str, actions) -> None:
        """Process agent actions like escalations and handoffs"""
        try:
            if hasattr(actions, "escalate") and actions.escalate:
                await self._add_thinking_message(
                    investigation_id,
                    "⚠️ Agent escalation",
                    "Agent is escalating for human intervention",
                    "major",
                    "escalation",
                )

            if hasattr(actions, "transfer_to_agent") and actions.transfer_to_agent:
                await self._add_thinking_message(
                    investigation_id,
                    "🔄 Agent handoff",
                    f"Transferring to agent: {actions.transfer_to_agent}",
                    "major",
                    "handoff",
                )

            if hasattr(actions, "state_delta") and actions.state_delta:
                await self._add_thinking_message(
                    investigation_id,
                    "📝 State update",
                    f"Agent updated session state with {len(actions.state_delta)} changes",
                    "detailed",
                    "state_update",
                )

        except Exception as e:
            logger.error(f"Error processing agent actions for {investigation_id}: {e}")

    # Remove old method
    async def _start_automatic_investigation(
        self, investigation_id: str, plant
    ) -> None:
        """Deprecated - use _execute_agent_automatically instead"""
        logger.warning(
            "_start_automatic_investigation is deprecated, use _execute_agent_automatically"
        )
        pass
