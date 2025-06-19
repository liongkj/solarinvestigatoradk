#!/usr/bin/env python3
"""
Complete test script for SSE streaming functionality
1. Creates a real investigation
2. Tests the SSE stream
3. Triggers some events to test streaming
"""

import asyncio
import httpx
import json
from datetime import date


async def create_test_investigation():
    """Create a test investigation first"""
    investigation_data = {
        "plant_id": "plant-001",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
        "additional_notes": "SSE streaming test investigation",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/api/investigations/",
                json=investigation_data,
                timeout=10.0,
            )

            if response.status_code == 200:
                investigation = response.json()
                print(f"✅ Investigation response: {investigation}")

                # Try different possible ID fields
                investigation_id = (
                    investigation.get("id")
                    or investigation.get("investigation_id")
                    or investigation.get("investigation", {}).get("id")
                    or investigation.get("data", {}).get("id")
                )

                if investigation_id:
                    print(f"✅ Created test investigation: {investigation_id}")
                    return investigation_id
                else:
                    print(f"❌ No ID found in response: {investigation}")
                    return None
            else:
                print(f"❌ Failed to create investigation: {response.status_code}")
                print(f"   Response: {response.text}")
                return None

    except Exception as e:
        print(f"❌ Error creating investigation: {e}")
        return None


async def test_sse_stream(investigation_id: str):
    """Test the SSE streaming endpoint with proper error handling"""
    url = f"http://localhost:8000/api/investigations/{investigation_id}/stream"

    print(f"\n📡 Testing SSE stream at: {url}")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 200:
                    print("✅ SSE connection established")
                    print("📡 Streaming events:")
                    print("-" * 40)

                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            try:
                                event = json.loads(data)
                                event_count += 1

                                print(
                                    f"🔔 Event #{event_count}: {event.get('type', 'unknown')}"
                                )
                                print(
                                    f"   Investigation: {event.get('investigation_id')}"
                                )

                                if event.get("status"):
                                    print(f"   Status: {event.get('status')}")
                                if event.get("message"):
                                    print(f"   Message: {event.get('message')}")
                                if event.get("ui_summary"):
                                    print(
                                        f"   Summary: {event.get('ui_summary')[:100]}..."
                                    )

                                print(f"   Timestamp: {event.get('timestamp')}")
                                print("-" * 40)

                                # Stop after getting some events or on completion
                                if (
                                    event.get("type") == "completion"
                                    or event_count >= 5
                                ):
                                    if event.get("type") == "completion":
                                        print("✅ Investigation completed")
                                    else:
                                        print(
                                            f"✅ Received {event_count} events successfully"
                                        )
                                    break

                            except json.JSONDecodeError as e:
                                print(f"📄 Raw data (invalid JSON): {data}")
                                print(f"   JSON Error: {e}")

                        elif line.strip():  # Non-empty, non-data line
                            print(f"📄 SSE Line: {line}")

                else:
                    print(f"❌ HTTP {response.status_code}")
                    response_text = await response.aread()
                    print(f"   Response: {response_text.decode()}")

    except httpx.ConnectError:
        print(
            "❌ Connection failed. Make sure FastAPI server is running on localhost:8000"
        )
    except httpx.TimeoutException:
        print("❌ Request timed out")
    except Exception as e:
        print(f"❌ Error: {e}")


async def trigger_test_events(investigation_id: str):
    """Trigger some test events to see in the stream"""
    print(f"\n🎯 Triggering test events for investigation: {investigation_id}")

    try:
        # Wait a bit before triggering events
        await asyncio.sleep(2)

        async with httpx.AsyncClient() as client:
            # Create a test workorder
            workorder_data = {"description": "Test workorder for SSE streaming"}
            response = await client.post(
                f"http://localhost:8000/api/investigations/{investigation_id}/workorders",
                json=workorder_data,
                timeout=10.0,
            )

            if response.status_code == 200:
                print("✅ Test workorder created")
            else:
                print(f"❌ Workorder creation failed: {response.status_code}")

    except Exception as e:
        print(f"❌ Error triggering events: {e}")


async def main():
    """Main test function"""
    print("🚀 SSE Stream Complete Tester")
    print("Make sure your FastAPI server is running first!")
    print()

    # Step 1: Create test investigation
    investigation_id = await create_test_investigation()
    if not investigation_id:
        print("❌ Cannot proceed without a valid investigation")
        return

    # Step 2: Start background task to trigger events
    asyncio.create_task(trigger_test_events(investigation_id))

    # Small delay to let the investigation be created
    await asyncio.sleep(1)

    # Step 3: Test SSE stream
    await test_sse_stream(investigation_id)

    print("\n✅ SSE streaming test completed!")


if __name__ == "__main__":
    asyncio.run(main())
