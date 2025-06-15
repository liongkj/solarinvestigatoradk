"""Investigation service for managing solar investigations"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import json

from adk.agents.solar_investigation_agent import get_solar_investigation_agent
from adk.models.investigation import (
    Investigation,
    InvestigationRequest,
    InvestigationStatus,
    AgentMessage,
    AgentMessageType,
)

logger = logging.getLogger(__name__)


class InvestigationService:
    """Service for managing solar investigations"""

    def __init__(self):
        # Use in-memory storage for now (TODO: implement persistent storage)
        self.investigations: Dict[str, Investigation] = {}
        self.chat_histories: Dict[str, List[AgentMessage]] = {}
        self.session_service = InMemorySessionService()
        self.runners: Dict[str, Runner] = {}

    async def create_investigation(
        self, request: InvestigationRequest
    ) -> Investigation:
        """Create a new solar investigation"""
        investigation = Investigation(
            address=request.address,
            monthly_usage=request.monthly_usage,
            property_type=request.property_type,
            budget_range=request.budget_range,
            additional_notes=request.additional_notes,
            status=InvestigationStatus.PENDING,
        )

        # Store investigation
        self.investigations[investigation.id] = investigation
        self.chat_histories[investigation.id] = []

        logger.info(
            f"Created investigation {investigation.id} for address: {request.address}"
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

    async def start_investigation(self, investigation_id: str) -> Investigation:
        """Start running the investigation using Google ADK agent"""
        investigation = self.investigations.get(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        if investigation.status != InvestigationStatus.PENDING:
            raise ValueError(
                f"Investigation {investigation_id} is not in pending status"
            )

        try:
            # Update status to running
            investigation.status = InvestigationStatus.RUNNING
            investigation.updated_at = datetime.now()

            # Create agent and runner
            agent = get_solar_investigation_agent()
            runner = Runner(
                agent=agent,
                app_name="solar_investigation_api",
                session_service=self.session_service,
            )

            # Store runner for this investigation
            self.runners[investigation_id] = runner

            # Create session
            session_id = f"session_{investigation_id}"
            investigation.session_id = session_id

            await self.session_service.create_session(
                app_name="solar_investigation_api",
                user_id=investigation.user_id,
                session_id=session_id,
            )

            # Add initial system message
            await self._add_agent_message(
                investigation_id,
                AgentMessageType.SYSTEM,
                f"Starting solar investigation for {investigation.address}",
            )

            # TODO: implement async agent execution - for now just mark as started
            logger.info(f"Started investigation {investigation_id}")

        except Exception as e:
            investigation.status = InvestigationStatus.FAILED
            investigation.error_message = str(e)
            investigation.updated_at = datetime.now()
            logger.error(f"Failed to start investigation {investigation_id}: {e}")
            raise

        return investigation

    async def run_investigation_step(
        self, investigation_id: str, user_message: str
    ) -> str:
        """Run a step of the investigation with user message"""
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

            # Prepare query for agent
            query = {
                "address": investigation.address,
                "monthly_usage": investigation.monthly_usage,
                "property_type": investigation.property_type,
                "user_message": user_message,
            }

            # Send to agent
            user_content = types.Content(
                role="user", parts=[types.Part(text=json.dumps(query))]
            )

            final_response = "No response received"
            async for event in runner.run_async(
                user_id=investigation.user_id,
                session_id=investigation.session_id,
                new_message=user_content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text

            # Add agent response to chat history
            await self._add_agent_message(
                investigation_id, AgentMessageType.AGENT, final_response
            )

            # Update investigation
            investigation.updated_at = datetime.now()

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
        """Add a message to the chat history"""
        message = AgentMessage(
            investigation_id=investigation_id,
            message_type=message_type,
            content=content,
            metadata=metadata,
        )

        if investigation_id not in self.chat_histories:
            self.chat_histories[investigation_id] = []

        self.chat_histories[investigation_id].append(message)
        return message


# Global service instance
investigation_service = InvestigationService()
