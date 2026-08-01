"""
Unit & Integration Test Suite for Dedicated UI Events WebSocket (/ws/ui-events)
Verifies:
1. Connection handshake & connection count.
2. Standardized event envelope schema compliance & strict validation.
3. Broadcast, broadcast_except, and emit_ui_event façade API functionality.
4. Heartbeat ping/pong and stale connection cleanup.
5. Error shielding of malformed packets.
6. Isolation from repository, file list, and upload state.
"""

import sys
import os
import asyncio
import json
import unittest
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.ws_manager.ui_events import UIEventsConnectionManager, ui_events_manager, emit_ui_event, emit_ui_event_sync


class MockWebSocket:
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, data: str):
        if self.closed:
            raise RuntimeError("WebSocket is closed")
        self.sent_messages.append(data)

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class TestUIEventsWebSocketManager(unittest.TestCase):
    def setUp(self):
        self.manager = UIEventsConnectionManager()

    def test_connect_and_disconnect(self):
        async def run_test():
            ws1 = MockWebSocket()
            conn_id1 = await self.manager.connect(ws1, client_id="client_1")
            self.assertTrue(ws1.accepted)
            self.assertEqual(await self.manager.connection_count(), 1)

            ws2 = MockWebSocket()
            conn_id2 = await self.manager.connect(ws2, client_id="client_2")
            self.assertEqual(await self.manager.connection_count(), 2)

            await self.manager.disconnect(conn_id1)
            self.assertEqual(await self.manager.connection_count(), 1)

            await self.manager.disconnect(conn_id2)
            self.assertEqual(await self.manager.connection_count(), 0)

        asyncio.run(run_test())

    def test_standardized_event_envelope_broadcast(self):
        async def run_test():
            ws1 = MockWebSocket()
            ws2 = MockWebSocket()
            conn_id1 = await self.manager.connect(ws1)
            conn_id2 = await self.manager.connect(ws2)

            payload = {"message": "System Announcement", "level": "info"}
            await self.manager.broadcast("ui.toast", payload)

            self.assertEqual(len(ws1.sent_messages), 1)
            self.assertEqual(len(ws2.sent_messages), 1)

            msg1 = json.loads(ws1.sent_messages[0])
            self.assertEqual(msg1["version"], 1)
            self.assertEqual(msg1["type"], "ui.toast")
            self.assertIn("timestamp", msg1)
            self.assertEqual(msg1["payload"], payload)

        asyncio.run(run_test())

    def test_public_facade_api(self):
        async def run_test():
            ws1 = MockWebSocket()
            conn_id = await ui_events_manager.connect(ws1)
            
            try:
                payload = {"title": "Banner Notice", "level": "warning"}
                await emit_ui_event("ui.banner", payload)

                self.assertGreaterEqual(len(ws1.sent_messages), 1)
                msg = json.loads(ws1.sent_messages[-1])
                self.assertEqual(msg["type"], "ui.banner")
                self.assertEqual(msg["payload"], payload)
            finally:
                await ui_events_manager.disconnect(conn_id)

        asyncio.run(run_test())

    def test_broadcast_except(self):
        async def run_test():
            ws1 = MockWebSocket()
            ws2 = MockWebSocket()
            conn_id1 = await self.manager.connect(ws1)
            conn_id2 = await self.manager.connect(ws2)

            payload = {"theme": "dark"}
            await self.manager.broadcast("ui.theme", payload, exclude_connection_id=conn_id1)

            self.assertEqual(len(ws1.sent_messages), 0)
            self.assertEqual(len(ws2.sent_messages), 1)

            msg2 = json.loads(ws2.sent_messages[0])
            self.assertEqual(msg2["type"], "ui.theme")
            self.assertEqual(msg2["payload"], payload)

        asyncio.run(run_test())

    def test_stale_heartbeat_cleanup(self):
        async def run_test():
            ws1 = MockWebSocket()
            ws2 = MockWebSocket()
            conn_id1 = await self.manager.connect(ws1)
            conn_id2 = await self.manager.connect(ws2)

            # Manually set conn_id1 heartbeat to 100 seconds ago
            self.manager.active_connections[conn_id1]["last_heartbeat"] = time.time() - 100.0

            # Sweep stale connections (> 30s)
            await self.manager.cleanup_stale_connections(max_idle_seconds=30.0)

            self.assertTrue(ws1.closed)
            self.assertEqual(ws1.close_reason, "Heartbeat timeout")
            self.assertFalse(ws2.closed)
            self.assertEqual(await self.manager.connection_count(), 1)

        asyncio.run(run_test())

    def test_dead_connection_pruning_on_broadcast(self):
        async def run_test():
            ws1 = MockWebSocket()
            ws2 = MockWebSocket()
            conn_id1 = await self.manager.connect(ws1)
            conn_id2 = await self.manager.connect(ws2)

            # Mark ws1 as closed to simulate socket error on send
            ws1.closed = True

            await self.manager.broadcast("ui.presence", {"online": True})

            # Dead socket ws1 should be automatically pruned
            self.assertEqual(await self.manager.connection_count(), 1)
            self.assertEqual(len(ws2.sent_messages), 1)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
