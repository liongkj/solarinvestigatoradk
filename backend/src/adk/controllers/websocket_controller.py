# """WebSocket endpoints for real-time investigation updates"""

# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
# from typing import Dict, Set, TYPE_CHECKING
# import json
# import logging
# import asyncio

# from adk.services.broadcast_service import broadcast_service

# if TYPE_CHECKING:
#     from adk.services.investigation_service import InvestigationService

# logger = logging.getLogger(__name__)

# # Router for WebSocket endpoints
# router = APIRouter(prefix="/ws", tags=["websocket"])


# # Connection manager for WebSocket connections
# class ConnectionManager:
#     def __init__(self):
#         # investigation_id -> set of websockets
#         self.active_connections: Dict[str, Set[WebSocket]] = {}

#     async def connect(self, websocket: WebSocket, investigation_id: str):
#         await websocket.accept()
#         if investigation_id not in self.active_connections:
#             self.active_connections[investigation_id] = set()
#         self.active_connections[investigation_id].add(websocket)
#         logger.info(f"WebSocket connected for investigation {investigation_id}")

#     def disconnect(self, websocket: WebSocket, investigation_id: str):
#         if investigation_id in self.active_connections:
#             self.active_connections[investigation_id].discard(websocket)
#             if not self.active_connections[investigation_id]:
#                 del self.active_connections[investigation_id]
#         logger.info(f"WebSocket disconnected for investigation {investigation_id}")

#     async def send_personal_message(self, message: str, websocket: WebSocket):
#         try:
#             await websocket.send_text(message)
#         except Exception as e:
#             logger.error(f"Error sending personal message: {e}")

#     async def broadcast_to_investigation(self, investigation_id: str, message: dict):
#         if investigation_id in self.active_connections:
#             disconnected = set()
#             for websocket in self.active_connections[investigation_id]:
#                 try:
#                     await websocket.send_text(json.dumps(message))
#                 except:
#                     disconnected.add(websocket)

#             # Clean up disconnected websockets
#             for websocket in disconnected:
#                 self.active_connections[investigation_id].discard(websocket)


# # Global connection manager
# manager = ConnectionManager()


# # Initialize the broadcast service with the connection manager when module loads
# def init_broadcast_service():
#     """Initialize the broadcast service with the connection manager"""
#     try:
#         broadcast_service.set_connection_manager(manager)
#         logger.info("Broadcast service initialized with connection manager")
#     except Exception as e:
#         logger.error(f"Failed to initialize broadcast service: {e}")


# # Call initialization immediately
# init_broadcast_service()


# @router.websocket("/investigations/{investigation_id}")
# async def websocket_investigation_updates(
#     websocket: WebSocket,
#     investigation_id: str,
# ):
#     """
#     WebSocket endpoint for real-time investigation updates.

#     Clients can connect to receive real-time updates about:
#     - Agent responses and UI summaries
#     - Investigation status changes
#     - New messages in chat history
#     """
#     await manager.connect(websocket, investigation_id)

#     try:
#         # Send initial connection confirmation
#         await websocket.send_json(
#             {
#                 "type": "connection_established",
#                 "data": {
#                     "investigation_id": investigation_id,
#                     "message": "Connected to investigation updates",
#                 },
#             }
#         )

#         # Keep connection alive and handle incoming messages
#         while True:
#             try:
#                 # Wait for client messages (ping/pong, etc.)
#                 data = await websocket.receive_text()
#                 message = json.loads(data)

#                 # Handle different message types
#                 if message.get("type") == "ping":
#                     await manager.send_personal_message(
#                         json.dumps({"type": "pong"}), websocket
#                     )

#             except WebSocketDisconnect:
#                 break
#             except Exception as e:
#                 logger.error(f"Error in WebSocket loop: {e}")
#                 break

#     except WebSocketDisconnect:
#         pass
#     finally:
#         manager.disconnect(websocket, investigation_id)


# # Ensure broadcast service is initialized
# init_broadcast_service()
