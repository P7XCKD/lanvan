# Implementation Plan: Synchronize Synthetic Folder Upload Rows and Upload Tray Header

## Problem Analysis

Runtime evidence and UI inspection reveal the root cause of the divergence shown in the screenshot:

1. **Upload Tray Header Text Ambiguity**:
   In `renderUploadTray()` (`app-init.js:3900`), `headerTitle` was constructed as:
   `"Uploading " + activePendingCount + " file • " + totalSpeedMB`
   - `activePendingCount` counts ONLY currently active network transfers (e.g. `1` when uploading 1 parallel file at a time).
   - When uploading a 16-file folder batch where 15 files have completed and 1 is active, the tray header rendered:
     `Uploading 1 file • 89.4 MB/s`
   - This caused the user to believe only 1 file total was being processed, contradicting the folder progress.

2. **Synthetic Folder Subtext Ambiguity**:
   In `ProjectionLayer` (`projection-layer.js:224`) and `renderPrototypeFileList()` (`app-init.js`):
   - The folder row calculated overall byte-weighted progress (`5%`) but displayed `5% • Uploading`.
   - It lacked the batch completion count (`15 of 16 completed`), creating an apparent mismatch between the `5%` progress and the tray's `Uploading 1 file`.

---

## Proposed Changes

### 1. Update Upload Tray Header Formatting (`app-init.js`)

#### [MODIFY] [app-init.js](file:///c:/Users/Public/Probz/Code/lanvan/app/static/js/app-init.js#L3895-L3902)
- Update `headerTitle` generation in `renderUploadTray()`:
  - When `totalCount > 1` and `activePendingCount > 0`:
    Display completed/active batch progress:
    `Uploading ${completedOrDeletedCount + 1} of ${totalCount} files (${avgPct}%) • ${totalSpeedMB}`
  - Example output: `Uploading 15 of 16 files (5%) • 89.4 MB/s`

### 2. Update Synthetic Folder Subtext Formatting (`projection-layer.js` & `app-init.js`)

#### [MODIFY] [projection-layer.js](file:///c:/Users/Public/Probz/Code/lanvan/app/static/js/projection-layer.js#L224-L240)
- In `ProjectionLayer.prototype.buildCurrentFolderViewModel`:
  - Calculate `sFolder.completedCount` and `sFolder.totalCount`.
  - Pass `uploadSubtext` on synthetic folder ViewModels:
    `5% • Uploading (${completedCount}/${totalCount} files)`

#### [MODIFY] [app-init.js](file:///c:/Users/Public/Probz/Code/lanvan/app/static/js/app-init.js#L550-L580)
- Render `uploadSubtext` on synthetic folder rows so the file list and tray header display 100% identical batch statistics.

---

## Verification Plan

### Automated Tests
1. Run Playwright script simulating multi-file folder upload and assert:
   - Floating Upload Tray header text contains total batch count (`of 16 files`).
   - Synthetic Folder Row text matches total batch progress and count.
2. Run full regression test suite:
   ```powershell
   python qt.py --fast
   ```

### Manual Verification
1. Upload a folder containing multiple files.
2. Confirm the Floating Upload Tray header and Folder Row in the file list update in lockstep with identical counts and progress percentages.
