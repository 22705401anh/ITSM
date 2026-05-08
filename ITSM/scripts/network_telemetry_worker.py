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

async def run_discovery_loop():
    from app.services.discovery_service import run_auto_discovery
    while True:
        try:
            logger.info("--- WORKER: STARTING AUTO-DISCOVERY ---")
            await run_auto_discovery()
            logger.info("--- WORKER: DISCOVERY SLEEPING FOR 1 HOUR ---")
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Discovery loop error: {e}")
            await asyncio.sleep(60)

async def run_telemetry_loop():
    from app.services.switch_telemetry import poll_fast_port_traffic
    while True:
        try:
            # Removed info log here to prevent spamming the console every 10 seconds
            await poll_fast_port_traffic()
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Fast telemetry loop error: {e}")
            await asyncio.sleep(10)

async def run_full_telemetry_loop():
    from app.services.switch_telemetry import poll_all_switch_telemetry
    while True:
        try:
            logger.info("--- WORKER: STARTING FULL SWITCH TELEMETRY ---")
            await poll_all_switch_telemetry()
            logger.info("--- WORKER: FULL TELEMETRY SLEEPING FOR 5 MINUTES ---")
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Full telemetry loop error: {e}")
            await asyncio.sleep(60)

async def run_worker():
    """Continuously runs the network discovery and switch telemetry in the background."""
    logger.info("Initializing Network Telemetry Worker Database...")
    init_db()
    logger.info("Database initialized. Worker starting.")
    
    t1 = asyncio.create_task(run_discovery_loop())
    t2 = asyncio.create_task(run_telemetry_loop())
    t3 = asyncio.create_task(run_full_telemetry_loop())
    
    try:
        await asyncio.gather(t1, t2, t3)
    except asyncio.CancelledError:
        t1.cancel()
        t2.cancel()
        t3.cancel()
        logger.info("Worker cancelled.")

if __name__ == "__main__":
    if sys.platform == "win32":
        # Required to fix UDP/datagram transport assertion errors with pysnmp on Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
