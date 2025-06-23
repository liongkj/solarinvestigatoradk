from google.adk.agents import Agent
from adk.problem_finder.toolbox import tools
from .prompts import return_instruction_daily_pr
from adk.callbacks import summarize_agent_output_callback
# ['compare_daily_inverter_performance', 'get_all_alarms', 'get_daily_plant_summary', 'get_detailed_plant_timeseries', 'get_inverters_alarms', 'list_available_plants', 'list_inverters_for_plant', 'track_single_inverter_performance']


daily_pr_agent = Agent(
    name="daily_pr_agent",
    model="gemini-2.5-flash-preview-05-20",
    description="You are agent to retrieve daily and monthly PR data for specific plant",
    instruction=return_instruction_daily_pr(),
    tools=[
        tools[2],
        tools[5],
    ],
    after_agent_callback=summarize_agent_output_callback,
    output_key="daily_pr_agent_output",
)
