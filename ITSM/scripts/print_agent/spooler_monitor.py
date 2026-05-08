"""
KOSTAL Print Agent — Spooler Monitor

Monitors the Windows Print Spooler via WMI to capture print job events.
Uses Win32_PrintJob WMI class for real-time tracking.
"""
import hashlib
import logging
import socket
import time
from datetime import datetime
from threading import Thread, Event

logger = logging.getLogger("KostalPrintAgent")


class SpoolerMonitor:
    """Monitors the Windows print spooler for job events using WMI."""

    def __init__(self, api_client, cache, config):
        self.api = api_client
        self.cache = cache
        self.config = config
        self._stop_event = Event()
        self._known_jobs = {}  # job_key -> last_status
        self._jobs_submitted_count = 0
        self.hostname = socket.gethostname()

    def start(self):
        """Start the spooler monitoring loop in a background thread."""
        self._stop_event.clear()
        thread = Thread(target=self._monitor_loop, daemon=True, name="SpoolerMonitor")
        thread.start()
        
        cmd_thread = Thread(target=self._command_polling_loop, daemon=True, name="CommandPoller")
        cmd_thread.start()
        
        logger.info("Spooler monitor and command poller started")
        return thread

    def stop(self):
        self._stop_event.set()
        logger.info("Spooler monitor stopping...")

    @property
    def jobs_submitted(self) -> int:
        return self._jobs_submitted_count

    def discover_queues(self) -> list:
        """Discover all local print queues via WMI."""
        try:
            import wmi
            c = wmi.WMI()
            queues = []
            for printer in c.Win32_Printer():
                queues.append({
                    "queue_name": printer.Name or "",
                    "printer_name": printer.Name or "",
                    "share_name": printer.ShareName or "",
                    "driver_name": printer.DriverName or "",
                    "port_name": printer.PortName or "",
                    "location": printer.Location or "",
                    "comment": printer.Comment or "",
                    "is_shared": bool(printer.Shared),
                    "is_network": bool(printer.Network),
                    "is_default": bool(printer.Default),
                    "status": self._map_printer_status(printer.PrinterStatus),
                })
            logger.info(f"Discovered {len(queues)} print queues")
            return queues
        except ImportError:
            logger.error("WMI module not available. Install with: pip install wmi")
            return []
        except Exception as e:
            logger.error(f"Queue discovery failed: {e}")
            return []

    def _monitor_loop(self):
        """Main monitoring loop — polls Win32_PrintJob at configured interval."""
        logger.info(f"Monitoring spooler every {self.config.polling_interval}s")

        try:
            import pythoncom
            pythoncom.CoInitialize()
        except ImportError:
            pass

        try:
            while not self._stop_event.is_set():
                try:
                    self._poll_jobs()
                except Exception as e:
                    logger.error(f"Spooler poll error: {e}")

                self._stop_event.wait(timeout=self.config.polling_interval)
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _poll_jobs(self):
        """Poll Win32_PrintJob and detect new/changed jobs."""
        try:
            import wmi
            c = wmi.WMI()
        except ImportError:
            logger.error("WMI module not available")
            return

        current_jobs = {}
        try:
            for job in c.Win32_PrintJob():
                job_key = f"{self.hostname}|{job.Name}|{job.JobId}"
                current_jobs[job_key] = job

                if job_key not in self._known_jobs:
                    # New job detected
                    self._handle_new_job(job)
                else:
                    # Check for status change
                    old_status = self._known_jobs[job_key]
                    new_status = self._map_job_status(job.StatusMask or 0)
                    if old_status != new_status:
                        self._handle_status_change(job, new_status)

                self._known_jobs[job_key] = self._map_job_status(job.StatusMask or 0)

        except Exception as e:
            logger.error(f"WMI query failed: {e}")
            return

        # Detect completed/removed jobs
        removed_keys = set(self._known_jobs.keys()) - set(current_jobs.keys())
        for key in removed_keys:
            old_status = self._known_jobs.pop(key, None)
            if old_status and old_status not in ("printed", "cancelled", "deleted"):
                self._handle_job_completed(key)

    def _handle_new_job(self, job):
        """Process a newly detected print job."""
        correlation_id = self._make_correlation_id(job)

        # Parse user — WMI returns "DOMAIN\\user" format
        owner = job.Owner or ""
        user_login = owner.split("\\")[-1] if "\\" in owner else owner

        submitted_at = self._parse_wmi_datetime(job.TimeSubmitted)

        job_data = {
            "correlation_id": correlation_id,
            "server_name": self.hostname,
            "queue_name": job.Name.split(",")[0] if job.Name else "",
            "printer_name": job.Name.split(",")[0] if job.Name else "",
            "job_id_windows": job.JobId,
            "user_login": user_login,
            "user_display_name": owner,
            "document_name": job.Document or "",
            "submitted_at": submitted_at,
            "status": self._map_job_status(job.StatusMask or 0),
            "total_pages": job.TotalPages or 0,
            "copies": 1,
            "file_size_bytes": job.Size or 0,
            "driver_name": job.DriverName if hasattr(job, "DriverName") else None,
            "paper_size": job.PaperSize if hasattr(job, "PaperSize") else None,
        }

        # Try to submit to backend
        try:
            resp = self.api.submit_job(job_data)
            self._jobs_submitted_count += 1
            logger.info(f"Submitted job {correlation_id}: {job.Document}")
            
            if resp and isinstance(resp, dict):
                policy_action = resp.get("policy_action")
                printer_name = job.Name.split(",")[0] if job.Name else ""
                if policy_action == "hold":
                    self._control_job(printer_name, job.JobId, "pause")
                elif policy_action == "deny":
                    self._control_job(printer_name, job.JobId, "cancel")
                    
        except Exception:
            # Cache for later
            self.cache.cache_job(correlation_id, job_data)
            logger.warning(f"Cached job {correlation_id} (offline)")

    def _handle_status_change(self, job, new_status):
        """Handle a job status transition."""
        correlation_id = self._make_correlation_id(job)
        event = {
            "correlation_id": correlation_id,
            "event_type": new_status,
            "source": "agent",
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            self.api.submit_events([event])
        except Exception:
            self.cache.cache_event(correlation_id, event)

    def _handle_job_completed(self, job_key):
        """Handle a job that disappeared from the queue (completed or deleted)."""
        parts = job_key.split("|")
        if len(parts) >= 3:
            logger.debug(f"Job completed/removed: {job_key}")

    def _make_correlation_id(self, job) -> str:
        """Create a deterministic correlation ID for deduplication."""
        raw = f"{self.hostname}|{job.Name}|{job.JobId}|{job.TimeSubmitted}|{job.Owner}"
        return hashlib.sha256(raw.encode()).hexdigest()[:64]

    @staticmethod
    def _map_job_status(status_mask: int) -> str:
        """Map Win32_PrintJob.StatusMask to a human-readable status."""
        if status_mask & 0x00000040:
            return "printed"
        if status_mask & 0x00000010:
            return "printing"
        if status_mask & 0x00000020:
            return "deleted"
        if status_mask & 0x00000004:
            return "failed"
        if status_mask & 0x00000001:
            return "queued"  # Paused
        return "queued"

    @staticmethod
    def _map_printer_status(status) -> str:
        """Map Win32_Printer.PrinterStatus to string."""
        status_map = {1: "other", 2: "unknown", 3: "idle", 4: "printing", 5: "warmup",
                      6: "offline", 7: "error"}
        return status_map.get(status, "unknown")

    @staticmethod
    def _parse_wmi_datetime(wmi_dt) -> str:
        """Parse WMI datetime format (e.g. '20260508103000.000000+060') to ISO."""
        if not wmi_dt:
            return datetime.utcnow().isoformat()
        try:
            dt_str = str(wmi_dt)[:14]
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            return dt.isoformat()
        except Exception:
            return datetime.utcnow().isoformat()

    def _control_job(self, printer_name: str, job_id: int, action: str):
        """Use win32print to manipulate a print job."""
        try:
            import win32print
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                if action == "pause":
                    win32print.SetJob(hprinter, job_id, 0, None, win32print.JOB_CONTROL_PAUSE)
                    logger.info(f"Held job {job_id} on {printer_name}")
                elif action == "resume":
                    win32print.SetJob(hprinter, job_id, 0, None, win32print.JOB_CONTROL_RESUME)
                    logger.info(f"Resumed job {job_id} on {printer_name}")
                elif action == "cancel":
                    win32print.SetJob(hprinter, job_id, 0, None, win32print.JOB_CONTROL_CANCEL)
                    logger.info(f"Cancelled job {job_id} on {printer_name}")
            finally:
                win32print.ClosePrinter(hprinter)
        except Exception as e:
            logger.error(f"Failed to {action} job {job_id} on {printer_name}: {e}")

    def _find_printer_for_job(self, job_id: int) -> str:
        try:
            import wmi
            c = wmi.WMI()
            for job in c.Win32_PrintJob():
                if job.JobId == job_id:
                    return job.Name.split(",")[0] if job.Name else None
        except Exception:
            pass
        return None

    def _command_polling_loop(self):
        """Polls backend for commands every 3 seconds."""
        logger.info("Command poller loop initialized")
        while not self._stop_event.is_set():
            try:
                if self.api.is_online:
                    commands = self.api.get_commands()
                    for cmd in commands:
                        cmd_id = cmd.get("id")
                        action = cmd.get("action")
                        job_id_windows = cmd.get("job_id_windows")
                        
                        printer_name = self._find_printer_for_job(job_id_windows)
                        if printer_name:
                            self._control_job(printer_name, job_id_windows, action)
                            self.api.update_command_status(cmd_id, "completed", f"Job {action} executed successfully")
                        else:
                            self.api.update_command_status(cmd_id, "failed", f"Job ID {job_id_windows} not found locally")
            except Exception as e:
                pass
                
            self._stop_event.wait(3.0)
