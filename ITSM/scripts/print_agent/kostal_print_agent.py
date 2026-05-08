"""
KOSTAL Print Agent — Main Entry Point

Windows Service that monitors print spooler events and syncs with KOSTAL ITSM.

Usage:
  python kostal_print_agent.py              # Run interactively (console mode)
  python kostal_print_agent.py install       # Install as Windows Service
  python kostal_print_agent.py start         # Start the Windows Service
  python kostal_print_agent.py stop          # Stop the Windows Service
  python kostal_print_agent.py remove        # Uninstall the Windows Service
"""
import sys
import os
import time
import logging
import socket
from threading import Event

# Add script directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AgentConfig
from cache import LocalCache
from api_client import APIClient
from spooler_monitor import SpoolerMonitor

# ── Logging Setup ──
def setup_logging(config):
    logger = logging.getLogger("KostalPrintAgent")
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    try:
        fh = logging.FileHandler(config.log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass

    return logger


class PrintAgentService:
    """Core agent logic — can run as console app or Windows Service."""

    _svc_name_ = "KOSTALPrintAgent"
    _svc_display_name_ = "KOSTAL Print Agent"
    _svc_description_ = "Monitors Windows print spooler and syncs print jobs to KOSTAL ITSM."

    def __init__(self):
        self.config = AgentConfig()
        self.logger = setup_logging(self.config)
        self.cache = LocalCache(self.config.cache_path)
        self.api = APIClient(self.config)
        self.monitor = SpoolerMonitor(self.api, self.cache, self.config)
        self._stop_event = Event()

    def start(self):
        """Main entry point."""
        self.logger.info("=" * 60)
        self.logger.info("KOSTAL Print Agent v1.0.0 starting...")
        self.logger.info(f"Server: {self.config.server_url}")
        self.logger.info(f"Hostname: {socket.gethostname()}")
        self.logger.info("=" * 60)

        # Step 1: Register if not already registered
        if not self.config.is_registered:
            self._register()

        if not self.config.is_registered:
            self.logger.error("Agent registration failed. Cannot start monitoring.")
            return

        # Step 2: Initial heartbeat
        self.api.heartbeat()

        # Step 3: Discover queues and report
        self._discover_and_report()

        # Step 4: Flush any cached offline jobs
        self._flush_cache()

        # Step 5: Start spooler monitor
        monitor_thread = self.monitor.start()

        # Step 6: Main loop — heartbeat + cache flush
        self.logger.info("Agent running. Press Ctrl+C to stop.")
        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=self.config.heartbeat_interval)
                if self._stop_event.is_set():
                    break

                # Heartbeat
                success = self.api.heartbeat(
                    queues_count=len(self.monitor.discover_queues()),
                    jobs_submitted=self.monitor.jobs_submitted,
                )

                # Flush cache if online
                if success:
                    self._flush_cache()

        except KeyboardInterrupt:
            self.logger.info("Ctrl+C received")
        finally:
            self.stop()

    def stop(self):
        """Clean shutdown."""
        self._stop_event.set()
        self.monitor.stop()
        self.logger.info("KOSTAL Print Agent stopped.")

    def _register(self):
        """Register with the backend and persist credentials."""
        self.logger.info("Registering with KOSTAL ITSM backend...")
        try:
            result = self.api.register()
            self.config.agent_id = result["agent_id"]
            self.config.auth_token = result["auth_token"]
            self.config.save()
            self.logger.info(f"Registration successful: {result['agent_id']}")
        except Exception as e:
            self.logger.error(f"Registration failed: {e}")

    def _discover_and_report(self):
        """Discover local print queues and report to backend."""
        queues = self.monitor.discover_queues()
        if queues:
            try:
                self.api.report_printers(socket.gethostname(), queues)
                self.logger.info(f"Reported {len(queues)} queues to backend")
            except Exception as e:
                self.logger.warning(f"Failed to report queues: {e}")

    def _flush_cache(self):
        """Flush cached offline jobs and events to the backend."""
        pending = self.cache.get_pending_jobs()
        if not pending:
            return

        self.logger.info(f"Flushing {len(pending)} cached jobs...")
        jobs = [p["data"] for p in pending]
        try:
            result = self.api.submit_jobs_bulk(jobs)
            self.cache.remove_jobs([p["cache_id"] for p in pending])
            self.logger.info(
                f"Flushed: {result.get('total_created', 0)} created, "
                f"{result.get('total_duplicates', 0)} duplicates"
            )
        except Exception as e:
            self.logger.warning(f"Cache flush failed: {e}")

        # Flush events
        pending_events = self.cache.get_pending_events()
        if pending_events:
            events = [p["data"] for p in pending_events]
            try:
                self.api.submit_events(events)
                self.cache.remove_events([p["cache_id"] for p in pending_events])
            except Exception:
                pass


try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager

    class WinService(win32serviceutil.ServiceFramework):
        _svc_name_ = "KOSTALPrintAgent"
        _svc_display_name_ = "KOSTAL Print Agent"
        _svc_description_ = "Monitors Windows print spooler and syncs print jobs to KOSTAL ITSM."

        def __init__(self, args):
            import os
            # CRITICAL: Windows Services run with CWD = C:\Windows\System32
            # We must change it to the script directory to find relative files (config/db)
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.agent = PrintAgentService()

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.agent.stop()
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ""),
            )
            self.agent.start()

except ImportError:
    WinService = None


def main():
    """Console entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ("install", "start", "stop", "remove", "update"):
        if WinService is None:
            print("pywin32 is required for Windows Service management.")
            print("Install it with: pip install pywin32")
            sys.exit(1)
        win32serviceutil.HandleCommandLine(WinService)
    else:
        # Interactive console mode
        agent = PrintAgentService()
        agent.start()


if __name__ == "__main__":
    main()
