"""Workorder processing agent using Google ADK"""

import logging
from typing import Dict, Any
from datetime import datetime
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)


class WorkorderAgent:
    """Agent for processing workorder requests and generating actionable tasks"""

    def __init__(self):
        """Initialize the workorder agent with hardcoded prompt"""
        self.agent = LlmAgent(
            name="WorkorderAgent",
            model="gemini-2.0-flash",
            description="Specialized agent for processing solar plant workorder requirements",
            instruction="""
You are a specialized workorder processing agent for solar power plant maintenance and operations.

Your role is to:
1. Analyze maintenance requirements and todo summaries
2. Break down tasks into actionable workorder steps
4. Consider safety, efficiency, and regulatory compliance

When given a maintenance requirement or todo summary, provide:
- Step-by-step actionable tasks
- Safety considerations
- Required tools/resources
- Estimated timeline
- Priority recommendations

Process this maintenance requirement and provide actionable tasks concisely.
""",
        )

        # Session service for agent execution
        self.session_service = InMemorySessionService()

    async def process_workorder(self, todo_summary: str, investigation_id: str) -> str:
        """
        Process a workorder todo summary and return agent recommendations

        Args:
            todo_summary: The maintenance/work requirement summary
            investigation_id: ID of the related investigation

        Returns:
            Agent response with actionable workorder recommendations
        """
        try:
            logger.info(f"Processing workorder for investigation {investigation_id}")

            # Generate consistent session ID
            session_id = f"workorder_{investigation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Create a session for this workorder processing
            session = await self.session_service.create_session(
                app_name="workorder_agent", user_id="system", session_id=session_id
            )

            # Create runner for the agent
            runner = Runner(
                agent=self.agent,
                app_name="workorder_agent",
                session_service=self.session_service,
            )

            # Prepare user message with todo summary (following investigation service pattern)
            user_message = types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=f"Process this workorder requirement: {todo_summary}"
                    )
                ],
            )

            # Run the agent and collect the response (following investigation service pattern)
            agent_response = ""
            final_response = None

            async for event in runner.run_async(
                user_id="system",
                session_id=session_id,  # Use the session_id string, not session.id
                new_message=user_message,
            ):
                # Handle final response (following investigation service pattern)
                if event.is_final_response() and event.content and event.content.parts:
                    final_response = event.content.parts[0].text
                    break

            # Process the final response
            if final_response and len(final_response.strip()) > 0:
                agent_response = final_response.strip()

            if not agent_response:
                logger.warning("No response from workorder agent")
                agent_response = "Workorder processing completed. Please review the requirements manually."

            logger.info(
                f"Workorder agent completed processing for investigation {investigation_id}"
            )
            return agent_response

        except Exception as e:
            logger.error(f"Error processing workorder with agent: {e}")
            return f"Error processing workorder: {str(e)}. Please review the requirements manually."
