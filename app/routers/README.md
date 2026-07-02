# Lanvan Routers Developer Documentation & API Reference

Welcome to the `app/routers` module! This document serves as a senior-level API Reference and developer guide for engineers onboarding or contributing to Lanvan's routing and endpoint architecture.

---

## Directory Map (Relative Links)

* **[pages.py](./pages.py)**: Serves HTML templates for the UI views.
* **[clipboard.py](./clipboard.py)**: Handles shared clipboard endpoints, WebSockets, and persistence.
* **[files.py](./files.py)**: Manages file transfer services, uploads, downloads, and directory management.
* **[system.py](./system.py)**: Handles system monitoring, server health, and lifecycle events.

---

## Core API Reference Specification

### 1. Clipboard Management API

#### Add Entry (`POST /api/clipboard/add`)
* **Content-Type**: `multipart/form-data` or `application/x-www-form-urlencoded`
* **Request Body**:
  * `data` (string, optional): The text content to add.
  * `file` (binary file, optional): The file attachment (such as pasted images).
* **Response (Success - Text)**:
  * **Status Code**: `200 OK`
  * **Headers**: `Content-Type: application/json`
  * **Body**:
    ```json
    {
      "status": "success",
      "msg": "Added to clipboard: text",
      "item": {
        "id": 12,
        "type": "text",
        "content_type": "text",
        "size": 4,
        "timestamp": "08:30:24 PM",
        "preview": "test",
        "is_image_preview": false
      }
    }
    ```
* **Response (Success - Image File Upload)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "success",
      "msg": "Added to clipboard: file",
      "item": {
        "id": 13,
        "type": "file",
        "content_type": "image",
        "size": 4291,
        "timestamp": "08:30:33 PM",
        "preview": "data:image/png;base64,iVBORw0KGgoAAA...",
        "is_image_preview": true
      }
    }
    ```
* **Response (Failure - Payload Empty)**:
  * **Status Code**: `400 Bad Request`
  * **Body**:
    ```json
    {
      "status": "error",
      "msg": "No content provided"
    }
    ```

#### Get Clipboard History (`GET /api/clipboard/list`)
* **Response (Success)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "success",
      "items": [
        {
          "id": 13,
          "type": "file",
          "content_type": "image",
          "filename": "clipboard-image.png",
          "size": 4291,
          "timestamp": "08:30:33 PM",
          "preview": "data:image/png;base64,iVBORw0KGgoAAA...",
          "is_image_preview": true
        }
      ],
      "count": 1
    }
    ```

#### Download / View Clipboard Entry (`GET /api/clipboard/get/{item_id}`)
* **Response (Success - Text Item)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "success",
      "item": {
        "id": 12,
        "type": "text",
        "content_type": "text",
        "data": "test-data-payload",
        "size": 17,
        "timestamp": "08:30:24 PM"
      }
    }
    ```
* **Response (Success - File Item)**:
  * **Status Code**: `200 OK`
  * **Headers**:
    * `Content-Type`: `application/octet-stream` (or inferred MIME type e.g., `image/png`)
    * `Content-Disposition`: `attachment; filename="clipboard-image.png"`
    * `Content-Length`: `4291`
  * **Body**: Binary byte stream of file.

---

### 2. File Transfer API

#### Upload Chunk (`POST /upload_chunk`)
* **Content-Type**: `multipart/form-data`
* **Request Body**:
  * `file` (binary, required): The chunk file byte stream.
  * `chunk_index` (integer, required): Index of the current chunk.
  * `total_chunks` (integer, required): Total number of chunks.
  * `upload_id` (string, required): Unique upload session ID.
  * `filename` (string, required): Original name of the file.
* **Response (Success)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "success",
      "message": "Chunk 2 of 5 uploaded successfully"
    }
    ```

#### Finalize Chunked Upload (`POST /finalize_upload`)
* **Content-Type**: `application/x-www-form-urlencoded` or `application/json`
* **Request Body**:
  * `upload_id` (string, required): The upload session ID.
  * `total_chunks` (integer, required): Total number of chunks.
  * `filename` (string, required): Original name of the file.
* **Response (Success)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "success",
      "filename": "DevResume.pdf",
      "size": 5242880
    }
    ```

---

### 3. System API

#### Get Server Status (`GET /api/server-status`)
* **Response (Success)**:
  * **Status Code**: `200 OK`
  * **Body**:
    ```json
    {
      "status": "online",
      "message": "[OK] Server is running normally",
      "timestamp": 1783003630.24,
      "resources_ready": true,
      "shutdown": false,
      "server_info": {
        "protocol": "http",
        "host": "127.0.0.1:5000",
        "version": "1.0.0",
        "features": ["file_transfer", "clipboard", "real_time_sync"]
      },
      "ios_optimizations": {
        "detected": false,
        "safari": false,
        "mobile_safari": false,
        "device_type": "unknown"
      }
    }
    ```

---

## Onboarding Guide for New Developers

### How to Add a New Endpoint
Follow these steps to add a new route:

1. **Locate the correct router file** based on the domain (e.g., `files.py` for downloads, `system.py` for health/info).
2. **Define the route decorator**:
   ```python
   @router.post("/api/system/restart", name="system_restart")
   async def restart_system(request: Request):
       """Initiate a server restart sequence."""
       # Endpoint logic goes here
       return {"status": "success", "action": "restart_initiated"}
   ```
3. **Register imports**: Avoid importing from `app.main` at the top level of the router files (causes circular import crashes). Always perform these imports locally within the handler function:
   ```python
   @router.post("/api/system/restart")
   async def restart_system():
       # Local import to prevent circular dependency at startup
       from app.main import trigger_restart_helper
       trigger_restart_helper()
   ```
4. **Backward Compatibility**: If the route is accessed by older clients or tests expecting it on the root `routes.py` path, add a mapping facade in `app/routes.py`:
   ```python
   from app.routers.system import restart_system
   # Explicitly expose it on the facade routing registry
   ```
5. **Verify your code**: Run the testing suite to check that nothing is broken:
   ```bash
   python qt.py
   ```

### Troubleshooting Common Pitfalls

#### 1. JSON Serialization Crash (HTTP 500)
* **Symptoms**: The console shows `SyntaxError: Unexpected token 'I', "Internal S"...` on list endpoints.
* **Cause**: Returning Python objects like `bytes` or complex database classes directly inside dictionaries.
* **Fix**: Ensure all binary payloads are either converted to `base64` strings (for previews) or filtered out of JSON list results completely.

#### 2. Startup Circular Imports
* **Symptoms**: The server crashes immediately at startup with `ImportError: cannot import name 'app' from partially initialized module`.
* **Fix**: Shift imports of `app`, `shutdown_event`, or managers from the file header down into the local execution block of the respective endpoints.
