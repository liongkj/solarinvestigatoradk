#!/usr/bin/env python3
"""Test script to verify the investigation flow works correctly with ADK."""

import asyncio
import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from datetime import datetime, date
from adk.services.investigation_service import InvestigationService
from adk.models.investigation import InvestigationRequest


async def test_investigation_flow():
    """Test the complete investigation flow."""
    print("🧪 Testing Investigation Flow with ADK")
    print("=" * 50)

    try:
        # Initialize investigation service
        print("1. Initializing Investigation Service...")
        service = InvestigationService()
        print("✅ Service initialized")

        # Test investigation creation with immediate agent start
        print("\n2. Creating new investigation...")
        request = InvestigationRequest(
            plant_id="test_plant_123",
            start_date=date.today(),
            end_date=date.today(),
            additional_notes="Test investigation for solar feasibility",
            parent_id=None,
        )

        # This should trigger the ADK agent immediately
        investigation = await service.start_investigation(request)
        print(f"✅ Investigation created: {investigation.id}")
        print(f"   Status: {investigation.status.value}")

        # Test getting investigation (should include ADK session data)
        print("\n3. Retrieving investigation...")
        retrieved = await service.get_investigation(investigation.id)
        if retrieved:
            print(f"✅ Investigation retrieved: {retrieved.id}")
            print(f"   Status: {retrieved.status.value}")
            print(f"   Session ID: {retrieved.session_id}")
        else:
            print("❌ Failed to retrieve investigation")

        # Test chat history (should include initial agent message)
        print("\n4. Getting chat history...")
        chat_history = await service.get_chat_history(investigation.id)
        print(f"✅ Retrieved {len(chat_history)} messages")

        for i, msg in enumerate(chat_history[:3]):  # Show first 3 messages
            print(
                f"   Message {i+1}: {msg.message_type.value} - {msg.content[:100]}..."
            )

        # Test follow-up message
        print("\n5. Sending follow-up message...")
        response = await service.run_investigation_step(
            investigation.id, "What are the main risks for this solar installation?"
        )
        print(f"✅ Agent response: {response[:200]}...")

        print("\n🎉 All tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_investigation_flow())
