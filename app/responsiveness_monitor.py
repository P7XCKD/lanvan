#!/usr/bin/env python3
"""
🚀 LANVan Responsiveness Monitor
Ensures the server remains ultra-responsive even during heavy file processing
"""

import asyncio
import time
import threading
from typing import Dict, Any, Optional
import gc

# Import Termux compatibility layer
from .termux_compat import (
    is_termux_environment, 
    should_use_lightweight_mode,
    get_safe_cpu_usage,
    get_safe_memory_info,
    safe_psutil_call
)


class ResponsivenessMonitor:
    """
    🎯 Monitors server responsiveness and automatically adjusts processing to prevent blocking
    """
    
    def __init__(self):
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.responsiveness_metrics = {
            'last_heartbeat': time.time(),
            'response_times': [],
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'active_uploads': 0,
            'processing_files': 0,
            'lag_detected': False
        }
        self.performance_caps = {
            'max_concurrent_uploads': 3,
            'max_chunk_size': 32 * 1024 * 1024,  # 32MB
            'yield_frequency': 0.1,  # 100ms default
            'emergency_yield_frequency': 0.02,  # 20ms emergency
        }
        self.lock = threading.Lock()
    
    async def start_monitoring(self):
        """Start the responsiveness monitoring task"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            print("🚀 Responsiveness monitor started")
    
    async def stop_monitoring(self):
        """Stop the responsiveness monitoring task"""
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        print("⏸️ Responsiveness monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop that runs continuously"""
        while self.monitoring:
            try:
                start_time = time.time()
                
                # Update system metrics
                await self._update_system_metrics()
                
                # Check responsiveness
                await self._check_responsiveness()
                
                # Adjust performance caps if needed
                await self._adjust_performance_caps()
                
                # Calculate response time for this monitoring cycle
                response_time = time.time() - start_time
                
                with self.lock:
                    self.responsiveness_metrics['response_times'].append(response_time)
                    # Keep only last 20 measurements
                    if len(self.responsiveness_metrics['response_times']) > 20:
                        self.responsiveness_metrics['response_times'].pop(0)
                
                # Sleep based on current load
                sleep_time = 0.5 if self.responsiveness_metrics['lag_detected'] else 2.0
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ Responsiveness monitor error: {e}")
                await asyncio.sleep(1.0)
    
    async def _update_system_metrics(self):
        """Update system performance metrics with Termux-safe methods"""
        try:
            # Use Termux-safe system metric collection
            if should_use_lightweight_mode():
                # Lightweight mode for Termux/Android
                cpu_percent = get_safe_cpu_usage()
                memory_info = get_safe_memory_info()
                
                with self.lock:
                    self.responsiveness_metrics.update({
                        'cpu_usage': cpu_percent,
                        'memory_usage': memory_info['percent'],
                        'last_heartbeat': time.time()
                    })
                
                # Only log occasionally to reduce noise
                if not hasattr(self, 'log_counter'):
                    self.log_counter = 0
                self.log_counter += 1
                
                if self.log_counter % 20 == 0:  # Every 20th update
                    print(f"📊 System: CPU {cpu_percent:.1f}%, Memory {memory_info['percent']:.1f}%")
            else:
                # Full monitoring for desktop/server environments
                cpu_percent = get_safe_cpu_usage()
                memory_info = get_safe_memory_info()
                
                with self.lock:
                    self.responsiveness_metrics.update({
                        'cpu_usage': cpu_percent,
                        'memory_usage': memory_info['percent'],
                        'last_heartbeat': time.time()
                    })
                
        except Exception as e:
            print(f"⚠️ Failed to update system metrics: {e}")
            # Set safe fallback values
            with self.lock:
                self.responsiveness_metrics.update({
                    'cpu_usage': 50.0,  # Neutral fallback
                    'memory_usage': 60.0,  # Conservative fallback
                    'last_heartbeat': time.time()
                })
    
    async def _check_responsiveness(self):
        """Check if the server is becoming unresponsive"""
        with self.lock:
            avg_response_time = sum(self.responsiveness_metrics['response_times']) / max(1, len(self.responsiveness_metrics['response_times']))
            cpu_usage = self.responsiveness_metrics['cpu_usage']
            memory_usage = self.responsiveness_metrics['memory_usage']
            
            # Detect lag conditions
            lag_detected = (
                avg_response_time > 0.1 or  # Average response time > 100ms
                cpu_usage > 85 or           # CPU usage > 85%
                memory_usage > 90           # Memory usage > 90%
            )
            
            # Update lag status
            if lag_detected != self.responsiveness_metrics['lag_detected']:
                self.responsiveness_metrics['lag_detected'] = lag_detected
                
                if lag_detected:
                    print("🚨 Server lag detected - activating emergency responsiveness mode")
                else:
                    print("✅ Server responsiveness restored - returning to normal mode")
    
    async def _adjust_performance_caps(self):
        """Automatically adjust performance caps based on system load"""
        with self.lock:
            if self.responsiveness_metrics['lag_detected']:
                # Emergency mode - prioritize responsiveness
                self.performance_caps.update({
                    'max_concurrent_uploads': 2,
                    'max_chunk_size': 8 * 1024 * 1024,  # 8MB
                    'yield_frequency': 0.02,  # 20ms - very frequent
                })
            else:
                # Normal mode - balanced performance
                self.performance_caps.update({
                    'max_concurrent_uploads': 3,
                    'max_chunk_size': 32 * 1024 * 1024,  # 32MB
                    'yield_frequency': 0.1,  # 100ms - normal
                })
    
    def get_recommended_settings(self) -> Dict[str, Any]:
        """Get current recommended performance settings"""
        with self.lock:
            return {
                'max_concurrent_uploads': self.performance_caps['max_concurrent_uploads'],
                'max_chunk_size': self.performance_caps['max_chunk_size'],
                'yield_frequency': self.performance_caps['yield_frequency'],
                'emergency_mode': self.responsiveness_metrics['lag_detected'],
                'cpu_usage': self.responsiveness_metrics['cpu_usage'],
                'memory_usage': self.responsiveness_metrics['memory_usage'],
            }
    
    def update_upload_status(self, active_uploads: int, processing_files: int):
        """Update upload and processing status"""
        with self.lock:
            self.responsiveness_metrics.update({
                'active_uploads': active_uploads,
                'processing_files': processing_files
            })
    
    async def emergency_yield(self):
        """Emergency yield for when responsiveness is critical"""
        if self.responsiveness_metrics['lag_detected']:
            await asyncio.sleep(0.01)  # 10ms emergency yield
        else:
            await asyncio.sleep(0.002)  # 2ms normal yield


# Global responsiveness monitor instance
responsiveness_monitor = ResponsivenessMonitor()


async def ensure_responsiveness():
    """
    🎯 Ensure server responsiveness - call this frequently during heavy operations
    """
    await responsiveness_monitor.emergency_yield()


def get_adaptive_settings() -> Dict[str, Any]:
    """
    📊 Get current adaptive performance settings
    """
    return responsiveness_monitor.get_recommended_settings()
