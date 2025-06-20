"""
Solar Investigation Agent - Simple ADK Implementation
Following the sample documentation pattern
"""

import json
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# from google.genai.adk import RunConfig, StreamingMode
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# --- Input Schema ---


def create_solar_investigation_agent(
    output_key: str = "solar_investigation_result", after_agent_callback=None
) -> LlmAgent:
    """Create a solar investigation agent following ADK best practices."""

    return LlmAgent(
        model="gemini-2.0-flash",  # Using ADK-compatible Gemini model
        name="solar_investigation_agent",
        description="Analyzes solar installation feasibility and provides comprehensive recommendations",
        instruction="""You are a Solar Investigation Expert AI assistant that helps evaluate solar installation opportunities.

When a user provides property details (typically in JSON format), analyze the information and provide a comprehensive solar feasibility assessment.

Your analysis should include:
1. Property suitability assessment based on location and usage patterns
2. Estimated solar system size and energy production potential  
3. Financial analysis including payback period and savings estimates
4. Available incentives and rebate programs
5. Clear recommendations and next steps

Always:
- Be realistic and honest about solar potential
- Explain your assumptions and reasoning clearly
- Provide practical, actionable advice
- Use a friendly but professional tone
- Structure your response clearly with headings and bullet points
- Include specific numbers and estimates when possible

If information is missing or unclear, ask clarifying questions or make reasonable assumptions and state them explicitly.

Focus on helping users make informed decisions about solar energy investments.""",
        tools=[],  # Tools will be added when available
        output_key=output_key,  # Save result to session state
        after_agent_callback=after_agent_callback,  # ADK callback for UI processing
    )


def get_solar_investigation_agent(
    output_key: str = "solar_investigation_result", after_agent_callback=None
) -> LlmAgent:
    """Get the solar investigation agent with optional callback support."""
    return create_solar_investigation_agent(
        output_key, after_agent_callback
    )  # TODO: Change entry point to this function


class SolarInvestigationAgent:
    """Wrapper class for compatibility."""

    def __init__(self, name: str = "SolarInvestigator"):
        self.agent = get_solar_investigation_agent()
        self.name = name

    def get_agent(self) -> LlmAgent:
        return self.agent


# Uncomment to run demo
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(demo_solar_investigation())
