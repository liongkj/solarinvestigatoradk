"""WebSocket endpoints for real-time investigation updates"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set
import json
import logging
import asyncio

from adk.services.investigation_service import InvestigationService

logger = logging.getLogger(__name__)

# Router for WebSocket endpoints
router = APIRouter(prefix="/ws", tags=["websocket"])


# Connection manager for WebSocket connections
class ConnectionManager:
    def __init__(self):
        # investigation_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, investigation_id: str):
        await websocket.accept()
        if investigation_id not in self.active_connections:
            self.active_connections[investigation_id] = set()
        self.active_connections[investigation_id].add(websocket)
        logger.info(f"WebSocket connected for investigation {investigation_id}")

    def disconnect(self, websocket: WebSocket, investigation_id: str):
        if investigation_id in self.active_connections:
            self.active_connections[investigation_id].discard(websocket)
            if not self.active_connections[investigation_id]:
                del self.active_connections[investigation_id]
        logger.info(f"WebSocket disconnected for investigation {investigation_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_investigation(self, investigation_id: str, message: dict):
        if investigation_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[investigation_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected.add(websocket)

            # Clean up disconnected websockets
            for websocket in disconnected:
                self.active_connections[investigation_id].discard(websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/investigations/{investigation_id}")
async def websocket_investigation_updates(
    websocket: WebSocket,
    investigation_id: str,
    investigation_service: InvestigationService = Depends(InvestigationService),
):
    """
    WebSocket endpoint for real-time investigation updates.

    Clients can connect to receive real-time updates about:
    - Agent responses and UI summaries
    - Investigation status changes
    - New messages in chat history
    """
    await manager.connect(websocket, investigation_id)

    try:
        # Send initial investigation data
        investigation = await investigation_service.get_investigation(investigation_id)
        if investigation:
            await manager.send_personal_message(
                json.dumps(
                    {
                        "type": "investigation_status",
                        "data": {
                            "investigation_id": investigation_id,
                            "status": investigation.status.value,
                            "updated_at": investigation.updated_at.isoformat(),
                        },
                    }
                ),
                websocket,
            )

        # Send latest UI summary if available
        try:
            session_id = investigation_service._get_session_id(investigation_id)
            session = await investigation_service.session_service.get_session(
                app_name=investigation_service.app_name,
                user_id=investigation_service.default_user_id,
                session_id=session_id,
            )

            if session and session.state.get("ui_state"):
                ui_state = session.state["ui_state"]
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "ui_summary_update",
                            "data": {
                                "investigation_id": investigation_id,
                                "ui_summary": ui_state.get("latest_ui_summary"),
                                "last_update": ui_state.get("last_summary_update"),
                            },
                        }
                    ),
                    websocket,
                )
        except Exception as e:
            logger.warning(f"Could not send initial UI summary: {e}")

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types
                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}), websocket
                    )
                elif message.get("type") == "request_status":
                    # Send current investigation status
                    investigation = await investigation_service.get_investigation(
                        investigation_id
                    )
                    if investigation:
                        await manager.send_personal_message(
                            json.dumps(
                                {
                                    "type": "investigation_status",
                                    "data": {
                                        "investigation_id": investigation_id,
                                        "status": investigation.status.value,
                                        "updated_at": investigation.updated_at.isoformat(),
                                    },
                                }
                            ),
                            websocket,
                        )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, investigation_id)


# Helper function to broadcast updates (to be called from service)
async def broadcast_ui_summary_update(
    investigation_id: str, ui_summary: str, full_content: str
):
    """Broadcast UI summary updates to connected clients"""
    await manager.broadcast_to_investigation(
        investigation_id,
        {
            "type": "ui_summary_update",
            "data": {
                "investigation_id": investigation_id,
                "ui_summary": ui_summary,
                "full_content": full_content,
                "timestamp": asyncio.get_event_loop().time(),
            },
        },
    )


async def broadcast_status_update(investigation_id: str, status: str):
    """Broadcast status updates to connected clients"""
    await manager.broadcast_to_investigation(
        investigation_id,
        {
            "type": "investigation_status",
            "data": {
                "investigation_id": investigation_id,
                "status": status,
                "timestamp": asyncio.get_event_loop().time(),
            },
        },
    )


async def broadcast_new_message(investigation_id: str, message: dict):
    """Broadcast new chat messages to connected clients"""
    await manager.broadcast_to_investigation(
        investigation_id,
        {
            "type": "new_message",
            "data": {
                "investigation_id": investigation_id,
                "message": message,
                "timestamp": asyncio.get_event_loop().time(),
            },
        },
    )
