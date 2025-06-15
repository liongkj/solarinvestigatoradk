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

        logger.info(f"Initialized InvestigationService with database: {settings.database_url}")
        logger.info(f"Loaded {len(self.investigations)} investigations from file storage")

    def _load_investigations_from_file(self):
        """Load investigations from JSON file"""
        try:
            import os
            if os.path.exists(self.investigations_file):
                with open(self.investigations_file, 'r') as f:
                    data = json.load(f)
                    for inv_id, inv_data in data.items():
                        # Convert ISO strings back to datetime/date objects
                        inv_data['created_at'] = datetime.fromisoformat(inv_data['created_at'])
                        inv_data['updated_at'] = datetime.fromisoformat(inv_data['updated_at'])
                        if inv_data['completed_at']:
                            inv_data['completed_at'] = datetime.fromisoformat(inv_data['completed_at'])
                        inv_data['start_date'] = datetime.fromisoformat(inv_data['start_date']).date()
                        inv_data['end_date'] = datetime.fromisoformat(inv_data['end_date']).date()
                        inv_data['status'] = InvestigationStatus(inv_data['status'])
                        
                        investigation = Investigation(**inv_data)
                        self.investigations[inv_id] = investigation
        except Exception as e:
            logger.error(f"Error loading investigations from file: {e}")

    def _save_investigations_to_file(self):
        """Save investigations to JSON file"""
        try:
            data = {}
            for inv_id, investigation in self.investigations.items():
                inv_dict = investigation.model_dump()
                # Convert datetime objects to ISO strings for JSON serialization
                inv_dict['created_at'] = investigation.created_at.isoformat()
                inv_dict['updated_at'] = investigation.updated_at.isoformat()
                if investigation.completed_at:
                    inv_dict['completed_at'] = investigation.completed_at.isoformat()
                else:
                    inv_dict['completed_at'] = None
                inv_dict['start_date'] = investigation.start_date.isoformat()
                inv_dict['end_date'] = investigation.end_date.isoformat()
                inv_dict['status'] = investigation.status.value
                data[inv_id] = inv_dict
            
            with open(self.investigations_file, 'w') as f:
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
        inves = await self._create_investigation(request)
        investigation_id = inves.id
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
            self._save_investigations_to_file()

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
            plant = await self.plant_service.get_plant_by_id(investigation.plant_id)
            plant_name = plant.plant_name if plant else "Unknown Plant"
            await self._add_agent_message(
                investigation_id,
                AgentMessageType.SYSTEM,
                f"Starting solar investigation for {plant_name} "
                f"from {investigation.start_date} to {investigation.end_date}",
            )

            # Save updated investigation
            self._save_investigations_to_file()

            # TODO: implement async agent execution - for now just mark as started
            logger.info(f"Started investigation {investigation_id}")

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

            # Send to agent
            user_content = types.Content(
                role="user", parts=[types.Part(text=json.dumps(query))]
            )

            final_response = "No response received"
            session_id = investigation.session_id
            if not session_id:
                raise ValueError(
                    f"No session found for investigation {investigation_id}"
                )

            async for event in runner.run_async(
                user_id=investigation.user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text or "Empty response"

            # Add agent response to chat history
            await self._add_agent_message(
                investigation_id, AgentMessageType.AGENT, final_response
            )

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
