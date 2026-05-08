"""
Background Worker for Print Management SNMP Polling
Runs continuously to poll printers every 5 minutes.
"""
import asyncio
import logging
import sys
import os
import time

# Ensure the app module is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import SessionLocal, init_db
from app.services.print_snmp_service import PrintSNMPService

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] PrintSNMP: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def run_snmp_polling_loop():
    logger.info("Initializing Database for Print SNMP Worker...")
    init_db()
    logger.info("Starting Print Management SNMP Polling Worker...")
    
    while True:
        try:
            db = SessionLocal()
            service = PrintSNMPService(db)
            
            logger.info("Starting polling cycle...")
            start_time = time.time()
            
            await service.poll_all_enabled_printers()
            
            elapsed = time.time() - start_time
            logger.info(f"Polling cycle completed in {elapsed:.2f} seconds.")
            
        except Exception as e:
            logger.error(f"Error in SNMP polling loop: {e}", exc_info=True)
        finally:
            if 'db' in locals():
                db.close()
                
        # Wait 5 minutes (300 seconds) before the next cycle
        logger.info("Sleeping for 5 minutes...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_snmp_polling_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
