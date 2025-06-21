from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

from adk.problem_finder.toolbox import tools

from .prompts import return_instruction_detailed_plant_timeseries
from .tools import append_problematic_rows, filter_plant_timeseries_data


def setup(callback_context: CallbackContext):
    # TODO marcus: access context.state
    # https://google.github.io/adk-docs/sessions/state/#how-state-is-updated-recommended-methods
    if "problematic_five_minutes_pr" not in callback_context.state:
        problematic_five_minutes_pr_settings = []
        callback_context.state["problematic_five_minutes_pr"] = (
            problematic_five_minutes_pr_settings
        )
    callback_context.state["filtered_plant_timeseries_df"] = None


detailed_plant_timeseries_agent = Agent(
    name="detailed_plant_timeseries_agent",
    model="gemini-2.5-flash-preview-05-20",
    description="You are an expert in retrieving detailed data for target days for specific plants",
    instruction=return_instruction_detailed_plant_timeseries(),
    tools=[
        tools[3],
        tools[5],
        # filter_plant_timeseries_data,
        append_problematic_rows,
    ],
    before_agent_callback=setup,
    output_key="detailed_plant_timeseries_agent_output",
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)

# line 20->line 26 -> line 20 -> line 28-> line 20
# TODO marcus:
# use after tool callback
# agent_timeseries

# before callback -> None

# tools[3] -> dict["result"] -> result

# after toolcallback(response) -> filter_plant_timeseries_data(response) -> modfied_response
