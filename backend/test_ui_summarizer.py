#!/usr/bin/env python3
"""
Test script for UI Summary functionality
"""

import asyncio
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from adk.agents.ui_summarizer_agent import generate_ui_summary


async def test_ui_summarizer():
    """Test the UI summarizer agent with various agent responses"""

    test_responses = [
        # Solar analysis completion
        """I've completed the solar feasibility analysis for Plant ABC. The site shows excellent solar potential with 4.2 kWh/m²/day average irradiation. The recommended 100kW system would generate approximately 146,000 kWh annually, resulting in $18,500 yearly savings. The payback period is estimated at 6.8 years. I recommend proceeding with the installation.""",
        # In-progress analysis
        """I'm currently analyzing the site's solar irradiation data and weather patterns to determine the optimal panel configuration. The preliminary data suggests good solar potential, but I need to complete the shadow analysis and roof structure assessment before providing final recommendations.""",
        # Error scenario
        """Error: Unable to access plant location data. Please verify the plant ID and ensure proper permissions are configured. The investigation cannot proceed without valid location coordinates and site specifications.""",
        # Technical assessment
        """Based on the site analysis, I recommend a 250kW solar installation with 625 panels oriented at 35° azimuth. The system would require 5 inverters and generate approximately 325,000 kWh annually. Estimated installation cost: $375,000 with a 7.2-year payback period.""",
        # Short response
        """Analysis complete. Proceeding to next phase.""",
    ]

    print("🧪 Testing UI Summarizer Agent")
    print("=" * 50)

    for i, response in enumerate(test_responses, 1):
        print(f"\n📝 Test {i}:")
        print(f"Original Response: {response[:100]}...")

        try:
            summary = await generate_ui_summary(response)
            word_count = len(summary.split())

            print(f"✅ UI Summary ({word_count} words): {summary}")

            if word_count > 10:
                print(f"⚠️  Warning: Summary exceeds 10 words")

        except Exception as e:
            print(f"❌ Error: {e}")

    print("\n" + "=" * 50)
    print("✅ UI Summarizer test completed!")


if __name__ == "__main__":
    asyncio.run(test_ui_summarizer())
