"""
Test script to demonstrate ADK streaming functionality
"""

import asyncio
import json
from datetime import datetime, date
from adk.services.investigation_service_simplified import (
    get_simplified_investigation_service,
)
from adk.models.investigation import InvestigationRequest


async def test_streaming_investigation():
    """Test the streaming investigation functionality"""
    print("🚀 Starting ADK Streaming Test...")

    service = get_simplified_investigation_service()

    # Create a test investigation request
    request = InvestigationRequest(
        plant_id="test_plant_001",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        additional_notes="Testing streaming functionality with simple solar analysis request",
        parent_id=None,
    )

    try:
        # Start investigation
        print("📝 Creating investigation...")
        investigation = await service.start_investigation(request)
        print(f"✅ Investigation created: {investigation.id}")

        # Get event stream
        print("🌊 Starting event stream...")
        event_count = 0
        streaming_chunks = []

        async for event in service.get_event_stream(investigation.id):
            event_count += 1
            print(f"\n📡 Event #{event_count}:")
            print(f"   Type: {event.get('type', 'unknown')}")
            print(f"   Time: {event.get('timestamp', 'unknown')}")

            if event.get("type") == "streaming_text_chunk":
                chunk = event.get("content", "")
                streaming_chunks.append(chunk)
                print(f"   📝 Streaming chunk: '{chunk}'")
                print(f"   🔄 Partial: {event.get('partial', False)}")
            elif event.get("type") == "complete_text_message":
                print(f"   ✅ Complete message: {event.get('content', '')[:100]}...")
            elif event.get("type") == "tool_call_request":
                print(f"   🔧 Tool calls: {event.get('tool_calls', [])}")
            elif event.get("type") == "completion":
                print("   🏁 Investigation completed!")
                break
            elif event.get("type") == "connected":
                print("   🔗 Stream connected")
            elif event.get("type") == "heartbeat":
                print("   💓 Heartbeat")
            else:
                print(f"   ℹ️  Other event: {json.dumps(event, indent=2)[:200]}...")

        print(f"\n📊 Stream Summary:")
        print(f"   Total events: {event_count}")
        print(f"   Streaming chunks: {len(streaming_chunks)}")
        if streaming_chunks:
            print(f"   Full streamed text: '{' '.join(streaming_chunks)}'")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_streaming_investigation())
