# """Broadcast service for WebSocket communications"""

# import asyncio
# import logging
# from typing import Dict, Set, Any

# logger = logging.getLogger(__name__)


# class BroadcastService:
#     """Service for managing WebSocket broadcasts"""

#     def __init__(self):
#         # This will be set by the websocket controller
#         self._connection_manager = None

#     def set_connection_manager(self, manager):
#         """Set the connection manager (called by websocket controller)"""
#         self._connection_manager = manager
#         logger.info(f"Connection manager set: {manager}")

#     def _ensure_connection_manager(self):
#         """Ensure connection manager is available, lazy load if needed"""
#         if self._connection_manager is None:
#             try:
#                 # Import here to avoid circular imports
#                 from adk.controllers.websocket_controller import manager

#                 self._connection_manager = manager
#                 logger.info("Lazy loaded connection manager from websocket controller")
#             except ImportError as e:
#                 logger.error(f"Failed to lazy load connection manager: {e}")

#         return self._connection_manager is not None

#     async def broadcast_ui_summary_update(
#         self, investigation_id: str, ui_summary: str, full_content: str
#     ):
#         """Broadcast UI summary updates to connected clients"""
#         if not self._ensure_connection_manager():
#             logger.warning(
#                 "Connection manager not available, cannot broadcast UI summary update"
#             )
#             return

#         await self._connection_manager.broadcast_to_investigation(
#             investigation_id,
#             {
#                 "type": "ui_summary_update",
#                 "data": {
#                     "investigation_id": investigation_id,
#                     "ui_summary": ui_summary,
#                     "full_content": full_content,
#                     "timestamp": asyncio.get_event_loop().time(),
#                 },
#             },
#         )

#     async def broadcast_status_update(self, investigation_id: str, status: str):
#         """Broadcast status updates to connected clients"""
#         if not self._ensure_connection_manager():
#             logger.warning(
#                 "Connection manager not available, cannot broadcast status update"
#             )
#             return

#         await self._connection_manager.broadcast_to_investigation(
#             investigation_id,
#             {
#                 "type": "investigation_status",
#                 "data": {
#                     "investigation_id": investigation_id,
#                     "status": status,
#                     "timestamp": asyncio.get_event_loop().time(),
#                 },
#             },
#         )

#     async def broadcast_new_message(self, investigation_id: str, message: dict):
#         """Broadcast new message to connected clients"""
#         if not self._ensure_connection_manager():
#             logger.warning(
#                 "Connection manager not available, cannot broadcast new message"
#             )
#             return

#         await self._connection_manager.broadcast_to_investigation(
#             investigation_id,
#             {
#                 "type": "new_message",
#                 "data": message,
#             },
#         )


# # Singleton instance
# broadcast_service = BroadcastService()
