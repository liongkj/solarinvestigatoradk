from io import BytesIO

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext

from .prompts import return_instruction_coding
from .tools import save_generated_report_local


def setup(callback_context: CallbackContext):
    """setup for coding agent"""
    callback_context.state["report_bytes"] = BytesIO()
    callback_context.state["html_daily_inverter"] = ""
    callback_context.state["html_detailed_inverter"] = ""
    callback_context.state["html_daily_pr"] = ""
    callback_context.state["html_detailed_plant_timeseries"] = ""


code_agent = Agent(
    name="code_agent",
    model="gemini-2.5-flash-preview-05-20",
    instruction=return_instruction_coding(),
    output_key='final_html',
    after_agent_callback=save_generated_report_local,
)
