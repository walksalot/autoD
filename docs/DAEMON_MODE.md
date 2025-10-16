# Daemon Mode — Automatic PDF Processing

**Purpose**: Setup and operations guide for daemon mode (automatic file watching)
**Audience**: System administrators, DevOps engineers
**Last Updated**: 2025-10-16

---

## Overview

Daemon mode enables automatic PDF processing as files arrive from your scanner (e.g., ScanSnap). Instead of manually running `process_inbox.py`, the daemon continuously monitors the inbox folder and processes PDFs automatically.

**Key Features**:
- **File watching**: Detects new PDFs instantly using filesystem events
- **File stabilization**: Waits for scanner to finish writing (handles phased writes for OCR)
- **Queue processing**: Handles multiple PDFs arriving simultaneously
- **Graceful shutdown**: Completes current processing before stopping
- **Auto-restart**: Restarts on crash (systemd/LaunchAgent)
- **Background operation**: Runs silently without user interaction

**Use Cases**:
- ScanSnap scanner integration (automatic processing after scan)
- Dropbox/network folder monitoring
- Always-on production deployments
- Unattended processing workflows

---

## macOS Setup (LaunchAgent)

### 1. Configure the LaunchAgent Plist

Edit `com.paperautopilot.daemon.plist` with your settings:

```bash
# Navigate to project directory
cd /Users/krisstudio/Developer/Projects/autoD

# Edit plist file
nano com.paperautopilot.daemon.plist
```

**Required changes**:
1. Update `OPENAI_API_KEY` (line 26) - Replace `YOUR_API_KEY_HERE` with your actual key
2. Verify Python path (line 13) - Should point to your virtual environment
3. Verify working directory (line 19) - Should point to project root
4. Configure inbox path (line 32) - Set scanner output folder

**Optional configuration**:
```xml
<key>OPENAI_MODEL</key>
<string>gpt-5-mini</string>  <!-- Use gpt-5-nano for lower cost -->

<key>LOG_LEVEL</key>
<string>INFO</string>  <!-- Use WARNING for less logging -->

<key>ENVIRONMENT</key>
<string>production</string>  <!-- Or development/staging -->
```

### 2. Install the LaunchAgent

```bash
# Copy plist to LaunchAgents directory
cp com.paperautopilot.daemon.plist ~/Library/LaunchAgents/

# Load the agent (starts immediately and on login)
launchctl load ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

# Verify it's running
launchctl list | grep paperautopilot
```

**Expected output**:
```
12345   0   com.paperautopilot.daemon
```
(First number is PID, second is exit code, third is label)

### 3. Monitor Daemon Logs (macOS)

```bash
# View stdout logs (processing info)
tail -f logs/daemon_stdout.log

# View stderr logs (errors)
tail -f logs/daemon_stderr.log

# View application logs (structured JSON)
tail -f logs/paper_autopilot.log | jq .

# Check daemon status
launchctl list | grep paperautopilot

# View recent system logs
log show --predicate 'process == "python3" AND message CONTAINS "paperautopilot"' --last 1h
```

### 4. Control Daemon (macOS)

```bash
# Stop daemon
launchctl unload ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

# Start daemon
launchctl load ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

# Restart daemon (reload after config changes)
launchctl unload ~/Library/LaunchAgents/com.paperautopilot.daemon.plist
launchctl load ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

# Remove daemon (disable auto-start)
launchctl unload ~/Library/LaunchAgents/com.paperautopilot.daemon.plist
rm ~/Library/LaunchAgents/com.paperautopilot.daemon.plist
```

---

## Linux Setup (systemd)

### 1. Configure the Systemd Service

Edit `paper-autopilot.service` with your settings:

```bash
# Edit service file
sudo nano paper-autopilot.service
```

**Required changes**:
1. Update `OPENAI_API_KEY` (line 13) - Replace with your actual key
2. Update `User` and `Group` (lines 8-9) - Set to appropriate user
3. Update `WorkingDirectory` (line 10) - Set to project root
4. Update `ExecStart` (line 28) - Verify Python path

**Alternative: Use EnvironmentFile (recommended for secrets)**:
```bash
# Create environment file
sudo mkdir -p /etc/paper_autopilot
sudo nano /etc/paper_autopilot/paper_autopilot.env
```

Add to `paper_autopilot.env`:
```bash
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-5-mini
PAPER_AUTOPILOT_DB_URL=postgresql://user:pass@localhost:5432/paper_autopilot
PAPER_AUTOPILOT_INBOX_PATH=/opt/paper_autopilot/inbox
ENVIRONMENT=production
LOG_LEVEL=INFO
```

Uncomment line 25 in service file:
```ini
EnvironmentFile=/etc/paper_autopilot/paper_autopilot.env
```

### 2. Install the Systemd Service

```bash
# Copy service file to systemd directory
sudo cp paper-autopilot.service /etc/systemd/system/

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable paper-autopilot

# Start service immediately
sudo systemctl start paper-autopilot

# Verify service is running
sudo systemctl status paper-autopilot
```

**Expected output**:
```
● paper-autopilot.service - Paper Autopilot Document Processing Service
     Loaded: loaded (/etc/systemd/system/paper-autopilot.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2025-10-16 10:30:00 UTC; 5min ago
   Main PID: 12345 (python)
      Tasks: 3 (limit: 4915)
     Memory: 150.2M
     CGroup: /system.slice/paper-autopilot.service
             └─12345 /opt/paper_autopilot/.venv/bin/python /opt/paper_autopilot/run_daemon.py
```

### 3. Monitor Daemon Logs (Linux)

```bash
# View live logs
sudo journalctl -u paper-autopilot -f

# View logs from last hour
sudo journalctl -u paper-autopilot --since "1 hour ago"

# View logs with filtering
sudo journalctl -u paper-autopilot | grep "Processing complete"

# View application logs (structured JSON)
tail -f /opt/paper_autopilot/logs/paper_autopilot.log | jq .

# Check service status
sudo systemctl status paper-autopilot
```

### 4. Control Daemon (Linux)

```bash
# Stop daemon
sudo systemctl stop paper-autopilot

# Start daemon
sudo systemctl start paper-autopilot

# Restart daemon (reload after config changes)
sudo systemctl restart paper-autopilot

# Reload service file (after editing .service file)
sudo systemctl daemon-reload
sudo systemctl restart paper-autopilot

# Disable auto-start on boot
sudo systemctl disable paper-autopilot

# Remove service
sudo systemctl stop paper-autopilot
sudo systemctl disable paper-autopilot
sudo rm /etc/systemd/system/paper-autopilot.service
sudo systemctl daemon-reload
```

---

## Configuration Options

All daemon settings can be configured via environment variables or `.env` file:

### Core Configuration

```bash
# Required
OPENAI_API_KEY=sk-...                    # OpenAI API key
OPENAI_MODEL=gpt-5-mini                  # Model (gpt-5-mini, gpt-5-nano, gpt-5, gpt-5-pro, gpt-4.1)

# Paths
PAPER_AUTOPILOT_INBOX_PATH=inbox         # Directory to watch for PDFs
PAPER_AUTOPILOT_DB_URL=sqlite:///paper_autopilot.db  # Database connection

# Environment
ENVIRONMENT=production                   # development, staging, or production
```

### File Watching Configuration

```bash
# File stabilization (handles scanner phased writes)
FILE_STABILIZATION_INTERVAL=0.2          # Check interval in seconds (default: 0.2)
FILE_STABILIZATION_TIMEOUT=2.0           # Max wait time in seconds (default: 2.0)
FILE_STABILIZATION_CHECKS=2              # Required stable checks (default: 2)

# Queue processing
PROCESSING_QUEUE_TIMEOUT=1.0             # Queue timeout during shutdown (default: 1.0)
```

### Processing Configuration

```bash
# API settings
API_TIMEOUT_SECONDS=300                  # API call timeout (30-600s)
MAX_RETRIES=5                            # Retry attempts (1-10)
RATE_LIMIT_RPM=60                        # Rate limit per minute (1-500)
MAX_OUTPUT_TOKENS=60000                  # Max output tokens (1000-100000)

# Parallel processing
BATCH_SIZE=10                            # PDFs to process in parallel (1-100)
MAX_WORKERS=3                            # Thread pool size (1-20)
PROCESSING_TIMEOUT_PER_DOC=60            # Timeout per document (10-600s)
```

### Logging Configuration

```bash
# Logging
LOG_LEVEL=INFO                           # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                          # json or text
LOG_FILE=logs/paper_autopilot.log        # Log file path
LOG_MAX_BYTES=10485760                   # Max log file size (default: 10MB)
LOG_BACKUP_COUNT=5                       # Number of backup files (1-50)
```

---

## Daemon Health Monitoring

### Automated Health Checks

```bash
#!/bin/bash
# Save as: scripts/daemon_health_check.sh

set -e

echo "=== Daemon Health Check ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Check if daemon is running (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if launchctl list | grep -q "com.paperautopilot.daemon"; then
        echo "Daemon Status: ✅ Running (macOS LaunchAgent)"
    else
        echo "Daemon Status: ❌ Not running"
        exit 1
    fi
fi

# Check if daemon is running (Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if systemctl is-active --quiet paper-autopilot; then
        echo "Daemon Status: ✅ Running (systemd)"
    else
        echo "Daemon Status: ❌ Not running"
        exit 1
    fi
fi

# Check recent processing activity
RECENT_COUNT=$(tail -100 logs/paper_autopilot.log | grep -c "Processing complete" || echo "0")
echo "Recent Activity: ${RECENT_COUNT} documents processed (last 100 log entries)"

# Check for errors
ERROR_COUNT=$(tail -100 logs/paper_autopilot.log | grep -c '"level":"ERROR"' || echo "0")
if [ "$ERROR_COUNT" -gt 5 ]; then
    echo "Error Rate: ⚠️  WARNING (${ERROR_COUNT} errors in last 100 entries)"
else
    echo "Error Rate: ✅ OK (${ERROR_COUNT} errors)"
fi

# Check inbox directory
if [ -d "inbox" ]; then
    INBOX_COUNT=$(find inbox -name "*.pdf" | wc -l | tr -d ' ')
    echo "Inbox Queue: ${INBOX_COUNT} PDFs pending"
else
    echo "Inbox Directory: ❌ Not found"
    exit 1
fi

echo "=== Health Check Complete ==="
```

### Monitoring Cron Job (Linux)

```bash
# Add to crontab: crontab -e
# Check daemon health every 5 minutes
*/5 * * * * /path/to/autoD/scripts/daemon_health_check.sh || systemctl restart paper-autopilot
```

---

## Troubleshooting Daemon Issues

### Problem: Daemon not starting

**Symptoms**: Service shows as failed or inactive

**Diagnosis (macOS)**:
```bash
# Check LaunchAgent status
launchctl list | grep paperautopilot

# View stderr logs
cat logs/daemon_stderr.log

# Check system logs
log show --predicate 'process == "python3"' --last 5m
```

**Diagnosis (Linux)**:
```bash
# Check service status
sudo systemctl status paper-autopilot

# View detailed logs
sudo journalctl -u paper-autopilot -n 50

# Check for permission errors
ls -la /opt/paper_autopilot
```

**Solutions**:
1. Verify Python path in service file is correct
2. Check OPENAI_API_KEY is set correctly
3. Verify working directory exists and has correct permissions
4. Check for missing dependencies: `pip list`
5. Verify config validation: `python3 -c "from src.config import get_config; get_config()"`

### Problem: Files not being detected

**Symptoms**: PDFs in inbox not being processed

**Diagnosis**:
```bash
# Check if daemon is watching correct directory
grep "File watcher started" logs/daemon_stdout.log

# Check for file detection events
grep "New PDF detected" logs/paper_autopilot.log

# Verify inbox path
python3 -c "from src.config import get_config; print(get_config().inbox_path)"
```

**Solutions**:
1. Verify PAPER_AUTOPILOT_INBOX_PATH environment variable
2. Check inbox directory permissions (daemon user must have read access)
3. Verify file is actually a PDF (`.pdf` extension)
4. Check if file is hidden (starts with `.`)
5. Ensure file write is complete (check file size stabilization logs)

### Problem: File stabilization timeout

**Symptoms**: Logs show "File stabilization timeout"

**Diagnosis**:
```bash
# Check stabilization events
grep "File size changed" logs/paper_autopilot.log

# Check timeout settings
python3 -c "from src.config import get_config; c = get_config(); \
    print(f'Timeout: {c.file_stabilization_timeout}s, Interval: {c.file_stabilization_interval}s')"
```

**Solutions**:
1. Increase `FILE_STABILIZATION_TIMEOUT` (e.g., 5.0 seconds)
2. Scanner may be writing file slowly - verify scanner settings
3. Check network latency if inbox is on network drive
4. File is still processed after timeout (warning only)

### Problem: High memory usage

**Symptoms**: Daemon consuming excessive memory

**Diagnosis**:
```bash
# Check memory usage (macOS)
ps aux | grep "run_daemon.py"

# Check memory usage (Linux)
systemctl status paper-autopilot

# Check processing queue size
grep "Processing queue" logs/paper_autopilot.log
```

**Solutions**:
1. Reduce `MAX_WORKERS` (default: 3)
2. Reduce `BATCH_SIZE` (default: 10)
3. Check for memory leaks in logs
4. Restart daemon periodically with cron job
5. Add memory limit in systemd service (already configured: `MemoryLimit=2G`)

### Problem: Graceful shutdown taking too long

**Symptoms**: Daemon takes > 30 seconds to stop

**Diagnosis**:
```bash
# Check shutdown logs
grep "Shutting down" logs/daemon_stdout.log

# Check processing queue size during shutdown
grep "Processing queue" logs/paper_autopilot.log
```

**Solutions**:
1. Reduce `PROCESSING_QUEUE_TIMEOUT` (default: 1.0s)
2. Wait for current document to complete (up to 60s per doc)
3. Force kill if necessary: `launchctl kill SIGKILL com.paperautopilot.daemon` (macOS)
4. Force kill if necessary: `sudo systemctl kill -s SIGKILL paper-autopilot` (Linux)

---

## ScanSnap Integration

For automatic processing with ScanSnap scanner, configure scanner to save PDFs to the inbox directory.

**Setup**:
1. Open ScanSnap Home application
2. Go to Settings → Save
3. Set save location to: `/Users/krisstudio/Developer/Projects/autoD/inbox` (or your inbox path)
4. Enable automatic file naming (recommended: `scan_YYYYMMDD_HHMMSS.pdf`)
5. Start daemon with instructions above
6. Scan a test document to verify automatic processing

**Expected workflow**:
1. **Scan** → Document scanned with ScanSnap
2. **Save** → PDF saved to inbox folder
3. **Detect** → Daemon detects new file instantly (< 100ms)
4. **Stabilize** → Daemon waits for scanner to finish writing (typically 200-400ms)
5. **Queue** → PDF added to processing queue
6. **Process** → Document processed with Responses API
7. **Move** → Successfully processed PDF moved to `processed/` folder
8. **Log** → Processing details logged with cost and time

For detailed ScanSnap configuration, see: `docs/scansnap-ix1600-setup.md`

---

## References

- **Production Runbook**: `docs/RUNBOOK.md`
- **Code Architecture**: `docs/CODE_ARCHITECTURE.md`
- **ScanSnap Setup**: `docs/scansnap-ix1600-setup.md`

---

**Maintained By**: Platform Engineering Team
**Last Updated**: 2025-10-16
