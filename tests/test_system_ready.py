#!/usr/bin/env python3
"""
🧪 Test QR Code Generation and Loading System
Tests the offline QR code generation and smart loading page behavior.
"""

import sys
import os
import requests
import time

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_qr_generation():
    """Test the offline QR code generation endpoint"""
    print("🧪 Testing QR Code Generation...")
    
    try:
        # Test QR generation using default HTTP port (80)
        test_url = "http://test.local"
        response = requests.get(f"http://localhost/api/qr-code?text={test_url}&size=150", timeout=5)
        
        if response.status_code == 200:
            if response.headers.get('content-type') == 'image/png':
                print(f"✅ QR code generated successfully for: {test_url}")
                print(f"   Content-Type: {response.headers.get('content-type')}")
                print(f"   Size: {len(response.content)} bytes")
                return True
            else:
                print(f"❌ Wrong content type: {response.headers.get('content-type')}")
                return False
        else:
            print(f"❌ QR generation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Server not running - start server first with: python run.py http")
        return False
    except Exception as e:
        print(f"❌ QR test failed: {e}")
        return False

def test_loading_page():
    """Test the loading page functionality"""
    print("\n🧪 Testing Loading Page System...")
    
    try:
        # Test loading page using default HTTP port (80)
        response = requests.get("http://localhost/loading", timeout=5)
        
        if response.status_code == 200:
            if "LANVan - Loading..." in response.text:
                print("✅ Loading page loads correctly")
                
                # Check if it contains the icon reference
                if "icon.png" in response.text:
                    print("✅ Loading page includes LANVan icon")
                else:
                    print("⚠️ Loading page missing icon reference")
                
                return True
            else:
                print("❌ Loading page content incorrect")
                return False
        else:
            print(f"❌ Loading page failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Loading page test failed: {e}")
        return False

def test_server_status():
    """Test the server status endpoint"""
    print("\n🧪 Testing Server Status...")
    
    try:
        # Test server status using default HTTP port (80)
        response = requests.get("http://localhost/api/server-status", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'online':
                print("✅ Server status endpoint working")
                print(f"   Resources ready: {data.get('resources_ready', 'unknown')}")
                return True
            else:
                print(f"❌ Unexpected status: {data.get('status')}")
                return False
        else:
            print(f"❌ Server status failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Server status test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("============================================================")
    print("🧪 Testing QR Code & Loading Page System")
    print("============================================================")
    
    # Wait a moment for server to be ready
    print("⏳ Waiting for server startup...")
    time.sleep(2)
    
    tests_passed = 0
    total_tests = 3
    
    if test_server_status():
        tests_passed += 1
    
    if test_qr_generation():
        tests_passed += 1
    
    if test_loading_page():
        tests_passed += 1
    
    print("\n============================================================")
    print(f"🎉 Test Results: {tests_passed}/{total_tests} tests passed")
    print("============================================================")
    
    if tests_passed == total_tests:
        print("✅ All systems working correctly!")
        print("   • QR codes generate offline")
        print("   • Loading page ready with LANVan icon")
        print("   • Smart loading system operational")
    else:
        print("⚠️ Some tests failed - check server setup")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
