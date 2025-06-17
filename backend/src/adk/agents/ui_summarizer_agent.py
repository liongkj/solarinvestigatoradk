"""Specialized UI Summarizer Agent for generating concise UI-friendly summaries"""

import logging
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

logger = logging.getLogger(__name__)


def create_ui_summarizer_agent() -> LlmAgent:
    """Create a specialized UI summarizer agent following ADK patterns"""

    instruction = """You are a specialized UI summarizer agent. Your only job is to create extremely concise 10-word summaries of agent responses for user interface display.

RULES:
1. Output EXACTLY 10 words maximum
2. Focus on the main action or finding
3. Use present tense, active voice
4. Include key outcomes or status
5. Be specific and actionable
6. NO extra formatting, just the summary text

EXAMPLES:
Input: "I've completed the solar feasibility analysis for Plant ABC. The site shows excellent solar potential with 4.2 kWh/m²/day average irradiation. The recommended 100kW system would generate approximately 146,000 kWh annually, resulting in $18,500 yearly savings. The payback period is estimated at 6.8 years. I recommend proceeding with the installation."
Output: "Solar analysis complete: excellent potential, 6.8 year payback recommended"

Input: "I'm currently analyzing the site's solar irradiation data and weather patterns to determine the optimal panel configuration..."
Output: "Analyzing solar irradiation data for optimal panel configuration recommendations"

Input: "Error: Unable to access plant location data. Please verify the plant ID and ensure proper permissions are configured."
Output: "Error accessing plant data: verify ID and permissions"

Always respond with EXACTLY the summary - no additional text or formatting."""

    return LlmAgent(
        model="gemini-1.5-flash",
        name="ui_summarizer",
        description="Generates 10-word UI summaries from agent responses",
        instruction=instruction,
    )


async def generate_ui_summary(agent_response: str) -> str:
    """Generate a 10-word summary of an agent response using the summarizer agent"""
    try:
        # Create agent and runner
        agent = create_ui_summarizer_agent()
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent, app_name="ui_summarizer_app", session_service=session_service
        )

        prompt = f"""Create a 10-word summary of this agent response:
        
{agent_response}

Remember: EXACTLY 10 words maximum, focus on main action/finding."""

        user_content = types.Content(role="user", parts=[types.Part(text=prompt)])

        # Run the summarizer agent
        summary = "Agent response processing completed"  # Default fallback
        async for event in runner.run_async(
            user_id="summarizer_user",
            session_id="summarizer_session",
            new_message=user_content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                summary = event.content.parts[0].text or "Summary generation failed"
                break

        # Clean and truncate to ensure 10 words max
        words = summary.strip().split()
        if len(words) > 10:
            summary = " ".join(words[:10])

        return summary

    except Exception as e:
        logger.error(f"Error generating UI summary: {e}")
        return "Summary generation failed"


def get_ui_summarizer_agent() -> LlmAgent:
    """Factory function to create and return a UI summarizer agent"""
    return create_ui_summarizer_agent()
