"""
File watching daemon for automatic PDF processing.

Monitors inbox directory and automatically processes PDFs as they arrive from scanner.
Handles file stabilization (waits for scanner to finish writing) and queues processing.
"""

from __future__ import annotations

import os
import signal
import sys
import time
import threading
from pathlib import Path
from queue import Queue, Empty

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.config import get_config
from src.logging_config import setup_logging
from src.processor import process_document
from src.database import DatabaseManager
from src.api_client import ResponsesAPIClient
from src.vector_store import VectorStoreManager


logger = setup_logging(
    log_level=get_config().log_level,
    log_format=get_config().log_format,
    log_file=str(get_config().log_file),
)


class FileStabilizer:
    """
    Waits for file size to stabilize before processing.

    Handles scanner's phased writes (e.g., when adding OCR text layer).
    Polls file size at regular intervals until it stops changing.
    """

    def __init__(
        self,
        interval: float = 0.2,  # Check every 200ms
        timeout: float = 2.0,  # Max wait 2 seconds
        required_stable_checks: int = 2,  # Require 2 consecutive stable checks
    ):
        self.interval = interval
        self.timeout = timeout
        self.required_stable_checks = required_stable_checks

    def wait_for_stable(self, file_path: Path) -> bool:
        """
        Wait for file size to stabilize.

        Args:
            file_path: Path to file to monitor

        Returns:
            True if file stabilized, False if timeout reached
        """
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return False

        start_time = time.time()
        last_size = -1
        stable_count = 0

        while time.time() - start_time < self.timeout:
            try:
                current_size = file_path.stat().st_size

                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= self.required_stable_checks:
                        elapsed = time.time() - start_time
                        logger.debug(
                            f"File stabilized: {file_path.name} ({current_size} bytes) after {elapsed:.3f}s"
                        )
                        return True
                else:
                    stable_count = 0
                    logger.debug(
                        f"File size changed: {file_path.name} ({last_size} → {current_size} bytes)"
                    )

                last_size = current_size
                time.sleep(self.interval)

            except FileNotFoundError:
                logger.warning(f"File disappeared during stabilization: {file_path}")
                return False
            except Exception as e:
                logger.error(f"Error checking file stability: {e}")
                return False

        # Timeout reached, but file exists
        logger.warning(
            f"File stabilization timeout: {file_path.name} (processing anyway)"
        )
        return True


class PDFFileHandler(FileSystemEventHandler):
    """
    Handles file system events for PDF files.

    Monitors new PDF files and adds them to processing queue after stabilization.
    """

    def __init__(
        self,
        processing_queue: Queue,
        stabilizer: FileStabilizer,
        processed_files: set,
    ):
        super().__init__()
        self.processing_queue = processing_queue
        self.stabilizer = stabilizer
        self.processed_files = processed_files
        self.lock = threading.Lock()

    def is_pdf_file(self, file_path: Path) -> bool:
        """Check if file is a PDF."""
        return file_path.suffix.lower() == ".pdf" and file_path.is_file()

    def should_process(self, file_path: Path) -> bool:
        """Check if file should be processed."""
        with self.lock:
            # Skip if already processed
            if str(file_path) in self.processed_files:
                return False

            # Skip hidden files
            if file_path.name.startswith("."):
                return False

            # Skip temporary files
            if file_path.name.endswith((".tmp", ".part", ".crdownload")):
                return False

            return True

    def handle_pdf_file(self, file_path: Path):
        """Handle a new or modified PDF file."""
        if not self.should_process(file_path):
            return

        logger.info(
            f"New PDF detected: {file_path.name}",
            extra={"event": "file_detected", "pdf_filename": file_path.name},
        )

        # Wait for file size to stabilize
        if self.stabilizer.wait_for_stable(file_path):
            with self.lock:
                self.processed_files.add(str(file_path))

            # Add to processing queue
            self.processing_queue.put(file_path)
            logger.info(
                f"File queued for processing: {file_path.name}",
                extra={"event": "file_queued", "pdf_filename": file_path.name},
            )
        else:
            logger.warning(f"File failed stabilization check: {file_path.name}")

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self.is_pdf_file(file_path):
            self.handle_pdf_file(file_path)

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self.is_pdf_file(file_path):
            self.handle_pdf_file(file_path)


class DaemonManager:
    """
    Main daemon manager for file watching and processing.

    Coordinates file watching, queue management, and document processing.
    Handles graceful shutdown on signals (SIGTERM, SIGINT).
    """

    def __init__(
        self,
        inbox_path: Path,
        processed_path: Path,
        failed_path: Path,
    ):
        self.inbox_path = inbox_path
        self.processed_path = processed_path
        self.failed_path = failed_path

        self.config = get_config()
        self.processing_queue = Queue()
        self.processed_files = set()
        self.is_running = False
        self.shutdown_event = threading.Event()

        # Initialize components
        self.stabilizer = FileStabilizer(
            interval=0.2,
            timeout=2.0,
            required_stable_checks=2,
        )

        self.handler = PDFFileHandler(
            processing_queue=self.processing_queue,
            stabilizer=self.stabilizer,
            processed_files=self.processed_files,
        )

        self.observer = Observer()

        # Initialize processing clients (reused across all documents)
        self.db_manager = DatabaseManager(self.config.paper_autopilot_db_url)
        self.db_manager.create_tables()  # Ensure tables exist

        self.api_client = ResponsesAPIClient()
        self.vector_manager = VectorStoreManager()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        logger.info(
            f"Daemon initialized: watching {inbox_path}",
            extra={"inbox_path": str(inbox_path)},
        )

    def signal_handler(self, signum, frame):
        """Handle shutdown signals (SIGTERM, SIGINT)."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.shutdown()

    def process_existing_files(self):
        """Process any existing PDF files in inbox at startup."""
        pdf_files = sorted(self.inbox_path.glob("*.pdf"))

        if pdf_files:
            logger.info(f"Found {len(pdf_files)} existing PDF files at startup")

            for pdf_file in pdf_files:
                if self.handler.should_process(pdf_file):
                    # Files already on disk should be stable
                    with self.handler.lock:
                        self.handler.processed_files.add(str(pdf_file))

                    self.processing_queue.put(pdf_file)
                    logger.info(
                        f"Queued existing file: {pdf_file.name}",
                        extra={
                            "event": "existing_file_queued",
                            "pdf_filename": pdf_file.name,
                        },
                    )

    def process_queue(self):
        """Process files from queue (runs in separate thread)."""
        while self.is_running or not self.processing_queue.empty():
            try:
                # Get file from queue (with timeout for graceful shutdown)
                file_path = self.processing_queue.get(timeout=1.0)

                logger.info(
                    f"Processing: {file_path.name}",
                    extra={"event": "processing_start", "pdf_filename": file_path.name},
                )

                # Process document using existing pipeline
                result = process_document(
                    file_path=file_path,
                    db_manager=self.db_manager,
                    api_client=self.api_client,
                    vector_manager=self.vector_manager,
                    skip_duplicates=True,
                )

                # Handle result
                if result.success:
                    if result.duplicate_of:
                        logger.info(
                            f"Duplicate detected: {file_path.name} (original ID: {result.duplicate_of})",
                            extra={
                                "event": "duplicate_detected",
                                "pdf_filename": file_path.name,
                                "duplicate_of": result.duplicate_of,
                            },
                        )
                        # Move to processed (duplicate is successful case)
                        dest = self.processed_path / file_path.name
                        file_path.rename(dest)
                    else:
                        logger.info(
                            f"Successfully processed: {file_path.name} "
                            f"(ID: {result.document_id}, Cost: ${result.cost_usd:.4f}, "
                            f"Time: {result.processing_time_seconds:.2f}s)",
                            extra={
                                "event": "processing_success",
                                "pdf_filename": file_path.name,
                                "document_id": result.document_id,
                                "cost_usd": result.cost_usd,
                                "processing_time": result.processing_time_seconds,
                            },
                        )
                        # Move to processed directory
                        dest = self.processed_path / file_path.name
                        file_path.rename(dest)
                else:
                    logger.error(
                        f"Processing failed: {file_path.name} - {result.error}",
                        extra={
                            "event": "processing_failed",
                            "pdf_filename": file_path.name,
                            "error": result.error,
                        },
                    )
                    # Move to failed directory
                    dest = self.failed_path / file_path.name
                    file_path.rename(dest)

                self.processing_queue.task_done()

            except Empty:
                # Queue timeout, check if still running
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error in processing queue: {e}", exc_info=True
                )

        logger.info("Processing queue thread terminated")

    def start(self):
        """Start the daemon."""
        if self.is_running:
            logger.warning("Daemon already running")
            return

        logger.info("Starting daemon...")
        self.is_running = True

        # Create directories if they don't exist
        self.inbox_path.mkdir(exist_ok=True, parents=True)
        self.processed_path.mkdir(exist_ok=True, parents=True)
        self.failed_path.mkdir(exist_ok=True, parents=True)

        # Process any existing files
        self.process_existing_files()

        # Start file watcher
        self.observer.schedule(self.handler, str(self.inbox_path), recursive=False)
        self.observer.start()
        logger.info(f"File watcher started: {self.inbox_path}")

        # Start processing thread
        self.processing_thread = threading.Thread(
            target=self.process_queue,
            name="ProcessingThread",
            daemon=False,  # Don't daemon thread so it can finish during shutdown
        )
        self.processing_thread.start()
        logger.info("Processing thread started")

        logger.info("Daemon running (press Ctrl+C to stop)")

        # Keep main thread alive
        try:
            while self.is_running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
            self.shutdown()

    def shutdown(self):
        """Gracefully shutdown the daemon."""
        if not self.is_running:
            return

        logger.info("Shutting down daemon...")
        self.is_running = False

        # Stop file watcher
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5.0)
            logger.info("File watcher stopped")

        # Wait for processing queue to empty (with timeout)
        logger.info("Waiting for processing queue to empty...")
        queue_empty_start = time.time()
        while not self.processing_queue.empty() and (
            time.time() - queue_empty_start < 30.0
        ):
            time.sleep(0.5)

        if not self.processing_queue.empty():
            logger.warning(
                f"Processing queue not empty after 30s (remaining: {self.processing_queue.qsize()})"
            )

        # Wait for processing thread
        if self.processing_thread.is_alive():
            logger.info("Waiting for processing thread to finish...")
            self.processing_thread.join(timeout=10.0)

            if self.processing_thread.is_alive():
                logger.warning("Processing thread did not terminate gracefully")

        logger.info("Daemon shutdown complete")

    def run(self):
        """Run the daemon (convenience method)."""
        try:
            self.start()
        except Exception as e:
            logger.error(f"Daemon failed: {e}", exc_info=True)
            self.shutdown()
            sys.exit(1)


def main():
    """Main entry point for daemon."""
    config = get_config()

    # Determine paths from environment or defaults
    inbox_path_str = os.getenv("PAPER_AUTOPILOT_INBOX_PATH")
    if inbox_path_str:
        inbox_path = Path(inbox_path_str)
        # Use sibling directories for processed/failed
        paper_dir = inbox_path.parent
        processed_path = paper_dir / "Processed"
        failed_path = paper_dir / "Failed"
    else:
        # Fallback to a default directory relative to CWD
        inbox_path = Path("inbox")
        processed_path = inbox_path.parent / "processed"
        failed_path = inbox_path.parent / "failed"

    logger.info(
        f"Starting Paper Autopilot daemon (v{config.paper_autopilot_version})",
        extra={"version": config.paper_autopilot_version},
    )

    daemon = DaemonManager(
        inbox_path=inbox_path,
        processed_path=processed_path,
        failed_path=failed_path,
    )

    daemon.run()


if __name__ == "__main__":
    main()
