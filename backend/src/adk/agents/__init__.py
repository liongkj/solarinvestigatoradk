"""ADK Agents module - Solar Investigation"""

try:
    from .solar_investigation_agent import (
        SolarInvestigationAgent,
        get_solar_investigation_agent,
        investigate_solar_project,
    )

    __all__ = [
        "SolarInvestigationAgent",
        "get_solar_investigation_agent",
        "investigate_solar_project",
    ]
except ImportError as e:
    # Handle case where ADK is not fully installed
    print(f"Warning: Could not import ADK agents: {e}")
    __all__ = []

    # Provide mock implementations for development
    class SolarInvestigationAgent:
        def __init__(self, name="solar_investigator"):
            self.name = name

    def create_solar_agent():
        return SolarInvestigationAgent()

    # def create_solar_investigation_agent():
    #     return SolarInvestigationAgent()

    __all__ = [
        "SolarInvestigationAgent",
        "create_solar_agent",
        # "create_solar_investigation_agent",
    ]
