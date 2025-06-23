"""Simple Workorder Agent using Google ADK for managing workorders"""

import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from google.adk.agents import Agent
from google.genai import types

from adk.models.workorder import (
    Workorder,
    WorkorderRequest,
    WorkorderUpdate,
    WorkorderPriority,
    WorkorderStatus,
)

logger = logging.getLogger(__name__)


class WorkorderAgent:
    """Simple workorder management agent using ADK state management"""
    
    def __init__(self, app_name: str = "solar_investigation_api"):
        self.app_name = app_name
        
        # Create a simple agent for workorder management
        self.agent = Agent(
            model_id="gemini-2.0-flash-exp",
            system_instruction="""You are a workorder management assistant for solar panel investigations.

Your responsibilities:
1. Create workorders based on investigation findings
2. Update workorder status and details
3. List and filter workorders
4. Provide workorder summaries

You manage workorders with these properties:
- ID, title, description
- Priority (low, medium, high, urgent)
- Status (pending, in_progress, completed, cancelled)
- Equipment ID, location, duration estimates
- Assignment and due dates

Always respond in a helpful and professional manner. Focus on actionable maintenance tasks."""
        )
    
    async def create_workorder(
        self, 
        investigation_id: str, 
        request: WorkorderRequest
    ) -> Workorder:
        """Create a new workorder"""
        workorder_id = str(uuid.uuid4())
        now = datetime.now()
        
        workorder = Workorder(
            id=workorder_id,
            investigation_id=investigation_id,
            title=request.title,
            description=request.description,
            priority=request.priority,
            equipment_id=request.equipment_id,
            location=request.location,
            estimated_duration_hours=request.estimated_duration_hours,
            due_date=request.due_date,
            created_at=now,
            updated_at=now
        )
        
        logger.info(f"Created workorder {workorder_id} for investigation {investigation_id}")
        return workorder
    
    async def update_workorder(
        self, 
        workorder: Workorder, 
        update: WorkorderUpdate
    ) -> Workorder:
        """Update an existing workorder"""
        update_data = update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if hasattr(workorder, field):
                setattr(workorder, field, value)
        
        workorder.updated_at = datetime.now()
        
        logger.info(f"Updated workorder {workorder.id}")
        return workorder
    
    async def process_workorder_request(
        self, 
        investigation_id: str, 
        user_message: str
    ) -> Dict[str, Any]:
        """Process a user message to extract workorder creation or update requests"""
        
        # Create a prompt for the agent to process the workorder request
        prompt = f"""
Based on the following user message about investigation {investigation_id}, 
extract workorder information or actions:

User message: "{user_message}"

If this is a request to create a workorder, respond with JSON in this format:
{{
    "action": "create",
    "title": "Brief title",
    "description": "Detailed description", 
    "priority": "low|medium|high|urgent",
    "equipment_id": "equipment_id if mentioned",
    "location": "location if mentioned",
    "estimated_duration_hours": hours_if_mentioned
}}

If this is a request to update workorders, respond with JSON in this format:
{{
    "action": "update",
    "query": "what to update or filter by",
    "updates": {{
        "status": "new_status_if_mentioned",
        "notes": "additional_notes"
    }}
}}

If this is a request to list workorders, respond with JSON:
{{
    "action": "list",
    "filters": {{
        "status": "status_filter_if_mentioned",
        "priority": "priority_filter_if_mentioned"
    }}
}}

Only respond with valid JSON, no other text.
"""
        
        try:
            # Use the agent to process the request
            response = await self.agent.send_message(
                content=[types.Part.from_text(prompt)]
            )
            
            # Extract JSON from response
            response_text = response.candidates[0].content.parts[0].text.strip()
            
            # Clean up response to extract JSON
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()
            
            result = json.loads(response_text)
            logger.info(f"Processed workorder request: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing workorder request: {e}")
            # Return a default create action if parsing fails
            return {
                "action": "create",
                "title": "Manual Workorder",
                "description": user_message,
                "priority": "medium"
            }
    
    async def generate_workorder_summary(self, workorders: List[Workorder]) -> str:
        """Generate a summary of workorders using the agent"""
        
        if not workorders:
            return "No workorders found for this investigation."
        
        workorder_data = []
        for wo in workorders:
            workorder_data.append({
                "id": wo.id,
                "title": wo.title,
                "status": wo.status.value,
                "priority": wo.priority.value,
                "created": wo.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        
        prompt = f"""
Provide a concise summary of these workorders:

{json.dumps(workorder_data, indent=2)}

Include:
- Total number of workorders
- Breakdown by status and priority
- Any urgent items that need attention
- Brief overview of main tasks

Keep the summary under 200 words.
"""
        
        try:
            response = await self.agent.send_message(
                content=[types.Part.from_text(prompt)]
            )
            
            summary = response.candidates[0].content.parts[0].text.strip()
            return summary
            
        except Exception as e:
            logger.error(f"Error generating workorder summary: {e}")
            return f"Found {len(workorders)} workorders. Check individual items for details."


# Singleton instance
_workorder_agent = None

def get_workorder_agent() -> WorkorderAgent:
    """Get or create the workorder agent instance"""
    global _workorder_agent
    if _workorder_agent is None:
        _workorder_agent = WorkorderAgent()
    return _workorder_agent
