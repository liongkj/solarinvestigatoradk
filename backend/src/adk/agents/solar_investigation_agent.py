# """
# Solar Investigation Agent - Simple ADK Implementation
# Following the sample documentation pattern
# """

# import json
# from google.adk.agents import LlmAgent, SequentialAgent
# from google.adk.runners import Runner
# from google.adk.sessions import InMemorySessionService
# from google.genai import types
# from adk.problem_finder.agent import root_agent
# # from google.genai.adk import RunConfig, StreamingMode
# from pydantic import BaseModel, Field
# import logging

# logger = logging.getLogger(__name__)


# # --- Input Schema ---


# def get_solar_investigation_agent(
# ) -> SequentialAgent:
#     """Get the solar investigation agent with optional callback support."""
#     return root_agent

# class SolarInvestigationAgent:
#     """Wrapper class for compatibility."""

#     def __init__(self, name: str = "SolarInvestigator"):
#         self.agent = get_solar_investigation_agent()
#         self.name = name

#     def get_agent(self) -> LlmAgent:
#         return self.agent


# # Uncomment to run demo
# # if __name__ == "__main__":
# #     import asyncio
# #     asyncio.run(demo_solar_investigation())
