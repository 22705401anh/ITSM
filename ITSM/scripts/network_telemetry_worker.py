import sys
import os
import asyncio
import logging

# Setup paths
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import settings
from app.db import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def run_worker():
    """Continuously runs the network discovery and switch telemetry in the background."""
    from app.services.discovery_service import run_auto_discovery
    from app.services.switch_telemetry import poll_all_switch_telemetry
    
    logger.info("Initializing Network Telemetry Worker Database...")
    init_db()
    logger.info("Database initialized. Worker starting.")
    
    while True:
        try:
            logger.info("--- WORKER: STARTING AUTO-DISCOVERY ---")
            await run_auto_discovery()
            
            logger.info("--- WORKER: STARTING SWITCH TELEMETRY ---")
            await poll_all_switch_telemetry()
            
            logger.info("--- WORKER: SLEEPING FOR 30 MINUTES ---")
            await asyncio.sleep(1800)
        except asyncio.CancelledError:
            logger.info("Worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Worker encountered an error: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    if sys.platform == "win32":
        # Required for massive concurrent network sockets on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
