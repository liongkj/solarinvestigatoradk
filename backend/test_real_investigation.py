#!/usr/bin/env python3
"""
Test script to trigger a real investigation and monitor for callback errors
"""

import asyncio
import httpx
import json
from datetime import date


async def create_and_start_investigation():
    """Create and start a real investigation"""
    investigation_data = {
        "plant_id": "plant-001",
        "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(),
        "additional_notes": "Real investigation test - checking callback fixes",
    }

    try:
        async with httpx.AsyncClient() as client:
            # Create investigation
            response = await client.post(
                "http://localhost:8000/api/investigations/",
                json=investigation_data,
                timeout=10.0,
            )

            if response.status_code == 200:
                investigation = response.json()
                investigation_id = investigation.get("investigation", {}).get("id")

                if investigation_id:
                    print(f"✅ Created investigation: {investigation_id}")

                    # Start the investigation
                    start_response = await client.post(
                        f"http://localhost:8000/api/investigations/{investigation_id}/start",
                        timeout=10.0,
                    )

                    if start_response.status_code == 200:
                        print(f"✅ Started investigation: {investigation_id}")
                        return investigation_id
                    else:
                        print(
                            f"❌ Failed to start investigation: {start_response.status_code}"
                        )
                        print(f"   Response: {start_response.text}")
                        return investigation_id  # Return anyway for testing
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


async def monitor_investigation_stream(investigation_id: str, duration: int = 30):
    """Monitor the SSE stream for a specific duration"""
    url = f"http://localhost:8000/api/investigations/{investigation_id}/stream"

    print(f"\n📡 Monitoring SSE stream for {duration} seconds...")
    print(f"   URL: {url}")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url) as response:
                if response.status_code == 200:
                    print("✅ SSE connection established")
                    print("📡 Streaming events:")
                    print("-" * 40)

                    start_time = asyncio.get_event_loop().time()
                    event_count = 0

                    async for line in response.aiter_lines():
                        # Check timeout
                        if asyncio.get_event_loop().time() - start_time > duration:
                            print(f"\n⏰ Monitoring timeout reached ({duration}s)")
                            break

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
                                    msg = event.get("message")
                                    if len(msg) > 100:
                                        msg = msg[:100] + "..."
                                    print(f"   Message: {msg}")
                                if event.get("ui_summary"):
                                    summary = event.get("ui_summary")
                                    if len(summary) > 100:
                                        summary = summary[:100] + "..."
                                    print(f"   Summary: {summary}")

                                print(f"   Timestamp: {event.get('timestamp')}")
                                print("-" * 40)

                                # Stop on completion
                                if event.get("type") == "completion":
                                    print("✅ Investigation completed")
                                    break

                            except json.JSONDecodeError as e:
                                print(f"📄 Raw data (invalid JSON): {data}")

                        elif line.strip():  # Non-empty, non-data line
                            print(f"📄 SSE Line: {line}")

                    print(f"\n✅ Received {event_count} events in {duration}s")

                else:
                    print(f"❌ HTTP {response.status_code}")
                    response_text = await response.aread()
                    print(f"   Response: {response_text.decode()}")

    except Exception as e:
        print(f"❌ Error monitoring stream: {e}")


async def main():
    """Main test function"""
    print("🚀 Real Investigation Test with Callback Fix")
    print("This will create and start a real investigation to test callback fixes")
    print()

    # Step 1: Create and start investigation
    investigation_id = await create_and_start_investigation()
    if not investigation_id:
        print("❌ Cannot proceed without a valid investigation")
        return

    # Step 2: Monitor for 30 seconds
    await monitor_investigation_stream(investigation_id, duration=30)

    print("\n✅ Investigation test completed!")
    print("Check the server logs for any callback errors.")


if __name__ == "__main__":
    asyncio.run(main())
