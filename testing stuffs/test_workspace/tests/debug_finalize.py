"""
Debug test to see what happens during finalization
"""
import requests

def debug_finalize():
    print("🔍 Testing finalization directly...")
    
    finalize_data = {
        'filename': 'stream_test_5mb.txt',
        'total_parts': 20,
        'encrypt': 'false'
    }
    
    response = requests.post("http://127.0.0.1/finalize_upload", data=finalize_data)
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Success!")
        print(f"Streaming assembly: {result.get('streaming_assembly', 'Unknown')}")
        print(f"Assembly method: {result.get('assembly_method', 'Unknown')}")
    else:
        print("❌ Failed!")

if __name__ == "__main__":
    debug_finalize()
