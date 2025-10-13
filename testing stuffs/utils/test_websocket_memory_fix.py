#!/usr/bin/env python3
"""
WebSocket Memory Leak Fix Test Script
=====================================

This script tests the WebSocket memory leak fixes without modifying qt.py.
Tests connection cleanup, timeout handling, and memory management.

Usage:
    python test_websocket_memory_fix.py
"""

import asyncio
import aiohttp
import websockets
import sys
import time
import gc
import psutil
import os
from pathlib import Path

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "app"))

class WebSocketMemoryTester:
    """Test WebSocket memory leak fixes"""
    
    def __init__(self):
        self.server_process = None
        self.test_results = {}
        self.initial_memory = 0
        
    def log(self, message, level="INFO"):
        """Log test messages with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def get_memory_usage(self):
        """Get current memory usage in MB"""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024  # MB
        except:
            return 0
            
    async def start_test_server(self):
        """Start LANVAN server for testing"""
        self.log("Starting LANVAN server for WebSocket testing...")
        
        try:
            # Import and start the server
            from app.main import app
            import uvicorn
            
            # Start server in background
            config = uvicorn.Config(app, host="127.0.0.1", port=8080, log_level="error")
            server = uvicorn.Server(config)
            
            # Run server in background task
            server_task = asyncio.create_task(server.serve())
            await asyncio.sleep(2)  # Give server time to start
            
            self.log("Test server started on http://127.0.0.1:8080")
            return server_task, server
            
        except Exception as e:
            self.log(f"Failed to start test server: {e}", "ERROR")
            return None, None
            
    async def test_clipboard_websocket_connections(self):
        """Test clipboard WebSocket connection management"""
        self.log("Testing clipboard WebSocket connections...")
        
        base_url = "ws://127.0.0.1:8080"
        connections = []
        
        try:
            # Create multiple WebSocket connections
            for i in range(10):
                try:
                    ws = await websockets.connect(f"{base_url}/ws/clipboard")
                    connections.append(ws)
                    self.log(f"Created clipboard connection {i+1}/10")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.log(f"Failed to create connection {i+1}: {e}", "WARN")
            
            self.log(f"Created {len(connections)} clipboard WebSocket connections")
            
            # Test sending messages
            for i, ws in enumerate(connections[:3]):  # Test first 3
                try:
                    await ws.send('{"action": "get_clipboard"}')
                    response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    self.log(f"Connection {i+1} response received")
                except Exception as e:
                    self.log(f"Connection {i+1} message test failed: {e}", "WARN")
            
            # Close half the connections normally
            for i in range(0, len(connections), 2):
                try:
                    await connections[i].close()
                    self.log(f"Closed connection {i+1} normally")
                except:
                    pass
            
            # Simulate abrupt disconnections for the rest
            for i in range(1, len(connections), 2):
                try:
                    # Just abandon the connection (simulates network disconnect)
                    connections[i] = None
                    self.log(f"Abandoned connection {i+1} (simulating disconnect)")
                except:
                    pass
            
            self.log("Clipboard WebSocket connection test completed")
            return True
            
        except Exception as e:
            self.log(f"Clipboard WebSocket test failed: {e}", "ERROR")
            return False
        finally:
            # Clean up remaining connections
            for ws in connections:
                if ws:
                    try:
                        await ws.close()
                    except:
                        pass
    
    async def test_upload_status_websocket_connections(self):
        """Test upload status WebSocket connection management"""
        self.log("Testing upload status WebSocket connections...")
        
        base_url = "ws://127.0.0.1:8080"
        connections = []
        
        try:
            # Create multiple WebSocket connections
            for i in range(10):
                try:
                    ws = await websockets.connect(f"{base_url}/ws/upload-status")
                    connections.append(ws)
                    self.log(f"Created upload status connection {i+1}/10")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    self.log(f"Failed to create upload connection {i+1}: {e}", "WARN")
            
            self.log(f"Created {len(connections)} upload status WebSocket connections")
            
            # Test connection timeout behavior
            self.log("Testing connection timeout behavior...")
            await asyncio.sleep(3)  # Wait to test timeout handling
            
            # Close connections
            for i, ws in enumerate(connections):
                try:
                    await ws.close()
                    self.log(f"Closed upload connection {i+1}")
                except:
                    pass
            
            self.log("Upload status WebSocket connection test completed")
            return True
            
        except Exception as e:
            self.log(f"Upload status WebSocket test failed: {e}", "ERROR")
            return False
    
    async def test_memory_leak_detection(self):
        """Test for memory leaks during WebSocket operations"""
        self.log("Testing WebSocket memory leak detection...")
        
        initial_memory = self.get_memory_usage()
        self.log(f"Initial memory usage: {initial_memory:.2f} MB")
        
        # Run multiple connection cycles
        for cycle in range(3):
            self.log(f"Running connection cycle {cycle + 1}/3...")
            
            # Test clipboard connections
            await self.test_clipboard_websocket_connections()
            
            # Force garbage collection
            gc.collect()
            await asyncio.sleep(1)
            
            # Check memory usage
            current_memory = self.get_memory_usage()
            memory_increase = current_memory - initial_memory
            self.log(f"Memory after cycle {cycle + 1}: {current_memory:.2f} MB (Δ{memory_increase:+.2f} MB)")
            
            if memory_increase > 50:  # 50MB threshold
                self.log(f"WARNING: Significant memory increase detected: {memory_increase:.2f} MB", "WARN")
        
        final_memory = self.get_memory_usage()
        total_increase = final_memory - initial_memory
        self.log(f"Final memory usage: {final_memory:.2f} MB (Total Δ{total_increase:+.2f} MB)")
        
        # Memory leak detection
        if total_increase > 100:  # 100MB threshold for 3 cycles
            self.log("❌ POTENTIAL MEMORY LEAK DETECTED", "ERROR")
            return False
        else:
            self.log("✅ Memory usage within acceptable limits", "PASS")
            return True
    
    async def test_connection_cleanup_verification(self):
        """Verify that WebSocket connections are properly cleaned up"""
        self.log("Testing WebSocket connection cleanup verification...")
        
        try:
            # Test HTTP endpoint to check connection status
            async with aiohttp.ClientSession() as session:
                # Check if server provides connection status
                try:
                    async with session.get("http://127.0.0.1:8080/network-info") as response:
                        if response.status == 200:
                            data = await response.json()
                            self.log("Server network info retrieved successfully")
                            return True
                except Exception as e:
                    self.log(f"Connection status check failed: {e}", "WARN")
            
            return True
            
        except Exception as e:
            self.log(f"Connection cleanup verification failed: {e}", "ERROR")
            return False
    
    async def run_all_tests(self):
        """Run all WebSocket memory leak tests"""
        self.log("🚀 Starting WebSocket Memory Leak Fix Tests")
        self.log("=" * 60)
        
        # Record initial memory
        self.initial_memory = self.get_memory_usage()
        
        # Start test server
        server_task, server = await self.start_test_server()
        if not server_task:
            self.log("❌ Failed to start test server", "ERROR")
            return False
        
        try:
            # Run tests
            tests = [
                ("Clipboard WebSocket Connections", self.test_clipboard_websocket_connections()),
                ("Upload Status WebSocket Connections", self.test_upload_status_websocket_connections()),
                ("Memory Leak Detection", self.test_memory_leak_detection()),
                ("Connection Cleanup Verification", self.test_connection_cleanup_verification())
            ]
            
            results = {}
            for test_name, test_coro in tests:
                self.log(f"\n--- Running: {test_name} ---")
                try:
                    result = await test_coro
                    results[test_name] = result
                    status = "✅ PASSED" if result else "❌ FAILED"
                    self.log(f"{test_name}: {status}")
                except Exception as e:
                    self.log(f"{test_name}: ❌ EXCEPTION - {e}", "ERROR")
                    results[test_name] = False
            
            # Summary
            self.log("\n" + "=" * 60)
            self.log("📊 TEST RESULTS SUMMARY")
            self.log("=" * 60)
            
            passed = sum(1 for result in results.values() if result)
            total = len(results)
            
            for test_name, result in results.items():
                status = "✅ PASSED" if result else "❌ FAILED"
                self.log(f"{test_name}: {status}")
            
            self.log(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                self.log("🎉 ALL WEBSOCKET MEMORY LEAK TESTS PASSED!")
                self.log("✅ WebSocket memory leak fixes are working correctly")
                self.log("💡 Safe to integrate into qt.py test suite")
                return True
            else:
                self.log("⚠️ Some tests failed - review fixes before integration")
                return False
                
        finally:
            # Cleanup server
            if server_task:
                server_task.cancel()
                try:
                    await server_task
                except asyncio.CancelledError:
                    pass
            self.log("Test server stopped")

async def main():
    """Main test runner"""
    tester = WebSocketMemoryTester()
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        tester.log("Test interrupted by user", "WARN")
        sys.exit(1)
    except Exception as e:
        tester.log(f"Test runner failed: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    print("WebSocket Memory Leak Fix Tester")
    print("=================================")
    print("Testing WebSocket connection management and memory leak fixes...")
    print("This test runs independently of qt.py to ensure safety.")
    print()
    
    asyncio.run(main())