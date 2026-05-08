"""
KOSTAL Print Agent — REST API Client

Handles all HTTP communication with the KOSTAL ITSM backend.
Includes retry logic and offline cache integration.
"""
import requests
import logging
import socket
from datetime import datetime

logger = logging.getLogger("KostalPrintAgent")


class APIClient:
    """REST client for the KOSTAL ITSM Print Management API."""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._online = False

    @property
    def base_url(self) -> str:
        return self.config.server_url

    def _headers(self) -> dict:
        return {"X-Agent-Token": self.config.auth_token}

    def register(self) -> dict:
        """Register this agent with the backend. Returns agent_id + auth_token."""
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()
        try:
            ip = socket.gethostbyname(hostname)
        except Exception:
            ip = "0.0.0.0"

        payload = {
            "hostname": hostname,
            "ip_address": ip,
            "fqdn": fqdn,
            "os_version": self._get_os_version(),
            "agent_version": "1.0.0",
        }

        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/agent/register",
                json=payload, timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._online = True
            logger.info(f"Registered as agent {data['agent_id']}")
            return data
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            self._online = False
            raise

    def heartbeat(self, queues_count: int = 0, jobs_submitted: int = 0, last_error: str = None) -> bool:
        """Send heartbeat to backend. Returns True if successful."""
        payload = {
            "agent_id": self.config.agent_id,
            "status": "online",
            "queues_count": queues_count,
            "jobs_submitted": jobs_submitted,
            "last_error": last_error,
            "version": "1.0.0",
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/agent/heartbeat",
                json=payload, headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            self._online = True
            return True
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            self._online = False
            return False

    def submit_job(self, job_data: dict) -> dict:
        """Submit a single print job."""
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/jobs",
                json=job_data, headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            self._online = True
            return resp.json()
        except Exception as e:
            logger.warning(f"Job submission failed: {e}")
            self._online = False
            raise

    def submit_jobs_bulk(self, jobs: list) -> dict:
        """Submit batch of print jobs."""
        payload = {"agent_id": self.config.agent_id, "jobs": jobs}
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/jobs/bulk",
                json=payload, headers=self._headers(), timeout=30,
            )
            resp.raise_for_status()
            self._online = True
            return resp.json()
        except Exception as e:
            logger.warning(f"Bulk submission failed: {e}")
            self._online = False
            raise

    def submit_events(self, events: list) -> dict:
        """Submit job lifecycle events."""
        payload = {"agent_id": self.config.agent_id, "events": events}
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/job-events",
                json=payload, headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            self._online = True
            return resp.json()
        except Exception as e:
            logger.warning(f"Event submission failed: {e}")
            self._online = False
            raise

    def report_printers(self, server_hostname: str, queues: list) -> dict:
        """Report discovered print queues to backend."""
        payload = {
            "agent_id": self.config.agent_id,
            "server_hostname": server_hostname,
            "queues": queues,
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/printers/discovered",
                json=payload, headers=self._headers(), timeout=15,
            )
            resp.raise_for_status()
            self._online = True
            return resp.json()
        except Exception as e:
            logger.warning(f"Printer discovery report failed: {e}")
            self._online = False
            raise

    def get_commands(self) -> list:
        """Fetch pending commands from the backend."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/print/agent/commands?agent_id={self.config.agent_id}",
                headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            self._online = True
            return resp.json()
        except Exception as e:
            logger.debug(f"Failed to fetch commands: {e}")
            self._online = False
            return []
            
    def update_command_status(self, command_id: int, status: str, result_message: str = "") -> bool:
        """Report command execution status."""
        payload = {
            "status": status,
            "result_message": result_message
        }
        try:
            resp = self.session.post(
                f"{self.base_url}/api/print/agent/commands/{command_id}/status?agent_id={self.config.agent_id}",
                json=payload, headers=self._headers(), timeout=10,
            )
            resp.raise_for_status()
            self._online = True
            return True
        except Exception as e:
            logger.warning(f"Failed to update command status {command_id}: {e}")
            self._online = False
            return False

    @property
    def is_online(self) -> bool:
        return self._online

    @staticmethod
    def _get_os_version() -> str:
        try:
            import platform
            return f"{platform.system()} {platform.release()} {platform.version()}"
        except Exception:
            return "Windows"
