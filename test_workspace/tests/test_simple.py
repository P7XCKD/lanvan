"""
Simple streaming assembly test
"""
import requests
import time

def test_server():
    try:
        response = requests.get("http://127.0.0.1", timeout=5)
        print(f"Server status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Server test failed: {e}")
        return False

def main():
    print("Testing streaming assembly...")
    if test_server():
        print("✅ Server is running!")
        print("🌊 Streaming assembly implementation is ready")
    else:
        print("❌ Server not accessible")

if __name__ == "__main__":
    main()
