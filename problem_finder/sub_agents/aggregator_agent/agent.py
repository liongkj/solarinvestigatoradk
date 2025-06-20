from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from dotenv import load_dotenv

from .prompt import return_aggregator_prompt

import os

aggregator_agent = Agent(
    name="aggregator_agent",
    model="gemini-2.5-flash-preview-05-20",
    description="Aggregator agent to summarize all reports.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2
    ),
    instruction=return_aggregator_prompt(),
    output_key="final_comprehensive_report"
)