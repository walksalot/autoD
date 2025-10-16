# ScanSnap iX1600 Quick Setup Guide for Paper Autopilot

**Purpose:** Step-by-step guide to configure the ScanSnap iX1600 scanner for automated document processing with Paper Autopilot.

**Prerequisites:**
- ScanSnap iX1600 scanner (connected via USB or Wi-Fi)
- macOS 14.0 or later
- Paper Autopilot installed and configured

---

## Overview

This guide walks through configuring the ScanSnap iX1600 to work optimally with Paper Autopilot's automated pipeline. The key is creating a "Scan to File" profile that saves PDFs directly to the inbox folder without manual intervention.

**Time Required:** 15-20 minutes

---

## Step 1: Install ScanSnap Home Software

1. Download the latest ScanSnap Home from the official website:
   - Visit: https://www.pfu.ricoh.com/global/scanners/scansnap/dl/
   - Select your model: **ScanSnap iX1600**
   - Download the macOS installer

2. Run the installer and follow the prompts
   - Grant necessary permissions when requested
   - Complete the initial setup wizard

3. Connect your scanner:
   - **USB:** Plug in the USB cable and power on the scanner
   - **Wi-Fi:** Follow the on-screen instructions to connect via Wi-Fi

4. Verify connection:
   - Open ScanSnap Home
   - Check that the scanner appears in the device list
   - Look for the scanner name in the top toolbar

---

## Step 2: Create Paper Autopilot Inbox Folder

Paper Autopilot monitors a specific folder for new scans. By default, this is `~/Paper/Inbox/`.

1. Open Terminal or Finder

2. Create the inbox directory:
   ```bash
   mkdir -p ~/Paper/Inbox
   ```

3. Verify the folder exists:
   ```bash
   ls -la ~/Paper/
   ```

**Alternative Path:**
If you configured Paper Autopilot to use a different inbox path (via `PA_INBOX_PATH` environment variable), use that path instead.

---

## Step 3: Configure Scan Profile

Create a profile that automatically saves scans to the Paper Autopilot inbox without any manual prompts.

### 3.1 Create New Profile

1. Open **ScanSnap Home**

2. Click the **"Scan"** button in the toolbar

3. In the profile dropdown, click **"Edit Profiles..."** or **"Add Profile"**

4. Click **"Add Profile"** button (usually a "+" icon)

5. Name the profile: **"Paper Autopilot - Auto Save"**

### 3.2 Configure Profile Settings

**Managing Options:**

1. Set **"Type"** to **"Mac (Scan to file)"**
   - This tells ScanSnap to save files directly to disk
   - Bypasses the internal content management system

**Scanning Settings:**

1. **Image quality:**
   - Select: **"Normal"** or **"Fine"** (300 dpi recommended)
   - Color mode: **"Auto Detect"** (scanner determines color vs. grayscale)

2. **Paper size:**
   - Select: **"Auto Detect"**

3. **Duplex:**
   - Enable: **"Scan both sides"**

**File Format:**

1. Select format: **"PDF (.pdf)"**

2. **OCR Settings:**
   - Disable **"Convert to Searchable PDF"**
   - **Why:** Paper Autopilot performs its own OCR using Apple Vision framework
   - ScanSnap OCR adds processing time and file writes in phases
   - Better to let Paper Autopilot handle OCR consistently

**Save Settings:**

1. Click **"Save"** or **"Destination"** section

2. Select **"Save to Folder"**

3. Click **"Browse..."** and navigate to:
   ```
   /Users/[YourUsername]/Paper/Inbox
   ```
   Or use the path you created in Step 2

4. **Critical:** Uncheck **"Save images with new file names after scanning"**
   - This prevents filename prompt dialog
   - Files will use auto-generated names (e.g., `Scan_20251015_123456.pdf`)

5. Set **"Application"** to **"None (Scan to file)"**
   - No post-scan actions
   - Just save the file and stop

### 3.3 Disable Quick Menu

Quick Menu causes a popup after each scan, requiring manual action selection.

1. In profile settings, find **"Quick Menu"** option

2. Ensure it's set to **"Do not use Quick Menu"** or **"Off"**

3. If there's a global Quick Menu setting:
   - Go to **ScanSnap Home > Preferences > Quick Menu**
   - Disable Quick Menu for this profile

### 3.4 Set Profile Icon (Optional)

1. Assign a color or icon to the profile for easy identification

2. This icon will appear on the scanner's touchscreen

### 3.5 Save and Sync Profile

1. Click **"Save"** or **"OK"** to save the profile

2. Wait for profile sync to scanner (usually automatic)
   - The new profile should appear on the iX1600's touchscreen within a few seconds

---

## Step 4: Configure Scanner Settings (Optional)

### 4.1 Adjust Auto Power-Off Timer

To keep the scanner ready for spontaneous scanning:

1. On the scanner touchscreen, tap **Settings** icon

2. Navigate to **"Power Settings"** or **"Auto Power Off"**

3. Set to **"30 minutes"** or **"60 minutes"** (instead of default 15 minutes)

### 4.2 Set Default Profile

1. On scanner touchscreen, find the "Paper Autopilot - Auto Save" profile

2. Long-press or access profile menu

3. Select **"Set as Default"** (if available)

---

## Step 5: Test the Setup

### 5.1 Test Scan

1. Load a test document into the scanner's feeder (1-2 pages recommended)

2. On the scanner touchscreen:
   - Select **"Paper Autopilot - Auto Save"** profile
   - Press the **Scan** button

3. Scanner should:
   - Scan the document (both sides if duplex enabled)
   - Save PDF immediately to `~/Paper/Inbox/`
   - Complete without any popups or prompts

### 5.2 Verify File Appears

1. Open Finder and navigate to `~/Paper/Inbox/`

2. You should see a new PDF file:
   - Example name: `Scan_20251015_123456.pdf`
   - File should appear within 2-3 seconds of scan completion

3. Open the PDF to verify it scanned correctly

### 5.3 Monitor Paper Autopilot Detection

If Paper Autopilot agent is running:

1. Check the agent logs:
   ```bash
   tail -f ~/Library/Logs/PaperAutopilot/agent.log
   ```
   Or check the debug log:
   ```bash
   tail -f /tmp/paperautopilot-debug.log
   ```

2. You should see messages like:
   ```
   📥 InboxMonitor: New file detected: Scan_20251015_123456.pdf
   ⏳ FileWatcher: Size changed 0 → 245123 bytes, waiting...
   ✓ FileWatcher: File size stable (245123 bytes) after 400ms
   📋 JobQueue: Created job [uuid] for Scan_20251015_123456.pdf
   ```

3. The file should be processed through the pipeline:
   - Deduplication check
   - Validation
   - OCR extraction
   - Classification
   - Final naming and organization

---

## Step 6: Paper Autopilot Configuration

Ensure Paper Autopilot is configured to watch the correct inbox path.

### 6.1 Check Environment Variables

If running the agent manually:

```bash
# Check current configuration
PA_INBOX_PATH=~/Paper/Inbox swift run PaperAutopilotAgent
```

### 6.2 LaunchAgent Configuration

If running as a LaunchAgent, verify the plist configuration:

1. Check the plist file:
   ```bash
   cat ~/Library/LaunchAgents/com.paperautopilot.agent.plist
   ```

2. Verify the `PA_INBOX_PATH` environment variable matches your inbox folder

3. Reload the LaunchAgent if you made changes:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.paperautopilot.agent.plist
   launchctl load ~/Library/LaunchAgents/com.paperautopilot.agent.plist
   ```

---

## Optimal Settings Summary

| Setting | Recommended Value | Reason |
|---------|------------------|---------|
| **Profile Type** | Mac (Scan to file) | Direct file save, no content management |
| **Save Location** | `~/Paper/Inbox/` | Paper Autopilot watch folder |
| **File Format** | PDF | Universal document format |
| **OCR** | Disabled | Paper Autopilot handles OCR |
| **Resolution** | 300 dpi (Normal/Fine) | Balance of quality and speed |
| **Color Mode** | Auto Detect | Scanner optimizes per page |
| **Duplex** | Enabled | Scan both sides automatically |
| **Quick Menu** | Disabled | No manual intervention |
| **Filename Prompt** | Disabled | Auto-generated names |
| **Application** | None | No post-scan actions |
| **Auto Power-Off** | 30-60 minutes | Stay ready for scanning |

---

## Troubleshooting

### Files Not Appearing in Inbox

**Problem:** After scanning, no file appears in `~/Paper/Inbox/`

**Solutions:**
1. Verify profile save location is correct:
   - Open profile settings in ScanSnap Home
   - Check "Save to Folder" path
   - Ensure it matches Paper Autopilot inbox

2. Check ScanSnap Home is not in managed mode:
   - Profile type should be "Mac (Scan to file)"
   - Not "Documents" or "Receipts" (managed types)

3. Look for files in default location:
   - Check `~/Documents/ScanSnap Home/`
   - If files appear there, profile is using managed mode

### Scanner Shows Filename Prompt

**Problem:** After scanning, popup asks for filename

**Solutions:**
1. In profile settings, uncheck:
   - "Save images with new file names after scanning"
   - "Prompt for filename"

2. Ensure "Application" is set to "None (Scan to file)"

### Quick Menu Popup Appears

**Problem:** Quick Menu appears after scan, requiring action selection

**Solutions:**
1. In profile settings:
   - Set Quick Menu to "Do not use" or "Off"

2. In global preferences:
   - ScanSnap Home > Preferences > Quick Menu
   - Disable for this profile

### Paper Autopilot Not Processing Files

**Problem:** Files appear in inbox but aren't processed

**Solutions:**
1. Check agent is running:
   ```bash
   ps aux | grep PaperAutopilotAgent
   ```

2. Check agent logs:
   ```bash
   tail -f /tmp/paperautopilot-debug.log
   ```

3. Verify inbox path matches:
   - Check `PA_INBOX_PATH` environment variable
   - Should match ScanSnap save location

4. Test file detection manually:
   ```bash
   # Copy a test PDF to inbox
   cp ~/Downloads/test.pdf ~/Paper/Inbox/
   # Check logs for detection
   ```

### File Size Keeps Changing

**Problem:** Logs show repeated "Size changed" messages

**Cause:** ScanSnap Home is writing file in phases (e.g., adding OCR text layer)

**Solution:**
1. Disable ScanSnap OCR in profile settings:
   - Uncheck "Convert to Searchable PDF"
   - This eliminates phased writes

2. Paper Autopilot's file stabilization will wait for size to stabilize:
   - Checks every 200ms
   - Requires 2 consecutive size matches
   - Timeout after 2 seconds (processes anyway)

### Permission Errors

**Problem:** "Permission denied" errors in logs

**Solutions:**
1. Grant Full Disk Access:
   - System Settings > Privacy & Security > Full Disk Access
   - Add PaperAutopilotAgent

2. Grant Files and Folders access:
   - System Settings > Privacy & Security > Files and Folders
   - Enable access to Documents folder

---

## Advanced Configuration

### Multiple Profiles for Different Document Types

You can create multiple profiles for different workflows:

1. **"Paper Autopilot - Mail"**:
   - Save to: `~/Paper/Inbox/Mail/`
   - Paper Autopilot can route differently based on subfolder

2. **"Paper Autopilot - Receipts"**:
   - Save to: `~/Paper/Inbox/Receipts/`
   - Higher classification priority for receipts

### Network Folder Destination

To save scans to a network location:

1. Mount network share on Mac:
   ```bash
   # Mount SMB share
   mount -t smbfs //server/share /Volumes/NetworkDocs
   ```

2. Set profile save location to network path:
   - Example: `/Volumes/NetworkDocs/Inbox/`

3. Ensure Mac is connected to network when scanning

### Wi-Fi Scanning Setup

To scan wirelessly:

1. In ScanSnap Home, go to **Preferences > Scanner**

2. Select **"Connect via Wi-Fi"**

3. Follow the setup wizard:
   - Scanner displays Wi-Fi network list
   - Select your network
   - Enter Wi-Fi password

4. Once connected, scanner shows Wi-Fi icon

5. Test scanning - files save to Mac over Wi-Fi

**Note:** Mac must be on and ScanSnap Home running for Wi-Fi scanning to work.

---

## Workflow Summary

**Complete End-to-End Flow:**

1. **User Action:**
   - Load documents into iX1600 feeder
   - Select "Paper Autopilot - Auto Save" on touchscreen
   - Press Scan button

2. **Scanner Processing:**
   - Scans pages (duplex, auto-orientation, blank removal)
   - Generates PDF with auto-generated filename
   - Saves directly to `~/Paper/Inbox/`

3. **File Stabilization (2-4 seconds):**
   - FileWatcher detects new file via FSEvents
   - Waits for file size to stabilize (handles phased writes)
   - File confirmed ready for processing

4. **Paper Autopilot Processing:**
   - Deduplication (content hash check)
   - Validation (PDF structure, page count)
   - OCR (Apple Vision framework)
   - Layout analysis (headers, regions, ROI crops)
   - Classification (document type, counterparty)
   - Field extraction (dates, amounts, IDs)
   - Entity resolution (vendors, properties)
   - Validation (code-based checks)
   - Naming (standardized filename)
   - Metadata embedding (XMP)
   - Organization (taxonomy-based folders)

5. **Result:**
   - Final PDF: `SDG&E — Bill — 2025-10 — Electric — Acct 4821 — LJ-5970.pdf`
   - Location: `~/Paper/Archive/LJ-5970/Bills/Utility/`
   - Searchable, indexed, ready for action

**Total Time:** ~6-8 seconds per document (P95)

---

## Reference Documents

- [ScanSnap iX1600 Comprehensive Guide](./scansnap-ix1600.md) - Full hardware and software documentation
- [Paper Autopilot Overview](../overview.md) - Project status and architecture
- [Initial Specification](../../initial_spec.md) - Complete system specification
- [Phase 2 Summary](../phase-2-summary.md) - FileWatcher implementation details
- [Phase 3 Summary](../phase-3-summary.md) - OCR pipeline details

---

**Last Updated:** 2025-10-15
**Scanner Model:** Fujitsu ScanSnap iX1600
**ScanSnap Home Version:** Latest (as of October 2025)
**Paper Autopilot Version:** 0.3.2
