"""
KOSTAL Print Agent — Configuration Loader
"""
import json
import os
import logging

logger = logging.getLogger("KostalPrintAgent")

DEFAULT_CONFIG = {
    "server_url": "http://localhost:8000",
    "agent_id": "",
    "auth_token": "",
    "polling_interval_seconds": 5,
    "heartbeat_interval_seconds": 60,
    "local_cache_path": "./cache.db",
    "log_level": "INFO",
    "log_file": "./kostal_print_agent.log",
}


class AgentConfig:
    """Loads and manages agent configuration from config.json."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r") as f:
                loaded = json.load(f)
                self._data.update(loaded)
            logger.info(f"Config loaded from {self.config_path}")
        else:
            logger.warning(f"Config file not found: {self.config_path}, using defaults")

    def save(self):
        with open(self.config_path, "w") as f:
            json.dump(self._data, f, indent=4)
        logger.info(f"Config saved to {self.config_path}")

    @property
    def server_url(self) -> str:
        return self._data.get("server_url", "").rstrip("/")

    @property
    def agent_id(self) -> str:
        return self._data.get("agent_id", "")

    @agent_id.setter
    def agent_id(self, value: str):
        self._data["agent_id"] = value

    @property
    def auth_token(self) -> str:
        return self._data.get("auth_token", "")

    @auth_token.setter
    def auth_token(self, value: str):
        self._data["auth_token"] = value

    @property
    def polling_interval(self) -> int:
        return self._data.get("polling_interval_seconds", 5)

    @property
    def heartbeat_interval(self) -> int:
        return self._data.get("heartbeat_interval_seconds", 60)

    @property
    def cache_path(self) -> str:
        return self._data.get("local_cache_path", "./cache.db")

    @property
    def log_level(self) -> str:
        return self._data.get("log_level", "INFO")

    @property
    def log_file(self) -> str:
        return self._data.get("log_file", "./kostal_print_agent.log")

    @property
    def is_registered(self) -> bool:
        return bool(self.agent_id and self.auth_token)
