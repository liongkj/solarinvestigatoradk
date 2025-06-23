from datetime import date

from adk.callbacks.summarizer import summarize_agent_output_callback
from adk.models.investigation import Investigation
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import types
from google.adk.tools.tool_context import ToolContext
from toolbox_core import ToolboxSyncClient
from .prompts import return_instruction_planner
from .sub_agents import (
    aggregator_agent,
    alarm_research_agent,
    daily_pr_agent,
    detailed_inverter_performance_agent,
    detailed_plant_timeseries_agent,
)

TOOLBOX_URL = "https://agentmcp.liongkj.com"

# Initialize Toolbox client
toolbox = ToolboxSyncClient(TOOLBOX_URL)
# Load all the tools from toolset
tools = toolbox.load_toolset()

# ['compare_daily_inverter_performance', 'get_all_alarms', 'get_daily_plant_summary', 'get_detailed_plant_timeseries', 'get_inverters_alarms', 'list_available_plants', 'list_inverters_for_plant', 'track_single_inverter_performance']
# TOOLS LIST:
# 0  comparing daily inverter performance
# 1  get all alarm
# 2  get daily plant summary
# 3  get detailed plant timeseries
# 4  get inverters alarms
# 5  list available plant
# 6  list inverters for plant
# 7  track single inverter performance


alarm_researcher = SequentialAgent(
    name="alarm_researcher",
    description="You are a sequential agent that coordinates the execution of the alarm_research_agent.",
    sub_agents=[
        alarm_research_agent,
        detailed_inverter_performance_agent,
    ],
)

parallel_pipeline = ParallelAgent(
    name="parallel_pipeline",
    sub_agents=[
        detailed_plant_timeseries_agent,
        alarm_researcher,
    ],
)


def store_inverter_device_id_and_capacity_peak(tool_context: ToolContext, data: dict):
    """Store inverter device id and capacity peak in the tool context state.

    args:
        tool_context (ToolContext): The context of the tool where the state is stored.
        data (dict): A dictionary containing inverter device ids and their corresponding capacity peaks.
    """
    if "inverter_device_id_and_capacity_peak" not in tool_context.state:
        tool_context.state["inverter_device_id_and_capacity_peak"] = str(data)
    tool_context.state["inverter_device_id_and_capacity_peak"] = str(data)


planner_agent = Agent(
    name="planner_agent",
    model="gemini-2.5-flash-preview-05-20",
    instruction=return_instruction_planner(),
    description="You are an expert planner",
    output_key="planner_agent_output",
    after_agent_callback=summarize_agent_output_callback,
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
    tools=[tools[5], tools[6], store_inverter_device_id_and_capacity_peak],
)

root_agent = SequentialAgent(
    name="problem_finder",
    sub_agents=[
        planner_agent,
        daily_pr_agent,
        parallel_pipeline,
        aggregator_agent,
    ],
)
