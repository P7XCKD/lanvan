"""
Test script for large PDF chunked upload and /finalize_upload endpoint.
"""
import os
import sys
import tempfile
import urllib.request
import urllib.parse
import json

BASE_URL = "http://localhost:80"

def test_chunked_pdf_upload():
    print("[START] Testing chunked PDF upload and finalization...")
    filename = "test_large_doc.pdf"
    
    # Create a 5MB PDF-signature dummy file
    pdf_header = b"%PDF-1.5\n% \xe2\xe3\xcf\xd3\n"
    pdf_body = b"0" * (5 * 1024 * 1024 - 100)
    pdf_trailer = b"\nstartxref\n12345\n%%EOF\n"
    content = pdf_header + pdf_body + pdf_trailer
    
    total_size = len(content)
    chunk_size = 1 * 1024 * 1024
    total_parts = (total_size + chunk_size - 1) // chunk_size
    
    print(f"[INFO] Uploading {total_size} bytes ({total_parts} parts)...")
    
    for i in range(1, total_parts + 1):
        chunk_data = content[(i - 1) * chunk_size : i * chunk_size]
        
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = []
        body.append(f"--{boundary}".encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="chunk"; filename="{filename}"'.encode('utf-8'))
        body.append(b'Content-Type: application/pdf')
        body.append(b'')
        body.append(chunk_data)
        
        fields = {
            "part_number": str(i),
            "total_parts": str(total_parts),
            "filename": filename,
            "total_size": str(total_size)
        }
        
        for k, v in fields.items():
            body.append(f"--{boundary}".encode('utf-8'))
            body.append(f'Content-Disposition: form-data; name="{k}"'.encode('utf-8'))
            body.append(b'')
            body.append(v.encode('utf-8'))
            
        body.append(f"--{boundary}--".encode('utf-8'))
        body.append(b'')
        
        req_body = b"\r\n".join(body)
        
        req = urllib.request.Request(
            f"{BASE_URL}/upload_chunk",
            data=req_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"  [Part {i}/{total_parts}] Response: {data.get('status')}")

    # Now call /finalize_upload
    print("[INFO] Calling /finalize_upload...")
    finalize_fields = {
        "filename": filename,
        "total_parts": str(total_parts),
        "total_size": str(total_size)
    }
    
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = []
    for k, v in finalize_fields.items():
        body.append(f"--{boundary}".encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="{k}"'.encode('utf-8'))
        body.append(b'')
        body.append(v.encode('utf-8'))
    body.append(f"--{boundary}--".encode('utf-8'))
    body.append(b'')
    
    finalize_req_body = b"\r\n".join(body)
    
    finalize_req = urllib.request.Request(
        f"{BASE_URL}/finalize_upload",
        data=finalize_req_body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    
    with urllib.request.urlopen(finalize_req) as resp:
        res = json.loads(resp.read().decode())
        print(f"[RESULT] /finalize_upload response: {res}")
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        assert res.get("status") in ("success", "complete"), f"Expected success status, got {res.get('status')}"

    print("[SUCCESS] PDF chunked upload and finalization test passed cleanly!")

if __name__ == "__main__":
    test_chunked_pdf_upload()
