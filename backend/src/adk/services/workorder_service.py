"""Workorder service for managing workorder operations with Google ADK integration"""

import logging
from typing import List, Optional
from datetime import datetime
import uuid

from adk.models.workorder import (
    Workorder,
    WorkorderAgentRequest,
    WorkorderAgentResponse,
    WorkorderStatus,
    WorkorderType,
)
from adk.models.investigation import AgentMessage, AgentMessageType
from adk.agents.workorder_agent import WorkorderAgent

logger = logging.getLogger(__name__)


class WorkorderService:
    """Service for managing workorder operations with Google ADK agent integration"""

    def __init__(self):
        # Initialize workorder agent
        self.workorder_agent = WorkorderAgent()

        # In-memory storage for workorders (TODO: replace with database)
        self._workorders: List[Workorder] = []

    async def create_workorder_with_agent(
        self, investigation_id: str, request: WorkorderAgentRequest
    ) -> tuple[WorkorderAgentResponse, List[AgentMessage]]:
        """
        Create a workorder using the Google ADK agent

        Args:
            investigation_id: ID of the investigation
            request: Workorder agent request with todo summary

        Returns:
            Tuple of (WorkorderAgentResponse, List[AgentMessage]) for chat integration
        """
        try:
            logger.info(
                f"Creating workorder with agent for investigation {investigation_id}"
            )

            # Process with workorder agent
            agent_response = await self.workorder_agent.process_workorder(
                todo_summary=request.todo_summary, investigation_id=investigation_id
            )

            # Create workorder response
            workorder_response = WorkorderAgentResponse(
                investigation_id=investigation_id,
                todo_summary=request.todo_summary,
                agent_response=agent_response,
                priority=request.priority,
                status=WorkorderStatus.COMPLETED,
                workorder_type=WorkorderType.ANALYSIS,
            )

            # Create workorder for storage
            workorder = Workorder(
                investigation_id=investigation_id,
                type=WorkorderType.ANALYSIS,
                description=f"Agent processed: {request.todo_summary}",
                agent_response=agent_response,
                priority=request.priority,
                status=WorkorderStatus.COMPLETED,
                completed_at=datetime.now(),
            )

            # Store workorder
            self._workorders.append(workorder)

            # Create chat messages for investigation history
            chat_messages = [
                # Tool call message
                AgentMessage(
                    investigation_id=investigation_id,
                    message_type=AgentMessageType.TOOL_CALL,
                    content=f"Workorder Agent called with todo: {request.todo_summary}",
                    ui_summary="Workorder Agent Processing",
                    ui_state={"processing": True},
                    show_full_content=False,
                    metadata={
                        "tool_name": "workorder_agent",
                        "workorder_id": workorder_response.workorder_id,
                        "todo_summary": request.todo_summary,
                        "priority": request.priority,
                    },
                ),
                # Agent response message
                AgentMessage(
                    investigation_id=investigation_id,
                    message_type=AgentMessageType.AGENT,
                    content=agent_response,
                    ui_summary="Workorder Generated",
                    ui_state={"completed": True},
                    show_full_content=True,
                    metadata={
                        "source": "workorder_agent",
                        "workorder_id": workorder_response.workorder_id,
                        "workorder_type": "analysis",
                    },
                ),
            ]

            logger.info(
                f"Workorder created successfully for investigation {investigation_id}"
            )
            return workorder_response, chat_messages

        except Exception as e:
            logger.error(f"Error creating workorder with agent: {e}")
            raise

    async def get_workorders_by_investigation(
        self, investigation_id: str
    ) -> List[Workorder]:
        """
        Get all workorders for a specific investigation

        Args:
            investigation_id: ID of the investigation

        Returns:
            List of workorders for the investigation
        """
        return [w for w in self._workorders if w.investigation_id == investigation_id]

    async def create_manual_workorder(
        self, investigation_id: str, description: str, priority: str = "medium"
    ) -> Workorder:
        """
        Create a manual workorder (existing functionality)

        Args:
            investigation_id: ID of the investigation
            description: Workorder description
            priority: Priority level

        Returns:
            Created workorder
        """
        workorder = Workorder(
            investigation_id=investigation_id,
            type=WorkorderType.MAINTENANCE,
            description=description,
            priority=priority,
            status=WorkorderStatus.PENDING,
        )

        self._workorders.append(workorder)
        logger.info(f"Manual workorder created for investigation {investigation_id}")
        return workorder
