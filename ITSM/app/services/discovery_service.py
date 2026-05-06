import time
import json
import logging
from datetime import datetime
import subprocess
import socket
import ipaddress
import platform
import concurrent.futures

# Attempt to import pysnmp
try:
    from pysnmp.hlapi import *
    HAS_SNMP = True
except ImportError:
    HAS_SNMP = False

from app.db import SessionLocal
from app.models.network import DiscoveryJob, DiscoveredDevice, DiscoveryLog

logger = logging.getLogger(__name__)

COMMON_PORTS = [22, 80, 443, 135, 445, 3389, 161]

def ping_ip(ip: str) -> bool:
    """Returns True if host responds to a ping request."""
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
    # Windows timeout is ms, Linux is s
    timeout_val = '1000' if platform.system().lower() == 'windows' else '1'
    
    # Building the command. Ex: "ping -c 1 -W 1 google.com"
    command = ['ping', param, '1', timeout_param, timeout_val, ip]
    
    try:
        # Popen is safer, but subprocess.call is simpler for just return code
        # Redirecting stdout and stderr to DEVNULL to keep console clean
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except Exception:
        return False

def scan_ports(ip: str, ports: list) -> list:
    """Returns a list of open ports from the given list."""
    open_ports = []
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5) # Fast timeout for local network
        result = sock.connect_ex((ip, port))
        if result == 0:
            open_ports.append(port)
        sock.close()
    return open_ports

async def get_snmp_sysdescr(ip: str, community: str = 'public') -> tuple:
    """Fetches sysDescr, sysName, sysUpTime, and Serial via SNMPv2c. Returns (sysDescr, sysName, snmp_status, snmp_error, uptime, serial_number)."""
    if not HAS_SNMP:
        return None, None, "NOT_ATTEMPTED", "PySNMP library not installed", None, None
        
    try:
        from pysnmp.hlapi.v3arch.asyncio import get_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        
        engine = SnmpEngine()
        try:
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                    engine,
                    CommunityData(community, mpModel=1), # mpModel=1 means SNMPv2c
                t,
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.1.0')), # sysDescr
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.5.0')), # sysName
                ObjectType(ObjectIdentity('1.3.6.1.2.1.1.3.0')), # sysUpTime
                ObjectType(ObjectIdentity('1.3.6.1.2.1.47.1.1.1.1.11.1')) # entPhysicalSerialNum.1 (Chassis)
            )
            
            if errorIndication:
                return None, None, "FAILED", f"Timeout or Network Error: {errorIndication}", None, None
                
            if errorStatus:
                return None, None, "FAILED", f"SNMP Error: {errorStatus.prettyPrint()}", None, None
                
            sys_descr = None
            sys_name = None
            uptime = None
            serial_number = None
            
            for name, val in varBinds:
                oid = str(name)
                if '1.3.6.1.2.1.1.1.0' in oid:
                    sys_descr = val.prettyPrint()
                elif '1.3.6.1.2.1.1.5.0' in oid:
                    sys_name = val.prettyPrint()
                elif '1.3.6.1.2.1.1.3.0' in oid:
                    # sysUpTime is in hundredths of a second
                    try:
                        ticks = int(val)
                        seconds = ticks / 100.0
                        days = int(seconds // 86400)
                        hours = int((seconds % 86400) // 3600)
                        minutes = int((seconds % 3600) // 60)
                        uptime = f"{days}d {hours}h {minutes}m"
                    except:
                        pass
                        
            return sys_descr, sys_name, "CONNECTED", None, uptime, serial_number
        finally:
            engine.transportDispatcher.closeDispatcher()
            
    except Exception as e:
        logger.warning(f"SNMP error for {ip}: {e}")
        return None, None, "FAILED", f"Exception: {str(e)}", None, None

async def get_snmp_mac_and_serial(ip: str, community: str = 'public') -> tuple:
    if not HAS_SNMP:
        return None, None
        
    try:
        from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        
        engine = SnmpEngine()
        try:
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            mac = None
            serial = None
            
            # Fetch Serial
            async for err, st, idx, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 10, ObjectType(ObjectIdentity('1.3.6.1.2.1.47.1.1.1.1.11')), lexicographicMode=False
            ):
                if err or st: break
                for name, val in varBinds:
                    p = val.prettyPrint()
                    if p and len(p) > 4:
                        serial = p
                        break
                if serial: break
            
            # Fetch MAC
            async for err, st, idx, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 10, ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.6')), lexicographicMode=False
            ):
                if err or st: break
                for name, val in varBinds:
                    p = val.prettyPrint()
                    if p.startswith('0x') and len(p) == 14:
                        # Format 0x3462884fb0c0 -> 34:62:88:4f:b0:c0
                        raw = p[2:]
                        mac = ':'.join([raw[i:i+2] for i in range(0, len(raw), 2)]).upper()
                        break
                if mac: break
                
            return mac, serial
        finally:
            engine.transportDispatcher.closeDispatcher()
            
    except Exception as e:
        logger.warning(f"SNMP mac/serial error for {ip}: {e}")
        return None, None

def get_mac_address(ip: str) -> str:
    """Attempt to find MAC address from ARP cache for a given IP."""
    try:
        if platform.system().lower() == 'windows':
            output = subprocess.check_output(['arp', '-a', ip]).decode('utf-8')
            for line in output.split('\n'):
                if ip in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1].replace('-', ':').upper()
        else:
            output = subprocess.check_output(['arp', '-n', ip]).decode('utf-8')
            for line in output.split('\n'):
                if ip in line and 'ether' in line:
                    parts = line.split()
                    for p in parts:
                        if ':' in p and len(p) == 17:
                            return p.upper()
    except Exception:
        pass
    return None



async def resolve_hostnames_from_ips(ip_list: list) -> dict:
    """Batch reverse DNS lookup. Returns dict[ip] = hostname.
    
    Runs lookups in a thread pool to avoid blocking the event loop.
    Times out individual lookups after 1 second.
    """
    import asyncio
    
    results = {}
    if not ip_list:
        return results
    
    # Deduplicate
    unique_ips = list(set(ip_list))
    
    def _resolve_one(target_ip):
        try:
            hostname, _, _ = socket.gethostbyaddr(target_ip)
            # Strip domain suffix for cleaner display
            short = hostname.split('.')[0] if hostname else ''
            return target_ip, short if short else hostname
        except (socket.herror, socket.gaierror, OSError):
            return target_ip, None
    
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        tasks = [loop.run_in_executor(pool, _resolve_one, ip) for ip in unique_ips[:100]]  # Cap at 100 lookups
        done = await asyncio.gather(*tasks, return_exceptions=True)
    
    for item in done:
        if isinstance(item, tuple) and item[1]:
            results[item[0]] = item[1]
    
    return results


async def analyze_device(ip: str, use_icmp: bool, use_snmp: bool, community: str) -> dict:
    """Scans the IP and determines its properties."""
    # 1. Ping
    is_alive = False
    if use_icmp:
        is_alive = ping_ip(ip)
    else:
        # If ICMP is disabled, we rely on ports
        pass
        
    # 2. Ports
    open_ports = []
    # Even if ICMP fails, some hosts block ping but allow TCP. We'll scan ports if it's alive OR if we force scan
    # To optimize, we only scan ports if ping responds, unless ICMP is turned off in config
    if is_alive or not use_icmp:
        open_ports = scan_ports(ip, COMMON_PORTS)
        if open_ports:
            is_alive = True
            
    # 3. SNMP
    sys_descr, sys_name = None, None
    uptime, serial_number = None, None
    snmp_status = "NOT_ATTEMPTED"
    snmp_error = None
    mac_address = None
    
    if use_snmp:
        sys_descr, sys_name, snmp_status, snmp_error, uptime, serial_number = await get_snmp_sysdescr(ip, community)
        if snmp_status == "CONNECTED":
            is_alive = True
            snmp_mac, snmp_serial = await get_snmp_mac_and_serial(ip, community)
            if snmp_serial and not serial_number:
                serial_number = snmp_serial
            if snmp_mac:
                mac_address = snmp_mac
            
    if not is_alive:
        return None # Device is down or not answering
        
    if not mac_address:
        mac_address = get_mac_address(ip)
        
    hostname = sys_name if sys_name else f"HOST-{ip.replace('.', '-')}"
        
    # 4. Fingerprint
    device_type = "Unknown"
    vendor = "Unknown"
    os_info = "Unknown"
    
    if sys_descr:
        desc_lower = sys_descr.lower()
        if "cisco" in desc_lower:
            vendor = "Cisco"
            device_type = "Switch" if "switch" in desc_lower or "ios" in desc_lower else "Router"
            os_info = "Cisco IOS"
        elif "windows" in desc_lower:
            vendor = "Microsoft"
            device_type = "Server" if "server" in desc_lower else "PC"
            os_info = "Windows"
        elif "linux" in desc_lower:
            vendor = "Linux"
            device_type = "Server"
            os_info = "Linux"
        elif "hp" in desc_lower or "jetdirect" in desc_lower or "printer" in desc_lower:
            vendor = "HP"
            device_type = "Printer"
            os_info = "Printer Firmware"
    else:
        # Fallback to port fingerprinting
        if 3389 in open_ports or 135 in open_ports or 445 in open_ports:
            vendor = "Microsoft"
            device_type = "PC"
            os_info = "Windows"
        elif 22 in open_ports and not (135 in open_ports or 3389 in open_ports):
            vendor = "Unknown"
            device_type = "Server"
            os_info = "Linux/Unix"
            
    return {
        "ip_address": ip,
        "is_alive": is_alive,
        "hostname": hostname,
        "vendor": vendor,
        "device_type": device_type,
        "os_info": os_info,
        "mac_address": mac_address,
        "serial_number": serial_number,
        "snmp_status": snmp_status,
        "snmp_error": snmp_error,
        "uptime": uptime,
        "open_ports": open_ports
    }


def run_discovery_job(job_id: int):
    """
    Background task to run a real discovery job.
    """
    db = SessionLocal()
    try:
        job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
        if not job:
            return
            
        logger.info(f"Starting Discovery Job {job.name} (ID: {job.id})")
        
        # Create a log entry
        log = DiscoveryLog(
            job_id=job.id,
            status="RUNNING"
        )
        db.add(log)
        db.commit()
        
        target_val = job.target_value.strip()
        protocols_raw = job.protocols or ""
        protocols_upper = protocols_raw.upper()
        
        use_icmp = "ICMP" in protocols_upper
        use_snmp = "SNMP" in protocols_upper
        
        # Parse community from job if we store it in protocols.
        # Format hack: if protocols contains "COMMUNITY:xxx", parse it out.
        snmp_community = None
        for proto in protocols_raw.split(','):
            proto_clean = proto.strip()
            if proto_clean.upper().startswith("COMMUNITY:"):
                # Extract the exact string after COMMUNITY: (preserve case)
                snmp_community = proto_clean[10:].strip()
                break
                
        # If no specific community was provided in the job, fallback to global settings
        if not snmp_community:
            from app.models.settings import SystemSetting
            global_community_setting = db.query(SystemSetting).filter(SystemSetting.setting_key == 'snmp_community').first()
            snmp_community = global_community_setting.setting_value if global_community_setting else "public"
        # Determine IPs to scan
        ips_to_scan = []
        try:
            if "/" in target_val:
                # Subnet
                network = ipaddress.ip_network(target_val, strict=False)
                ips_to_scan = [str(ip) for ip in network.hosts()]
            elif "-" in target_val:
                # Range: 192.168.1.1-192.168.1.10
                start_ip, end_ip = target_val.split("-")
                start = int(ipaddress.IPv4Address(start_ip.strip()))
                end = int(ipaddress.IPv4Address(end_ip.strip()))
                ips_to_scan = [str(ipaddress.IPv4Address(i)) for i in range(start, end + 1)]
            else:
                # Single IP
                ips_to_scan = [str(ipaddress.IPv4Address(target_val))]
        except Exception as e:
            raise ValueError(f"Invalid target format: {e}")
            
        logger.info(f"Scanning {len(ips_to_scan)} IP addresses...")
        
        found_devices = 0
        output_lines = []
        
        def scan_worker(ip):
            import asyncio
            return asyncio.run(analyze_device(ip, use_icmp, use_snmp, snmp_community))
            
        # Use ThreadPoolExecutor for fast scanning, limited to 15 to prevent FD exhaustion (Windows select() limit is 512)
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            future_to_ip = {executor.submit(scan_worker, ip): ip for ip in ips_to_scan}
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        # Database write per found device
                        existing = db.query(DiscoveredDevice).filter(DiscoveredDevice.ip_address == result["ip_address"]).first()
                        if not existing:
                            new_device = DiscoveredDevice(
                                hostname=result["hostname"],
                                ip_address=result["ip_address"],
                                mac_address=result["mac_address"],
                                device_type=result["device_type"],
                                vendor=result["vendor"],
                                os_info=result["os_info"],
                                open_ports=json.dumps(result["open_ports"]),
                                status="NEW",
                                discovery_source=protocols_raw,
                                snmp_status=result["snmp_status"],
                                snmp_error=result["snmp_error"],
                                serial_number=result.get("serial_number"),
                                uptime=result.get("uptime")
                            )
                            db.add(new_device)
                            found_devices += 1
                            output_lines.append(f"Discovered new device: {result['ip_address']} ({result['device_type']})")
                        else:
                            # Update existing
                            existing.last_seen = datetime.utcnow()
                            if result["hostname"] and "HOST-" not in result["hostname"]:
                                existing.hostname = result["hostname"]
                            if result["mac_address"]:
                                existing.mac_address = result["mac_address"]
                            if result["device_type"] != "Unknown":
                                existing.device_type = result["device_type"]
                            if result["vendor"] != "Unknown":
                                existing.vendor = result["vendor"]
                            existing.open_ports = json.dumps(result["open_ports"])
                            existing.snmp_status = result["snmp_status"]
                            existing.snmp_error = result["snmp_error"]
                            existing.discovery_source = protocols_raw
                            if result.get("serial_number"):
                                existing.serial_number = result.get("serial_number")
                            if result.get("uptime"):
                                existing.uptime = result.get("uptime")
                            
                            output_lines.append(f"Updated existing device: {result['ip_address']}")
                        
                        db.commit()
                except Exception as exc:
                    logger.error(f"{ip} generated an exception: {exc}")
                    db.rollback()
            
        # Complete job
        job.status = "IDLE"
        job.last_run = datetime.utcnow()
        
        log.end_time = datetime.utcnow()
        log.status = "SUCCESS"
        log.devices_found = found_devices
        log.log_output = "\n".join(output_lines)
        
        db.commit()
        logger.info(f"Discovery Job {job.id} completed. Found {found_devices} devices.")
        
    except Exception as e:
        logger.error(f"Error running discovery job: {e}")
        db.rollback()
        
        # Attempt to mark as failed
        try:
            job = db.query(DiscoveryJob).filter(DiscoveryJob.id == job_id).first()
            if job:
                job.status = "FAILED"
                # Update log
                log = db.query(DiscoveryLog).filter(DiscoveryLog.job_id == job_id, DiscoveryLog.status == "RUNNING").first()
                if log:
                    log.status = "ERROR"
                    log.log_output = str(e)
                db.commit()
        except:
            pass
    finally:
        db.close()

async def run_auto_discovery():
    """
    Background routine to automatically sweep configured subnets using ICMP and SNMP.
    Reads target subnets and enabled status dynamically from system settings.
    """
    import asyncio
    import ipaddress
    import concurrent.futures
    import json
    from datetime import datetime
    from app.db import SessionLocal
    from app.models.network import DiscoveredDevice
    from app.models.settings import SystemSetting
    
    logger.info("=== run_auto_discovery() CALLED ===")
    db = SessionLocal()
    try:
        auto_scan_enabled = db.query(SystemSetting).filter_by(setting_key="auto_discovery_enabled").first()
        if auto_scan_enabled and auto_scan_enabled.setting_value != "true":
            logger.info("Auto-discovery is disabled in global settings. Skipping.")
            return

        subnets_setting = db.query(SystemSetting).filter_by(setting_key="auto_discovery_subnets").first()
        if not subnets_setting or not subnets_setting.setting_value:
            logger.warning("No discovery subnets configured in global settings. Skipping auto-discovery.")
            return
            
        subnets_list = [s.strip() for s in subnets_setting.setting_value.split(',') if s.strip()]
        
        snmp_community_setting = db.query(SystemSetting).filter_by(setting_key="snmp_community").first()
        community = snmp_community_setting.setting_value if snmp_community_setting else "public"

        for subnet_str in subnets_list:
            logger.info(f"Sweeping subnet: {subnet_str}")
            try:
                network = ipaddress.ip_network(subnet_str, strict=False)
                ips = [str(ip) for ip in network.hosts()]
                
                def scan_worker(ip):
                    import asyncio
                    return asyncio.run(analyze_device(ip, use_icmp=True, use_snmp=True, community=community))
                
                # Split into chunks
                for i in range(0, len(ips), 50):
                    batch = ips[i:i+50]
                    loop = asyncio.get_event_loop()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                        tasks = [loop.run_in_executor(executor, scan_worker, ip) for ip in batch]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                    for res in results:
                        if isinstance(res, dict) and res.get('is_alive'):
                            device = db.query(DiscoveredDevice).filter_by(ip_address=res['ip']).first()
                            if not device:
                                device = DiscoveredDevice(ip_address=res['ip'])
                                db.add(device)
                            
                            device.hostname = res.get('hostname')
                            device.mac_address = res.get('mac')
                            device.vendor = res.get('vendor')
                            device.device_type = res.get('device_type')
                            device.os_info = res.get('os_info')
                            device.serial_number = res.get('serial')
                            device.last_seen = datetime.utcnow()
                            device.is_active = True
                            
                    db.commit()
                    
            except Exception as e:
                logger.error(f"Error sweeping subnet {subnet_str}: {e}")

    finally:
        db.close()
        logger.info("=== run_auto_discovery() COMPLETED ===")
