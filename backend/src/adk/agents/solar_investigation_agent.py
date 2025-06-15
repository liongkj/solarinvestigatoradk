"""
Solar Investigation Agent - Simple ADK Implementation
Following the sample documentation pattern
"""

import json
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


# --- Input Schema ---


class SolarInvestigationInput(BaseModel):
    """Input schema for solar investigation requests."""

    address: str = Field(description="Property address for solar investigation")
    monthly_usage: float = Field(description="Monthly energy usage in kWh")
    property_type: str = Field(
        default="residential",
        description="Property type: residential, commercial, or industrial",
    )


# --- Tool Functions (Simple Python Functions) ---


def analyze_solar_feasibility(
    address: str, monthly_usage: float, property_type: str = "residential"
) -> dict:
    """
    Analyze solar installation feasibility for a property.

    Args:
        address (str): Property address
        monthly_usage (float): Monthly energy usage in kWh
        property_type (str): Type of property

    Returns:
        dict: Feasibility analysis results
    """
    print(
        f"-- Tool Call: analyze_solar_feasibility(address='{address}', usage={monthly_usage} kWh) --"
    )

    # Simple feasibility calculation
    # Assume 1kW system produces ~130 kWh/month on average
    required_system_size = monthly_usage / 130

    # Basic cost estimation ($3.50 per watt)
    estimated_cost = required_system_size * 1000 * 3.50
    federal_credit = estimated_cost * 0.30  # 30% federal tax credit
    net_cost = estimated_cost - federal_credit

    # Annual savings estimation
    annual_usage = monthly_usage * 12
    annual_savings = annual_usage * 0.12  # Assume $0.12/kWh
    payback_years = net_cost / annual_savings if annual_savings > 0 else 25

    # Determine feasibility score
    if payback_years <= 7:
        feasibility = "Excellent"
        score = 90
    elif payback_years <= 10:
        feasibility = "Good"
        score = 75
    elif payback_years <= 15:
        feasibility = "Fair"
        score = 60
    else:
        feasibility = "Poor"
        score = 40

    result = {
        "address": address,
        "monthly_usage_kwh": monthly_usage,
        "property_type": property_type,
        "feasibility_rating": feasibility,
        "feasibility_score": score,
        "recommended_system_size_kw": round(required_system_size, 1),
        "estimated_cost": f"${estimated_cost:,.0f}",
        "federal_tax_credit": f"${federal_credit:,.0f}",
        "net_cost_after_incentives": f"${net_cost:,.0f}",
        "estimated_annual_savings": f"${annual_savings:,.0f}",
        "payback_period_years": round(payback_years, 1),
        "assumptions": [
            "Average solar production: 130 kWh/month per kW installed",
            "Installation cost: $3.50/watt",
            "30% Federal Investment Tax Credit",
            "Electricity rate: $0.12/kWh",
        ],
    }

    print(
        f"-- Tool Result: {feasibility} feasibility, {payback_years:.1f} year payback --"
    )
    return result


def get_solar_incentives(address: str) -> dict:
    """
    Get available solar incentives for a location.

    Args:
        address (str): Property address

    Returns:
        dict: Available incentives information
    """
    print(f"-- Tool Call: get_solar_incentives(address='{address}') --")

    # Extract state from address (simplified)
    state_incentives = {
        "CA": {
            "state_rebate": "SGIP battery storage rebate available",
            "net_metering": "NEM 3.0 - reduced export rates",
            "property_tax": "Property tax exemption for solar installations",
        },
        "TX": {
            "state_rebate": "No state rebate programs",
            "net_metering": "Varies by utility company",
            "property_tax": "Property tax exemption available",
        },
        "FL": {
            "state_rebate": "No state rebate programs",
            "net_metering": "Full retail rate net metering",
            "property_tax": "Property tax exemption available",
        },
        "NY": {
            "state_rebate": "NY-Sun incentive program",
            "net_metering": "Full retail rate net metering",
            "property_tax": "Property tax exemption available",
        },
    }

    # Simple state detection (this would be more sophisticated in real implementation)
    detected_state = "General"
    for state in state_incentives.keys():
        if state in address.upper():
            detected_state = state
            break

    result = {
        "address": address,
        "detected_location": detected_state,
        "federal_incentives": {
            "investment_tax_credit": "30% through 2032, then 26% in 2033, 22% in 2034"
        },
        "state_incentives": state_incentives.get(
            detected_state,
            {
                "state_rebate": "Check local utility programs",
                "net_metering": "Check with local utility",
                "property_tax": "Varies by jurisdiction",
            },
        ),
        "recommendations": [
            "Consult with local solar installer for specific incentives",
            "Check utility company net metering policies",
            "Research local property tax exemptions",
        ],
    }

    print(f"-- Tool Result: Incentives found for {detected_state} --")
    return result


# --- Create the Solar Investigation Agent ---


def create_solar_investigation_agent() -> LlmAgent:
    """Create a solar investigation agent following ADK best practices."""

    return LlmAgent(
        model="gemini-2.0-flash",
        name="solar_investigation_agent",
        description="Analyzes solar installation feasibility and provides recommendations",
        instruction="""You are a Solar Investigation Expert that helps people evaluate solar installation opportunities.

When a user provides property details in JSON format, use your tools to:
1. First, use 'analyze_solar_feasibility' to assess the property's solar potential
2. Then, use 'get_solar_incentives' to find available rebates and programs
3. Provide a clear, comprehensive summary with actionable recommendations

Always be realistic about solar potential and clearly explain your assumptions.
Focus on practical advice that helps users make informed decisions.

Present your findings in a friendly, professional manner with clear next steps.""",
        tools=[analyze_solar_feasibility, get_solar_incentives],
        input_schema=SolarInvestigationInput,
        output_key="solar_investigation_result",
    )


# --- Session Service and Runner Setup ---


def create_solar_investigation_service():
    """Create session service and runner for the solar investigation agent."""

    # Create the agent
    agent = create_solar_investigation_agent()

    # Create session service
    session_service = InMemorySessionService()

    # Create runner
    runner = Runner(
        agent=agent, app_name="solar_investigation_app", session_service=session_service
    )

    return agent, session_service, runner


# --- Helper Function for Easy Usage ---


async def investigate_solar_project(
    address: str, monthly_usage: float, property_type: str = "residential"
):
    """
    Helper function to investigate a solar project.

    Args:
        address: Property address
        monthly_usage: Monthly energy usage in kWh
        property_type: Type of property

    Returns:
        Investigation results
    """
    # Create service components
    agent, session_service, runner = create_solar_investigation_service()

    # Create session
    session_id = "solar_investigation_session"
    user_id = "solar_user"
    await session_service.create_session(
        app_name="solar_investigation_app", user_id=user_id, session_id=session_id
    )

    # Prepare the query
    query = {
        "address": address,
        "monthly_usage": monthly_usage,
        "property_type": property_type,
    }

    # Send query to agent
    user_content = types.Content(
        role="user", parts=[types.Part(text=json.dumps(query))]
    )

    final_response = "No response received"
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=user_content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return final_response


# --- Demo/Test Function ---


async def demo_solar_investigation():
    """Demo function to test the solar investigation agent."""

    print("🌞 Solar Investigation Agent Demo")
    print("=" * 50)

    # Test case 1: Residential property
    print("\n📋 Test Case 1: Residential Property")
    result1 = await investigate_solar_project(
        address="123 Main St, San Jose, CA 95120",
        monthly_usage=850,
        property_type="residential",
    )
    print("Result:", result1)

    # Test case 2: Commercial property
    print("\n📋 Test Case 2: Commercial Property")
    result2 = await investigate_solar_project(
        address="456 Business Blvd, Austin, TX 78701",
        monthly_usage=2500,
        property_type="commercial",
    )
    print("Result:", result2)


# --- Export Functions ---


def get_solar_investigation_agent() -> LlmAgent:
    """Get the solar investigation agent."""
    return create_solar_investigation_agent()


# --- Compatibility Wrapper (if needed) ---


class SolarInvestigationAgent:
    """Wrapper class for compatibility."""

    def __init__(self, name: str = "SolarInvestigator"):
        self.agent = create_solar_investigation_agent()
        self.name = name

    def get_agent(self) -> LlmAgent:
        return self.agent


# Uncomment to run demo
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(demo_solar_investigation())
