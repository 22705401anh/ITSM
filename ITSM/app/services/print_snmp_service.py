"""
KOSTAL Print Management — SNMP Polling Service
Polls network printers for online status, toner levels, and page counters.
Generates PrintAlert incidents if printers are offline or have low toner.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
import asyncio
from pysnmp.hlapi.asyncio import *

from app.models.print_management import PrintPrinter, PrintAlert

logger = logging.getLogger(__name__)

# Standard Printer MIB OIDs (RFC 3805)
OID_STATUS = "1.3.6.1.2.1.25.3.2.1.5.1"  # hrDeviceStatus
OID_ERROR_STATE = "1.3.6.1.2.1.25.3.5.1.1.1"  # hrPrinterDetectedErrorState
OID_LIFE_COUNT = "1.3.6.1.2.1.43.10.2.1.4.1.1"  # prtMarkerLifeCount (total pages)

# Supply tables
OID_SUPPLY_DESC = "1.3.6.1.2.1.43.11.1.1.6.1"  # prtMarkerSuppliesDescription
OID_SUPPLY_MAX = "1.3.6.1.2.1.43.11.1.1.8.1"   # prtMarkerSuppliesMaxCapacity
OID_SUPPLY_CUR = "1.3.6.1.2.1.43.11.1.1.9.1"   # prtMarkerSuppliesLevel

class PrintSNMPService:
    def __init__(self, db: Session):
        self.db = db
        self.snmp_engine = SnmpEngine()
        
    async def _get_snmp_values(self, ip: str, community: str, oids: list, timeout: int = 3, retries: int = 1):
        """Helper to fetch SNMP values using pysnmp."""
        results = {}
        errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
            self.snmp_engine,
            CommunityData(community, mpModel=1),  # SNMPv2c
            UdpTransportTarget((ip, 161), timeout=timeout, retries=retries),
            ContextData(),
            *[ObjectType(ObjectIdentity(oid)) for oid in oids]
        )
        if errorIndication:
            raise Exception(str(errorIndication))
        elif errorStatus:
            raise Exception(f"{errorStatus.prettyPrint()} at {errorIndex}")
        else:
            for varBind in varBinds:
                oid_str = str(varBind[0])
                val = varBind[1]
                if val.isSameTypeWith(Integer()):
                    results[oid_str] = int(val)
                else:
                    results[oid_str] = str(val)
        return results

    async def _walk_snmp_table(self, ip: str, community: str, base_oid: str, timeout: int = 3, retries: int = 1):
        """Helper to walk an SNMP table (e.g. supplies) to get all rows."""
        results = {}
        try:
            # We use nextCmd for walking
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                self.snmp_engine,
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, 161), timeout=timeout, retries=retries),
                ContextData(),
                ContextData(),
                ObjectType(ObjectIdentity(base_oid)),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for varBind in varBinds:
                    oid_str = str(varBind[0])
                    val = varBind[1]
                    idx = oid_str.split('.')[-1]
                    if val.isSameTypeWith(Integer()):
                        results[idx] = int(val)
                    else:
                        results[idx] = str(val).strip().lower()
        except Exception:
            pass
        return results

    async def poll_printer(self, printer: PrintPrinter):
        """Poll a single printer and update its database record."""
        ip = printer.ip_address
        comm = printer.snmp_community or "public"
        
        try:
            # 1. Base Status & Life Count
            oids_to_fetch = [OID_STATUS, OID_LIFE_COUNT]
            base_data = await self._get_snmp_values(ip, comm, oids_to_fetch)
            
            status_code = base_data.get(OID_STATUS)
            life_count = base_data.get(OID_LIFE_COUNT)
            
            # 2. Toner Levels
            # We walk the description, max, and current tables and map by index
            desc_table = await self._walk_snmp_table(ip, comm, OID_SUPPLY_DESC)
            max_table = await self._walk_snmp_table(ip, comm, OID_SUPPLY_MAX)
            cur_table = await self._walk_snmp_table(ip, comm, OID_SUPPLY_CUR)
            
            toner_levels = {}
            for idx, desc in desc_table.items():
                if idx in max_table and idx in cur_table:
                    max_cap = max_table[idx]
                    cur_cap = cur_table[idx]
                    if max_cap > 0 and cur_cap >= 0:
                        pct = int((cur_cap / max_cap) * 100)
                        if "black" in desc or "blk" in desc or "k" in desc: toner_levels["black"] = pct
                        elif "cyan" in desc or "c" in desc: toner_levels["cyan"] = pct
                        elif "magenta" in desc or "m" in desc: toner_levels["magenta"] = pct
                        elif "yellow" in desc or "y" in desc: toner_levels["yellow"] = pct

            # Map Status
            status_map = {1: "unknown", 2: "offline", 3: "idle", 4: "printing", 5: "warmup"}
            mapped_status = status_map.get(status_code, "online")
            
            # Database Update
            printer.status = "online" if mapped_status in ["idle", "printing", "warmup"] else mapped_status
            
            if life_count is not None and life_count > 0:
                if printer.hardware_validation_enabled and printer.total_page_counter and life_count > printer.total_page_counter:
                    hardware_delta = life_count - printer.total_page_counter
                    
                    from app.models.print_management import PrintJob
                    
                    time_window_start = printer.last_seen if printer.last_seen else datetime.utcnow() - timedelta(days=1)
                    
                    jobs = self.db.query(PrintJob).filter(
                        PrintJob.printer_name == printer.name,
                        PrintJob.submitted_at >= time_window_start,
                        PrintJob.status == "printed"
                    ).all()
                    
                    spooler_delta = sum([j.total_pages or 0 for j in jobs])
                    
                    # Tolerance of 2 pages for blank/separator sheets
                    if hardware_delta > (spooler_delta + 2):
                        untracked = hardware_delta - spooler_delta
                        self._create_alert(
                            printer.id, "page_count_mismatch", "warning", 
                            f"Hardware page count anomaly: {untracked} untracked pages printed directly on {printer.name} (Delta: {hardware_delta}, Spooler: {spooler_delta})."
                        )
                    else:
                        self._resolve_alert(printer.id, "page_count_mismatch")
                        
                    for j in jobs:
                        j.validation_status = "validated"
                        j.validated_pages = j.total_pages
                
                printer.total_page_counter = life_count

            printer.last_seen = datetime.utcnow()
            
            if "black" in toner_levels: printer.toner_black = toner_levels["black"]
            if "cyan" in toner_levels: printer.toner_cyan = toner_levels["cyan"]
            if "magenta" in toner_levels: printer.toner_magenta = toner_levels["magenta"]
            if "yellow" in toner_levels: printer.toner_yellow = toner_levels["yellow"]
            
            # Resolve any active offline alerts
            self._resolve_alert(printer.id, "offline")
            
            # Check for low toner (< 10%)
            for color, level in toner_levels.items():
                if level <= 10:
                    self._create_alert(
                        printer.id, "low_toner", "warning", 
                        f"Low {color} toner: {level}% remaining on printer {printer.name} ({printer.ip_address})"
                    )
                else:
                    # Resolve if it was previously low but is now > 10% (e.g. replaced)
                    # We might need to map colors specifically if we want to resolve individually, 
                    # but for simplicity, we resolve all low_toner if all > 10%.
                    pass
            
            # If all toners > 10%, resolve low_toner alert
            if all(level > 10 for level in toner_levels.values()):
                self._resolve_alert(printer.id, "low_toner")

            logger.info(f"SNMP Polled {printer.name} ({ip}): Status={printer.status}, Pages={life_count}")

        except Exception as e:
            # SNMP failure = offline
            printer.status = "offline"
            self._create_alert(
                printer.id, "offline", "warning", 
                f"Printer {printer.name} ({ip}) is offline or unreachable via SNMP."
            )
            logger.warning(f"Failed to poll printer {printer.name} ({ip}): {e}")

    def _create_alert(self, printer_id: int, alert_type: str, severity: str, message: str):
        """Create a new alert if one doesn't exist, or update the last_detected time if it does."""
        existing = self.db.query(PrintAlert).filter(
            PrintAlert.printer_id == printer_id,
            PrintAlert.alert_type == alert_type,
            PrintAlert.status == "open"
        ).first()
        
        if existing:
            existing.last_detected = datetime.utcnow()
        else:
            alert = PrintAlert(
                printer_id=printer_id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                status="open"
            )
            self.db.add(alert)

    def _resolve_alert(self, printer_id: int, alert_type: str):
        """Resolve an open alert."""
        alerts = self.db.query(PrintAlert).filter(
            PrintAlert.printer_id == printer_id,
            PrintAlert.alert_type == alert_type,
            PrintAlert.status == "open"
        ).all()
        for alert in alerts:
            alert.status = "resolved"
            alert.resolved_at = datetime.utcnow()

    async def poll_all_enabled_printers(self):
        """Poll all printers that have SNMP enabled."""
        printers = self.db.query(PrintPrinter).filter(
            PrintPrinter.snmp_enabled == True,
            PrintPrinter.ip_address != None
        ).all()
        
        if not printers:
            logger.info("No SNMP-enabled printers found to poll.")
            return

        logger.info(f"Starting SNMP polling for {len(printers)} printers...")
        
        # Concurrency: chunk into batches of 10 to avoid blasting the network
        chunk_size = 10
        for i in range(0, len(printers), chunk_size):
            chunk = printers[i:i+chunk_size]
            tasks = [self.poll_printer(p) for p in chunk]
            await asyncio.gather(*tasks)
            self.db.commit()
            
        # Run hardware validation on recent jobs
        self.validate_completed_jobs()
            
        logger.info("SNMP polling cycle completed.")

    def validate_completed_jobs(self):
        """Hardware page validation: check recent completed jobs and verify against printer state."""
        from app.models.print_management import PrintJob
        from datetime import datetime, timedelta
        
        # Find jobs completed recently that haven't been validated yet
        recent = datetime.utcnow() - timedelta(hours=1)
        jobs = self.db.query(PrintJob).filter(
            PrintJob.status == "printed",
            PrintJob.validation_status == None,
            PrintJob.completed_at >= recent
        ).all()
        
        count = 0
        for job in jobs:
            # We check if the printer is online and has SNMP enabled.
            # In a full implementation, we'd compare exact pre/post page counters.
            # Here we do a simplified validation: if the printer is online and healthy, we verify it.
            printer = self.db.query(PrintPrinter).filter(PrintPrinter.name == job.printer_name).first()
            if printer and printer.snmp_enabled:
                if printer.status == "online":
                    job.validation_status = "verified"
                    job.validated_pages = job.total_pages
                    job.validated_cost = job.estimated_cost
                else:
                    job.validation_status = "unverified"
            else:
                job.validation_status = "not_supported"
            count += 1
            
        if count > 0:
            self.db.commit()
            logger.info(f"Hardware validation completed for {count} recent jobs.")
