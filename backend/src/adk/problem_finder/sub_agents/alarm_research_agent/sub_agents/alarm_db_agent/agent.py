import os
from google.adk.agents import Agent
from pydantic import BaseModel



model_name = os.getenv("ANALYTICS_AGENT_MODEL")
if model_name is None:
    raise ValueError("Environment variable 'ANALYTICS_AGENT_MODEL' must be set.")

root_agent = Agent(
    model="gemini-2.0-flash",
    name="databasemcp_agent",
    instruction="""
    You are a helpful Model Context Protocol (MCP) agent that retrieves data from database.
    """,
)