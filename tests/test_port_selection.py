#!/usr/bin/env python3
"""Test the new port selection logic"""

import sys
import os

# Add the current directory to sys.path so we can import from run.py
sys.path.insert(0, os.path.dirname(__file__))

# Import the functions we need to test
import socket
from run import get_safe_port, is_port_available, can_bind_privileged_port, find_available_port

def test_port_selection():
    print("🔍 Testing new port selection logic...")
    
    print("\n📝 Testing HTTP port priority:")
    http_port = get_safe_port(protocol="http")
    print(f"   Selected HTTP port: {http_port}")
    
    print("\n📝 Testing HTTPS port priority:")
    https_port = get_safe_port(protocol="https")  
    print(f"   Selected HTTPS port: {https_port}")
    
    print("\n📝 Testing with specific preferred port:")
    custom_port = get_safe_port(preferred_port=3000, protocol="http")
    print(f"   Selected custom port: {custom_port}")
    
    print("\n✅ Port selection tests completed!")

if __name__ == "__main__":
    test_port_selection()
