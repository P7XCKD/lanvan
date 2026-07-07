#!/usr/bin/env python3
"""
iOS Compatibility Test Script
Tests the iOS-specific features and endpoints
"""

import requests
import json

def test_ios_endpoints():
    base_url = "http://localhost:5000"
    
    # iOS Safari User Agent
    ios_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
    }
    
    print(" Testing iOS compatibility features...\n")
    
    # Test 1: Server Status
    try:
        response = requests.get(f"{base_url}/api/server-status", headers=ios_headers)
        if response.status_code == 200:
            data = response.json()
            print("[OK] Server Status Test:")
            print(f"   Status: {data['status']}")
            print(f"   iOS Detected: {data['ios_optimizations']['detected']}")
            print(f"   Safari Detected: {data['ios_optimizations']['safari']}")
            print(f"   Device Type: {data['ios_optimizations']['device_type']}")
        else:
            print(f"[ERR] Server Status Test Failed: {response.status_code}")
    except Exception as e:
        print(f"[ERR] Server Status Test Error: {e}")
    
    print()
    
    # Test 2: iOS Compatibility Check
    try:
        response = requests.get(f"{base_url}/ios-check", headers=ios_headers)
        if response.status_code == 200:
            data = response.json()
            print("[OK] iOS Compatibility Check:")
            print(f"   iOS Detected: {data['is_ios']}")
            print(f"   Device Type: {data['device_type']}")
            print(f"   Protocol: {data['current_protocol']}")
            print(f"   Suggestions: {len(data.get('suggestions', []))}")
            for suggestion in data.get('suggestions', []):
                print(f"      - {suggestion['message']} ({suggestion['priority']})")
        else:
            print(f"[ERR] iOS Compatibility Check Failed: {response.status_code}")
    except Exception as e:
        print(f"[ERR] iOS Compatibility Check Error: {e}")
    
    print()
    
    # Test 3: Main Page with iOS headers
    try:
        response = requests.get(f"{base_url}/", headers=ios_headers)
        if response.status_code == 200:
            print("[OK] Main Page Access Test:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Content Length: {len(response.text)} bytes")
            
            # Check for iOS-specific headers in response
            ios_headers_in_response = {}
            for header, value in response.headers.items():
                if any(ios_keyword in header.lower() for ios_keyword in ['cache', 'connection', 'content-type']):
                    ios_headers_in_response[header] = value
            
            if ios_headers_in_response:
                print("   iOS-Specific Response Headers:")
                for header, value in ios_headers_in_response.items():
                    print(f"      {header}: {value}")
        else:
            print(f"[ERR] Main Page Access Failed: {response.status_code}")
    except Exception as e:
        print(f"[ERR] Main Page Access Error: {e}")
    
    print()
    
    # Test 4: iOS Help Page
    try:
        response = requests.get(f"{base_url}/ios-help")
        if response.status_code == 200:
            print("[OK] iOS Help Page Test:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Content Length: {len(response.text)} bytes")
            
            # Check if it contains iOS-specific content
            if "iOS Safari" in response.text:
                print("   [OK] Contains iOS Safari help content")
            if "QR Code" in response.text:
                print("   [OK] Contains QR code generation")
        else:
            print(f"[ERR] iOS Help Page Failed: {response.status_code}")
    except Exception as e:
        print(f"[ERR] iOS Help Page Error: {e}")
    
    print("\n iOS compatibility test completed!")

if __name__ == "__main__":
    test_ios_endpoints()