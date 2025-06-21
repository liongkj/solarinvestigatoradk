from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from adk.problem_finder.toolbox import tools
# from solar_investigator.tools import tools

from .prompts import return_instruction_detailed_inverter_performance
from .tools import append_problematic_rows


def setup(callback_context: CallbackContext):
    if "problematic_detailed_inverter_performance" not in callback_context.state:
        problematic_detailed_inverter_settings = []
        callback_context.state["problematic_detailed_inverter_performance"] = (
            problematic_detailed_inverter_settings
        )


detailed_inverter_performance_agent = Agent(
    name="detailed_inverter_performance_agent",
    model="gemini-2.5-flash-preview-05-20",
    instruction=return_instruction_detailed_inverter_performance(),
    tools=[tools[7], append_problematic_rows],
    before_agent_callback=setup,
    output_key="detailed_inverter_performance_agent_output",
)
