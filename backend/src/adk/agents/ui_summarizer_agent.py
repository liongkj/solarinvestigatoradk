"""Specialized UI Summarizer Agent for generating concise UI-friendly summaries"""

import logging
from google.adk.agents import LlmAgent

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
    """Generate a 10-word summary of an agent response using a lightweight approach"""
    try:
        prompt = f"""Create a 10-word summary of this agent response:
        
{agent_response}

Remember: EXACTLY 10 words maximum, focus on main action/finding."""

        # Simple client-side truncation for now - TODO: integrate with agent when state management is clarified
        # This provides immediate functionality while avoiding complex session management

        # Extract key information from the response
        words = agent_response.strip().split()

        # Simple heuristic-based summarization
        if "error" in agent_response.lower() or "failed" in agent_response.lower():
            summary = "Error occurred during agent processing operation"
        elif (
            "completed" in agent_response.lower()
            or "analysis" in agent_response.lower()
        ):
            if "solar" in agent_response.lower():
                summary = "Solar analysis completed with findings and recommendations"
            else:
                summary = (
                    "Analysis completed with findings and recommendations available"
                )
        elif (
            "analyzing" in agent_response.lower()
            or "processing" in agent_response.lower()
        ):
            summary = "Agent currently analyzing data and processing request"
        elif "investigating" in agent_response.lower():
            summary = "Investigation in progress gathering data and insights"
        else:
            # Fallback: take first meaningful words
            meaningful_words = [w for w in words[:15] if len(w) > 2][:10]
            if len(meaningful_words) >= 6:
                summary = " ".join(meaningful_words[:10])
            else:
                summary = "Agent response processed successfully"

        # Ensure exactly 10 words or fewer
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
