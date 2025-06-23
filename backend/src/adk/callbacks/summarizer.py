from adk.config import settings
from google.adk.agents import Agent
from google.genai import types
from pydantic import BaseModel, Field
from typing import Dict, Any, List
import json
import logging
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event, EventActions
from datetime import datetime

from google.adk.sessions import DatabaseSessionService
import asyncio

logger = logging.getLogger(__name__)


class AgentActionSummary(BaseModel):
    """Structured output model for agent action summary"""

    main_theme: str = Field(
        description="The main theme or primary focus of the agent's actions"
    )
    action_taken: str = Field(
        description="The specific action that was performed by the agent"
    )
    action_type: str = Field(
        description="The type/category of action (e.g., analysis, investigation, data_processing, reporting, monitoring, diagnosis)"
    )
    description_first_party: str = Field(
        description="A detailed description of what the agent is doing current step, limited to 300 characters",
    )
    next_steps: str = Field(
        default=...,
        description="Optional next steps or recommendations based on the agent's actions, if applicable",
    )
    description_events: List[str] = Field(
        description="A list of concise descriptions of the agent's actions, suitable for event logging"
    )


def get_structured_summarizer_prompt() -> str:
    """Generate the prompt for the structured summarizer agent"""
    return """
You are a Structured Summarizer Agent responsible for analyzing agent outputs and creating structured summaries.

When given an agent's output, you must respond with a JSON object that matches this exact schema:
{
  "main_theme": "string - The main theme or primary focus of the agent's actions",
  "action_taken": "string - The specific action that was performed by the agent", 
  "action_type": "string - One of: analysis, investigation, data_processing, reporting, monitoring, diagnosis, optimization, maintenance, planning",
  "description_first_party": "string - A brief description of what the agent accomplished, STRICTLY limited to 300 characters maximum. Be concise and informative, focusing on key outcomes and findings.",
  "next_steps": "string - Optional next steps or recommendations based on the agent's actions, if applicable",
  "description_events": "array of strings - Each item STRICTLY limited to 50 characters maximum. Should be concise, specific, and capture key actions or findings. Include relevant context like system names, dates, or specific issues when possible."
}

Action type categories:
- analysis: Analyzing data, patterns, or performance metrics
- investigation: Investigating issues, problems, or anomalies  
- data_processing: Processing, transforming, or organizing data
- reporting: Generating reports, summaries, or documentation
- monitoring: Monitoring systems, metrics, or performance
- diagnosis: Diagnosing problems, issues, or system health
- optimization: Optimizing performance or configurations
- maintenance: Performing maintenance or updates
- planning: Creating plans, procedures, or structured approaches

CHARACTER LIMITS ARE MANDATORY:
- description_first_party: Maximum 300 characters (count carefully)
- description_events: Each item maximum 50 characters (count carefully)

Guidelines for effective summaries:
1. Be specific - include system names, dates, quantities when relevant
2. Focus on outcomes and findings, not just actions
3. Use active voice and clear, technical language
4. Prioritize the most important information within character limits
5. For events, capture the essence of each major step or finding

CRITICAL: Validate character counts before responding. Truncate if necessary to meet limits.

IMPORTANT: Respond ONLY with the JSON object, no additional text or formatting.
"""


# Create the structured summarizer agent
structured_summarizer_agent = Agent(
    name="structured_summarizer_agent",
    model="gemini-2.5-flash-preview-05-20",
    description="Agent that creates structured summaries of other agent outputs",
    # generate_content_config=types.GenerateContentConfig(temperature=0.1),
    instruction=get_structured_summarizer_prompt(),
    output_key="structured_summary",
)

# In-memory storage for agent summaries
_agent_summaries: Dict[str, AgentActionSummary] = {}


def _run_summarizer_agent(agent_name: str, agent_output: str) -> AgentActionSummary:
    """Run the ADK summarizer agent to generate structured summary"""
    try:
        # Create a session for the agent
        session_service = InMemorySessionService()

        # Create runner with proper parameters
        runner = Runner(
            agent=structured_summarizer_agent,
            app_name="summarizer_app",
            session_service=session_service,
        )

        # Prepare the input for the summarizer agent
        summarizer_input = f"""
            Agent Name: {agent_name}
            Agent Output:
            {agent_output}

            Analyze this agent output and provide a structured summary.
        """

        # Create Content object for the message
        user_content = types.Content(
            role="user", parts=[types.Part(text=summarizer_input)]
        )
        session = session_service.create_session_sync(
            app_name="summarizer_app", user_id="summarizer_user"
        )
        # Run the agent using the correct method
        final_response_text = ""
        for event in runner.run(
            user_id="summarizer_user",
            session_id=session.id,
            new_message=user_content,
        ):
            # Accumulate response text from events
            if (
                hasattr(event, "content")
                and event.content
                and hasattr(event.content, "parts")
                and event.content.parts
            ):
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_response_text += part.text

        # Extract the structured summary from the result
        if final_response_text.strip():
            try:
                # Try to parse the JSON response
                # Check if the response is within a JSON code block
                response_text = final_response_text.strip()
                if response_text.startswith("```json") and response_text.endswith(
                    "```"
                ):
                    response_text = response_text[7:-3].strip()
                summary_data = json.loads(response_text.strip())
                summary = AgentActionSummary(**summary_data)
                return summary
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse agent response as JSON: {e}")
                logger.warning(f"Response was: {final_response_text[:200]}...")
                # Fall back to rule-based approach
                return _create_fallback_summary(agent_name, agent_output)
        else:
            logger.warning("No content in agent response, using fallback")
            return _create_fallback_summary(agent_name, agent_output)

    except Exception as e:
        logger.error(f"Error running summarizer agent: {e}")
        return _create_fallback_summary(agent_name, agent_output)


def _create_fallback_summary(agent_name: str, agent_output: str) -> AgentActionSummary:
    """Create a summary using rule-based approach as fallback"""
    output_lower = agent_output.lower()

    # Determine action type based on content analysis
    if any(
        word in output_lower
        for word in ["analyzing", "analysis", "examined", "studied"]
    ):
        action_type = "analysis"
    elif any(
        word in output_lower
        for word in ["investigating", "investigation", "researched"]
    ):
        action_type = "investigation"
    elif any(
        word in output_lower
        for word in ["processing", "processed", "transformed", "organized"]
    ):
        action_type = "data_processing"
    elif any(
        word in output_lower
        for word in ["report", "summary", "documented", "generated"]
    ):
        action_type = "reporting"
    elif any(word in output_lower for word in ["monitoring", "tracked", "watching"]):
        action_type = "monitoring"
    elif any(
        word in output_lower for word in ["diagnosing", "diagnosis", "troubleshooting"]
    ):
        action_type = "diagnosis"
    elif any(
        word in output_lower for word in ["optimizing", "optimization", "improving"]
    ):
        action_type = "optimization"
    elif any(
        word in output_lower for word in ["maintenance", "updating", "maintaining"]
    ):
        action_type = "maintenance"
    else:
        action_type = "analysis"  # Default

    # Extract main theme and action based on content
    if "solar" in output_lower:
        if "investigation" in output_lower:
            main_theme = "Solar System Investigation"
            action_taken = "Investigated solar system performance and issues"
        elif "analysis" in output_lower:
            main_theme = "Solar Performance Analysis"
            action_taken = "Analyzed solar system performance data"
        else:
            main_theme = "Solar System Operations"
            action_taken = "Performed solar system operations"
    elif "plant" in output_lower:
        main_theme = "Plant Operations"
        action_taken = "Performed plant-related operations"
    elif "inverter" in output_lower:
        main_theme = "Inverter Analysis"
        action_taken = "Analyzed inverter performance and data"
    elif "alarm" in output_lower:
        main_theme = "Alarm Management"
        action_taken = "Processed and analyzed system alarms"
    else:
        main_theme = f"{agent_name} Operations"
        action_taken = f"Executed {agent_name} tasks"

    # Create structured summary
    return AgentActionSummary(
        main_theme=main_theme,
        action_taken=action_taken,
        action_type=action_type,
        description_first_party=(
            agent_output[:300] + "..." if len(agent_output) > 300 else agent_output
        ),
        next_steps="No specific next steps provided",
        description_events=[
            f"{action_taken} for {main_theme}",
            f"Action type: {action_type}",
            "Summary created using fallback method",
        ],
    )


# async def after_agent_callback(
#     agent_name: str, agent_output: str
# ) -> AgentActionSummary:
#     """
#     Agent-powered callback function that creates structured summary after agent execution

#     Args:
#         agent_name: Name of the agent that completed execution
#         agent_output: The output text from the agent

#     Returns:
#         AgentActionSummary: Structured summary of what the agent did
#     """
#     logger.info(f"Creating structured summary for agent: {agent_name}")

#     try:
#         # Use the ADK agent to generate the summary
#         summary = await _run_summarizer_agent(agent_name, agent_output)

#         # Store in memory for later retrieval
#         _agent_summaries[agent_name] = summary

#         logger.info(f"Summary created: {summary.main_theme} - {summary.action_type}")
#         return summary

#     except Exception as e:
#         logger.error(f"Error creating summary for {agent_name}: {e}")
#         # Fallback summary in case of error
#         fallback_summary = AgentActionSummary(
#             main_theme=f"{agent_name} Operations",
#             action_taken="Completed agent execution",
#             action_type="analysis",
#             description=f"Agent {agent_name} completed execution. Error: {str(e)}",
#         )
#         _agent_summaries[agent_name] = fallback_summary
#         return fallback_summary


def summarize_agent_output_callback(callback_context: CallbackContext) -> None:

    session_service = DatabaseSessionService(db_url=settings.database_url)
    agent_name = callback_context.agent_name
    invocation_id = callback_context.invocation_id
    current_state = callback_context.state.to_dict()

    print(f"\n[Callback] Exiting agent: {agent_name} (Inv: {invocation_id})")
    print(f"[Callback] Current State: {current_state}")

    if agent_output := current_state.get(f"{agent_name}_output"):

        summary = _run_summarizer_agent(agent_name, agent_output)

        # Ensure ui_summary is a list before appending
        if not isinstance(callback_context.state.get("ui_summary"), list):
            callback_context.state["ui_summary"] = []
        history = callback_context.state["ui_summary"]
        
        # Fix: Use model_dump() instead of model_dump_json() to get a dict, not a string
        summary_dict = summary.model_dump()
        summary_dict["timestamp"] = datetime.now().isoformat()
        history.append(summary_dict)
        
        callback_context.state["ui_summary"] = history