from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from adk.callbacks import summarize_agent_output_callback
from adk.problem_finder.toolbox import tools

from .prompts import return_instruction_detailed_plant_timeseries
from .tools import append_problematic_rows, filter_plant_timeseries_data


def setup(callback_context: CallbackContext):
    if "problematic_five_minutes_pr" not in callback_context.state:
        problematic_five_minutes_pr_settings = []
        callback_context.state["problematic_five_minutes_pr"] = (
            problematic_five_minutes_pr_settings
        )
    if "filtered_plant_timeseries_df" not in callback_context.state:
        callback_context.state["filtered_plant_timeseries_df"] = None


detailed_plant_timeseries_agent = Agent(
    name="detailed_plant_timeseries_agent",
    model="gemini-2.5-flash-preview-05-20",
    description="You are an expert in retrieving detailed data for target days for specific plants",
    instruction=return_instruction_detailed_plant_timeseries(),
    tools=[
        tools[3],
        filter_plant_timeseries_data,
        append_problematic_rows,
    ],
    before_agent_callback=setup,
    output_key="detailed_plant_timeseries_agent_output",
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
    after_agent_callback=summarize_agent_output_callback,
)
