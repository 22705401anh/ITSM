import time
import json
import logging
from datetime import datetime
import asyncio
import socket

try:
    from pysnmp.hlapi.v3arch.asyncio import *
    HAS_SNMP = True
except ImportError:
    HAS_SNMP = False

from app.db import SessionLocal
from app.models.network import DiscoveredDevice, DeviceTelemetry

logger = logging.getLogger(__name__)


_global_snmp_engine = None

def _get_snmp_engine():
    global _global_snmp_engine
    if _global_snmp_engine is None:
        from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
        _global_snmp_engine = SnmpEngine()
    return _global_snmp_engine

async def get_arp_table(ip: str, community: str = 'public') -> dict:
    """Fetches the ARP table (MAC to IP mapping) from an L3 switch via SNMP."""
    if not HAS_SNMP:
        return {}
        
    eng = _get_snmp_engine()
    try:
        from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        t = await UdpTransportTarget.create((ip, 161), timeout=3.0, retries=2)
        arp_table = {}
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            eng, CommunityData(community, mpModel=1), t, ContextData(),
            0, 50, ObjectType(ObjectIdentity('1.3.6.1.2.1.4.22.1.2')),
            lexicographicMode=False
        ):
            if errorIndication or errorStatus:
                break
            for name, val in varBinds:
                parts = str(name).split('.')
                resolved_ip = '.'.join(parts[-4:])
                try:
                    mac = ':'.join([f"{b:02x}" for b in val.asOctets()]).lower()
                    if mac and len(mac) == 17 and resolved_ip:
                        arp_table[mac] = resolved_ip
                except Exception:
                    pass
        
        logger.info(f"ARP table from {ip}: {len(arp_table)} entries")
        return arp_table
    except Exception as e:
        logger.warning(f"SNMP ARP table error for {ip}: {e}")
        return {}

async def get_cdp_neighbors(ip: str, community: str = 'public') -> list:
    """Lightweight function to just fetch CDP neighbors for topology mapping."""
    if not HAS_SNMP:
        return []
        
    eng = _get_snmp_engine()
    try:
        from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        import asyncio
        t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=1)
        neighbors = []
        
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            eng, CommunityData(community, mpModel=1), t, ContextData(),
            0, 50, ObjectType(ObjectIdentity('1.3.6.1.4.1.9.9.23.1.2.1.1.4')),
            lexicographicMode=False
        ):
            if errorIndication or errorStatus:
                break
            for name, val in varBinds:
                ip_hex = val.asOctets().hex()
                if len(ip_hex) == 8:
                    neighbor_ip = '.'.join([str(int(ip_hex[i:i+2], 16)) for i in range(0, 8, 2)])
                    neighbors.append(neighbor_ip)
                    
        return list(set(neighbors))
    except Exception as e:
        logger.warning(f"SNMP CDP topology error for {ip}: {e}")
        return {}

async def get_switch_ports(ip: str, community: str = 'public') -> list:
    """Fetches switch ports details via SNMPv2c."""
    if not HAS_SNMP:
        return []
        
    try:
        from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        engine = _get_snmp_engine()
        
        async def fetch_column(oid_str):
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            results = {}
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 50, ObjectType(ObjectIdentity(oid_str)),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for name, val in varBinds:
                    oid_parts = str(name).split('.')
                    index = oid_parts[-1]
                    results[index] = val.prettyPrint()
            return results

        async def fetch_cdp(oid_str, is_ip=False, is_cap=False):
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            results = {}
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 50, ObjectType(ObjectIdentity(oid_str)),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for name, val in varBinds:
                    oid_parts = str(name).split('.')
                    ifIndex = oid_parts[-2] # For CDP, ifIndex is second to last
                    if is_ip:
                        ip_hex = val.asOctets().hex()
                        if len(ip_hex) == 8:
                            val_str = '.'.join([str(int(ip_hex[i:i+2], 16)) for i in range(0, 8, 2)])
                        else:
                            val_str = val.prettyPrint()
                    elif is_cap:
                        cap_hex = val.asOctets().hex()
                        if len(cap_hex) >= 2:
                            cap_int = int(cap_hex[:2], 16)
                            caps = []
                            if cap_int & 0x01: caps.append('Router')
                            if cap_int & 0x02: caps.append('Trans-Bridge')
                            if cap_int & 0x04: caps.append('Source-Route-Bridge')
                            if cap_int & 0x08: caps.append('Switch')
                            if cap_int & 0x10: caps.append('Host')
                            if cap_int & 0x20: caps.append('IGMP')
                            if cap_int & 0x40: caps.append('Repeater')
                            val_str = ', '.join(caps) if caps else val.prettyPrint()
                        else:
                            val_str = val.prettyPrint()
                    else:
                        val_str = val.prettyPrint()
                    results[ifIndex] = val_str
            return results

        async def fetch_cam_data():
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            auth = CommunityData(community, mpModel=1)
            vlans = []
            
            # Fetch VLANs
            async for err, st, idx, varBinds in bulk_walk_cmd(
                engine, auth, t, ContextData(),
                0, 50, ObjectType(ObjectIdentity('1.3.6.1.4.1.9.9.46.1.3.1.1.2')),
                lexicographicMode=False
            ):
                if err or st: break
                for name, val in varBinds:
                    vlan_id = str(name).split('.')[-1]
                    if vlan_id not in ['1002', '1003', '1004', '1005']:
                        vlans.append(vlan_id)
            
            ifindex_to_macs = {}
            sem = asyncio.Semaphore(5) # Limit concurrency to 5 VLANs at a time
            
            async def fetch_cam_vlan(vlan):
                async with sem:
                    v_auth = CommunityData(f"{community}@{vlan}", mpModel=1)
                    
                    # Fetch dot1dBasePort -> ifIndex for THIS vlan
                    v_port_to_ifindex = {}
                    async for err, st, idx, varBinds in bulk_walk_cmd(
                        engine, v_auth, t, ContextData(),
                        0, 50, ObjectType(ObjectIdentity('1.3.6.1.2.1.17.1.4.1.2')),
                        lexicographicMode=False
                    ):
                        if err or st: break
                        for name, val in varBinds:
                            v_port_to_ifindex[str(name).split('.')[-1]] = str(val)

                    async for err, st, idx, varBinds in bulk_walk_cmd(
                        engine, v_auth, t, ContextData(),
                        0, 50, ObjectType(ObjectIdentity('1.3.6.1.2.1.17.4.3.1.2')),
                        lexicographicMode=False
                    ):
                        if err or st: break
                        for name, val in varBinds:
                            mac = ':'.join([f"{int(x):02x}" for x in str(name).split('.')[-6:]]).lower()
                            ifidx = v_port_to_ifindex.get(str(val), str(val))
                            if ifidx not in ifindex_to_macs:
                                ifindex_to_macs[ifidx] = []
                            ifindex_to_macs[ifidx].append(mac)
                        
            if vlans:
                await asyncio.gather(*(fetch_cam_vlan(v) for v in vlans))
            return ifindex_to_macs

        # Primary: Cisco vmVlan (CISCO-VLAN-MEMBERSHIP-MIB) — indexed directly by ifIndex
        # Much more reliable on Cisco IOS/Catalyst than Q-BRIDGE-MIB dot1qPvid
        async def fetch_vmvlan():
            """Returns {ifIndex_str: vlan_id_str} via Cisco vmVlan OID."""
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)
            vlan_map = {}
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 50, ObjectType(ObjectIdentity('1.3.6.1.4.1.9.9.68.1.2.2.1.2')),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for name, val in varBinds:
                    ifidx = str(name).split('.')[-1]
                    v = str(val)
                    if v and v != '0':
                        vlan_map[ifidx] = v
            return vlan_map

        # Fallback: dot1qPvid (Q-BRIDGE-MIB) — indexed by bridge port, needs mapping
        async def fetch_pvid_with_mapping():
            """Returns {ifIndex_str: vlan_id_str} via dot1qPvid + bridge port map."""
            t = await UdpTransportTarget.create((ip, 161), timeout=2.0, retries=2)

            # Step 1: dot1dBasePortIfIndex — bridge port → ifIndex
            bp_to_ifidx = {}
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 50, ObjectType(ObjectIdentity('1.3.6.1.2.1.17.1.4.1.2')),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for name, val in varBinds:
                    bp_to_ifidx[str(name).split('.')[-1]] = str(val)

            # Step 2: dot1qPvid — bridge port → PVID
            pvid_map = {}
            async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                engine, CommunityData(community, mpModel=1), t, ContextData(),
                0, 50, ObjectType(ObjectIdentity('1.3.6.1.2.1.17.7.1.4.5.1.1')),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for name, val in varBinds:
                    bp = str(name).split('.')[-1]
                    ifidx = bp_to_ifidx.get(bp)
                    if ifidx:
                        v = str(val)
                        if v and v != '0':
                            pvid_map[ifidx] = v
            return pvid_map

        # Run column fetches with strict concurrency limit to prevent CoPP packet drops
        col_sem = asyncio.Semaphore(3)
        async def run_col(coro):
            async with col_sem:
                return await coro

        results = await asyncio.gather(
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.2')), # ifDescr
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.5')), # ifSpeed
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.6')), # ifPhysAddress
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.7')), # ifAdminStatus
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.8')), # ifOperStatus
            run_col(fetch_column('1.3.6.1.2.1.31.1.1.1.18')), # ifAlias
            run_col(fetch_cdp('1.3.6.1.4.1.9.9.23.1.2.1.1.4', is_ip=True)), # CDP IP
            run_col(fetch_cdp('1.3.6.1.4.1.9.9.23.1.2.1.1.6', is_ip=False)), # CDP Name
            run_col(fetch_cdp('1.3.6.1.4.1.9.9.23.1.2.1.1.9', is_ip=False, is_cap=True)), # CDP Capabilities
            run_col(fetch_cam_data()),          # CAM Table MACs
            run_col(fetch_vmvlan()),            # Primary: Cisco vmVlan
            run_col(fetch_pvid_with_mapping()), # Fallback: Q-BRIDGE dot1qPvid
            run_col(fetch_column('1.3.6.1.2.1.31.1.1.1.6')),  # ifHCInOctets
            run_col(fetch_column('1.3.6.1.2.1.31.1.1.1.10')), # ifHCOutOctets
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.10')),    # ifInOctets
            run_col(fetch_column('1.3.6.1.2.1.2.2.1.16')),    # ifOutOctets
        )

        # Build ifIndex → vlan_id: prefer Cisco vmVlan, fall back to dot1qPvid
        cisco_vlan_map = results[10]   # {ifIndex: vlan_id}
        pvid_vlan_map  = results[11]   # {ifIndex: vlan_id}
        ifidx_to_vlan  = {**pvid_vlan_map, **cisco_vlan_map}  # Cisco takes priority

        hc_in = results[12]
        hc_out = results[13]
        in_octets = results[14]
        out_octets = results[15]

        merged = []
        for idx in results[0].keys():
            ib = hc_in.get(idx) or in_octets.get(idx) or '0'
            ob = hc_out.get(idx) or out_octets.get(idx) or '0'
            
            try:
                ib_val = int(ib)
                ob_val = int(ob)
            except:
                ib_val = 0
                ob_val = 0
                
            merged.append({
                'index': int(idx),
                'name': results[0].get(idx, ''),
                'speed': results[1].get(idx, ''),
                'mac': results[2].get(idx, ''),
                'admin_status': results[3].get(idx, ''),
                'oper_status': results[4].get(idx, ''),
                'alias': results[5].get(idx, ''),
                'neighbor_ip': results[6].get(idx, ''),
                'neighbor_name': results[7].get(idx, ''),
                'neighbor_caps': results[8].get(idx, ''),
                'macs_connected': results[9].get(idx, []),
                'vlan_id': ifidx_to_vlan.get(idx),
                'in_bytes': ib_val,
                'out_bytes': ob_val
            })
        
        merged.sort(key=lambda x: x['index'])
        return merged
        
    except Exception as e:
        logger.warning(f"SNMP get_switch_ports error for {ip}: {e}")
        return []


async def _snmp_walk(ip: str, community: str, oid: str, engine=None) -> dict:
    """Generic SNMP GETBULK walk helper. Returns {index: value_str}."""
    if not HAS_SNMP:
        return {}
    
    eng = engine or _get_snmp_engine()
    try:
        t = await UdpTransportTarget.create((ip, 161), timeout=3.0, retries=2)
        results = {}
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            eng, CommunityData(community, mpModel=1), t, ContextData(),
            0, 50, ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
        ):
            if errorIndication or errorStatus:
                break
            for name, val in varBinds:
                index = str(name).split('.')[-1]
                results[index] = val.prettyPrint()
        return results
    except Exception as e:
        logger.warning(f"SNMP walk error for {ip} at {oid}: {e}")
        return {}


async def _snmp_walk_full_index(ip: str, community: str, oid: str, engine=None) -> dict:
    """Generic SNMP GETBULK walk helper keeping full index after base OID."""
    if not HAS_SNMP:
        return {}
        
    eng = engine or _get_snmp_engine()
    try:
        t = await UdpTransportTarget.create((ip, 161), timeout=3.0, retries=2)
        results = {}
        async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
            eng, CommunityData(community, mpModel=1), t, ContextData(),
            0, 50, ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
        ):
            if errorIndication or errorStatus:
                break
            for name, val in varBinds:
                name_str = str(name)
                if name_str.startswith(oid):
                    index = name_str[len(oid):].lstrip('.')
                else:
                    index = name_str
                results[index] = val.prettyPrint()
        return results
    except Exception as e:
        logger.warning(f"SNMP full walk error for {ip} at {oid}: {e}")
        return {}


async def _snmp_get(ip: str, community: str, oids: list, engine=None) -> dict:
    """SNMP GET for specific OIDs. Returns {oid: value_str}."""
    if not HAS_SNMP:
        return {}
        
    try:
        from pysnmp.hlapi.v3arch.asyncio import get_cmd, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
        eng = engine or _get_snmp_engine()
        t = await UdpTransportTarget.create((ip, 161), timeout=3.0, retries=2)
        obj_types = [ObjectType(ObjectIdentity(o)) for o in oids]
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            eng, CommunityData(community, mpModel=1), t, ContextData(),
            *obj_types
        )
        if errorIndication or errorStatus:
            return {}
        results = {}
        for name, val in varBinds:
            results[str(name)] = val.prettyPrint()
        return results
    except Exception as e:
        logger.warning(f"SNMP get error for {ip}: {e}")
        return {}

async def get_device_summary(ip: str, community: str) -> dict:
    """Aggregated summary: sysDescr, sysName, sysUpTime, sysContact, sysLocation, serial, model."""
    import asyncio
    oids_get = [
        '1.3.6.1.2.1.1.1.0',   # sysDescr
        '1.3.6.1.2.1.1.3.0',   # sysUpTime
        '1.3.6.1.2.1.1.4.0',   # sysContact
        '1.3.6.1.2.1.1.5.0',   # sysName
        '1.3.6.1.2.1.1.6.0',   # sysLocation
        '1.3.6.1.2.1.47.1.1.1.1.11.1',  # entPhysicalSerialNum.1
        '1.3.6.1.2.1.47.1.1.1.1.13.1',  # entPhysicalModelName.1
    ]
    data = await _snmp_get(ip, community, oids_get)

    # Parse uptime
    uptime = '—'
    raw_up = data.get('1.3.6.1.2.1.1.3.0', '')
    if raw_up:
        try:
            ticks = int(raw_up)
            seconds = ticks / 100.0
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            uptime = f"{days}d {hours}h {minutes}m"
        except:
            uptime = raw_up

    return {
        'sys_descr': data.get('1.3.6.1.2.1.1.1.0', '—'),
        'sys_name': data.get('1.3.6.1.2.1.1.5.0', '—'),
        'sys_uptime': uptime,
        'sys_contact': data.get('1.3.6.1.2.1.1.4.0', '—'),
        'sys_location': data.get('1.3.6.1.2.1.1.6.0', '—'),
        'serial_number': data.get('1.3.6.1.2.1.47.1.1.1.1.11.1', '—'),
        'model': data.get('1.3.6.1.2.1.47.1.1.1.1.13.1', '—'),
    }

async def get_device_hardware_software(ip: str, community: str) -> dict:
    """Entity MIB chassis details: model, HW rev, SW rev, serial, description."""
    import asyncio

    engine = _get_snmp_engine()
    try:
        # Walk Entity MIB columns
        descr, model_name, hw_rev, sw_rev, serial, phys_class = await asyncio.gather(
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.2', engine),   # entPhysicalDescr
            _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.46.1.3.1.1.2', engine), # ... actually we should just let these use engine ...
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.13', engine),  # entPhysicalModelName
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.8', engine),   # entPhysicalHardwareRev
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.10', engine),  # entPhysicalSoftwareRev
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.11', engine),  # entPhysicalSerialNum
            _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.5', engine),   # entPhysicalClass
        )

        # Also fetch sysDescr for IOS version extraction
        sys_data = await _snmp_get(ip, community, ['1.3.6.1.2.1.1.1.0'], engine)
        sys_descr = sys_data.get('1.3.6.1.2.1.1.1.0', '')

        # Extract IOS version from sysDescr
        ios_version = '—'
        if sys_descr:
            import re
            ver_match = re.search(r'Version\s+([\w\.\(\)]+)', sys_descr)
            if ver_match:
                ios_version = ver_match.group(1)

        # Build entity table
        CLASS_MAP = {'1': 'Other', '2': 'Unknown', '3': 'Chassis', '4': 'Backplane',
                     '5': 'Container', '6': 'Power Supply', '7': 'Fan', '8': 'Sensor',
                     '9': 'Module', '10': 'Port', '11': 'Stack', '12': 'CPU'}

        entities = []
        for idx in descr:
            cls = phys_class.get(idx, '')
            cls_name = CLASS_MAP.get(cls, cls)
            entity = {
                'index': idx,
                'description': descr.get(idx, ''),
                'model': model_name.get(idx, ''),
                'hw_rev': hw_rev.get(idx, ''),
                'sw_rev': sw_rev.get(idx, ''),
                'serial': serial.get(idx, ''),
                'class': cls_name,
            }
            # Only include meaningful entries (chassis, module, stack)
            if cls in ('3', '9', '11') and entity['description']:
                entities.append(entity)

        # Chassis is typically index 1
        chassis = {
            'model': model_name.get('1', '—'),
            'description': descr.get('1', '—'),
            'hw_revision': hw_rev.get('1', '—'),
            'sw_revision': sw_rev.get('1', '—') or ios_version,
            'serial_number': serial.get('1', '—'),
            'ios_version': ios_version,
            'sys_descr': sys_descr,
        }

        return {
            'chassis': chassis,
            'entities': entities,
        }
    except Exception as e:
        logger.warning(f"SNMP hardware software error for {ip}: {e}")
        return {}

async def get_device_power(ip: str, community: str) -> dict:
    """Power supply status via CISCO-ENVMON-MIB and CISCO-ENTITY-FRU-CONTROL-MIB."""
    import asyncio

    # CISCO-ENVMON-MIB: ciscoEnvMonSupplyStatusTable
    psu_descr, psu_state = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.5.1.2'),  # ciscoEnvMonSupplyStatusDescr
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.5.1.3'),  # ciscoEnvMonSupplyState
    )

    # State mapping: 1=normal, 2=warning, 3=critical, 4=shutdown, 5=notPresent, 6=notFunctioning
    STATE_MAP = {'1': 'Normal', '2': 'Warning', '3': 'Critical', '4': 'Shutdown',
                 '5': 'Not Present', '6': 'Not Functioning'}

    supplies = []
    for idx in psu_descr:
        state_val = psu_state.get(idx, '0')
        supplies.append({
            'index': idx,
            'name': psu_descr.get(idx, f'PSU {idx}'),
            'state': STATE_MAP.get(state_val, f'Unknown ({state_val})'),
            'state_code': state_val,
            'ok': state_val == '1',
        })

    # Try CISCO-ENTITY-FRU-CONTROL for more detail (PoE budget)
    poe_available = {}
    poe_used = {}
    poe_remaining = {}
    try:
        poe_available = await _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.402.1.2.1.7')  # cpeExtPsePortPwrAvailable
        poe_used = await _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.402.1.2.1.8')       # cpeExtPsePortPwrConsumption
    except:
        pass

    # Inline PoE Budget from pethMainPseTable (standard)
    poe_budget = {}
    poe_consumption = {}
    try:
        poe_budget = await _snmp_walk(ip, community, '1.3.6.1.2.1.105.1.3.1.1.2')      # pethMainPsePower (watts)
        poe_consumption = await _snmp_walk(ip, community, '1.3.6.1.2.1.105.1.3.1.1.4')  # pethMainPseConsumptionPower
    except:
        pass

    poe_info = None
    if poe_budget:
        first_key = list(poe_budget.keys())[0] if poe_budget else None
        if first_key:
            poe_info = {
                'budget_watts': poe_budget.get(first_key, '0'),
                'consumption_watts': poe_consumption.get(first_key, '0'),
            }

    return {
        'supplies': supplies,
        'poe': poe_info,
    }

async def get_device_fans(ip: str, community: str) -> dict:
    """Fan status via CISCO-ENVMON-MIB."""
    import asyncio

    fan_descr, fan_state = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.4.1.2'),  # ciscoEnvMonFanStatusDescr
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.4.1.3'),  # ciscoEnvMonFanState
    )

    STATE_MAP = {'1': 'Normal', '2': 'Warning', '3': 'Critical', '4': 'Shutdown',
                 '5': 'Not Present', '6': 'Not Functioning'}

    fans = []
    for idx in fan_descr:
        state_val = fan_state.get(idx, '0')
        fans.append({
            'index': idx,
            'name': fan_descr.get(idx, f'Fan {idx}'),
            'state': STATE_MAP.get(state_val, f'Unknown ({state_val})'),
            'state_code': state_val,
            'ok': state_val == '1',
        })

    return {'fans': fans}

async def get_device_temperature(ip: str, community: str) -> dict:
    """Temperature sensors via CISCO-ENVMON-MIB."""
    import asyncio

    temp_descr, temp_value, temp_threshold, temp_state = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.3.1.2'),  # ciscoEnvMonTemperatureStatusDescr
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.3.1.3'),  # ciscoEnvMonTemperatureStatusValue
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.3.1.4'),  # ciscoEnvMonTemperatureThreshold
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.13.1.3.1.6'),  # ciscoEnvMonTemperatureState
    )

    STATE_MAP = {'1': 'Normal', '2': 'Warning', '3': 'Critical', '4': 'Shutdown',
                 '5': 'Not Present', '6': 'Not Functioning'}

    sensors = []
    for idx in temp_descr:
        state_val = temp_state.get(idx, '0')
        sensors.append({
            'index': idx,
            'name': temp_descr.get(idx, f'Sensor {idx}'),
            'value_celsius': temp_value.get(idx, '—'),
            'threshold_celsius': temp_threshold.get(idx, '—'),
            'state': STATE_MAP.get(state_val, f'Unknown ({state_val})'),
            'ok': state_val == '1',
        })

    return {'sensors': sensors}

async def get_device_sfp(ip: str, community: str) -> dict:
    """SFP/Transceiver modules from Entity MIB — filtered by class=10 (port) or transceiver entries."""
    import asyncio

    descr, model_name, serial, vendor_type, phys_class = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.2'),   # entPhysicalDescr
        _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.13'),  # entPhysicalModelName
        _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.11'),  # entPhysicalSerialNum
        _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.3'),   # entPhysicalVendorType
        _snmp_walk(ip, community, '1.3.6.1.2.1.47.1.1.1.1.5'),   # entPhysicalClass
    )

    sfps = []
    for idx in descr:
        desc_lower = descr.get(idx, '').lower()
        cls = phys_class.get(idx, '')
        # Filter for transceivers: class 10 (port) with SFP/transceiver keywords, or class 10 with model
        if cls == '10' or 'sfp' in desc_lower or 'transceiver' in desc_lower or 'gbic' in desc_lower or 'xfp' in desc_lower:
            mdl = model_name.get(idx, '')
            ser = serial.get(idx, '')
            if mdl or ser or 'sfp' in desc_lower or 'transceiver' in desc_lower:
                sfps.append({
                    'index': idx,
                    'description': descr.get(idx, ''),
                    'model': mdl or '—',
                    'serial': ser or '—',
                    'vendor_type': vendor_type.get(idx, '—'),
                })

    return {'sfp_modules': sfps}

async def get_device_vlans(ip: str, community: str) -> dict:
    """VLAN information via CISCO-VTP-MIB."""
    import asyncio

    vlan_state, vlan_name, vlan_type = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.46.1.3.1.1.2'),  # vtpVlanState
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.46.1.3.1.1.4'),  # vtpVlanName
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.46.1.3.1.1.3'),  # vtpVlanType
    )

    # vtpVlanState: 1=operational, 2=suspended, 3=mtuTooBigForDevice, 4=mtuTooBigForTrunk
    STATE_MAP = {'1': 'Active', '2': 'Suspended', '3': 'MTU Too Big (Device)', '4': 'MTU Too Big (Trunk)'}
    TYPE_MAP = {'1': 'Ethernet', '2': 'FDDI', '3': 'TokenRing', '4': 'FDDINet', '5': 'TRNet'}

    vlans = []
    # VTP MIB indexes as managementDomainIndex.vlanID — but last part is VLAN ID
    for idx in vlan_state:
        vlans.append({
            'vlan_id': idx,
            'name': vlan_name.get(idx, f'VLAN{idx}'),
            'state': STATE_MAP.get(vlan_state.get(idx, ''), vlan_state.get(idx, '—')),
            'type': TYPE_MAP.get(vlan_type.get(idx, ''), vlan_type.get(idx, '—')),
        })

    # Sort by VLAN ID numerically
    try:
        vlans.sort(key=lambda v: int(v['vlan_id']))
    except:
        pass

    return {'vlans': vlans}

async def get_device_stp(ip: str, community: str) -> dict:
    """Spanning Tree info via BRIDGE-MIB."""
    import asyncio

    stp_data = await _snmp_get(ip, community, [
        '1.3.6.1.2.1.17.2.1.0',   # dot1dStpProtocolSpecification
        '1.3.6.1.2.1.17.2.2.0',   # dot1dStpPriority
        '1.3.6.1.2.1.17.2.5.0',   # dot1dStpDesignatedRoot
        '1.3.6.1.2.1.17.2.6.0',   # dot1dStpRootCost
        '1.3.6.1.2.1.17.2.7.0',   # dot1dStpRootPort
        '1.3.6.1.2.1.17.2.8.0',   # dot1dStpMaxAge
        '1.3.6.1.2.1.17.2.9.0',   # dot1dStpHelloTime
        '1.3.6.1.2.1.17.2.10.0',  # dot1dStpHoldTime
        '1.3.6.1.2.1.17.2.11.0',  # dot1dStpForwardDelay
    ])

    PROTO_MAP = {'1': 'Unknown', '2': 'decLb100', '3': 'ieee8021d'}

    # Parse designated root to extract bridge priority and MAC
    root_raw = stp_data.get('1.3.6.1.2.1.17.2.5.0', '')
    root_priority = '—'
    root_mac = '—'
    if root_raw and root_raw.startswith('0x') and len(root_raw) >= 18:
        hex_str = root_raw[2:]
        root_priority = str(int(hex_str[:4], 16))
        root_mac = ':'.join([hex_str[i:i+2] for i in range(4, 16, 2)])

    return {
        'protocol': PROTO_MAP.get(stp_data.get('1.3.6.1.2.1.17.2.1.0', ''), '—'),
        'bridge_priority': stp_data.get('1.3.6.1.2.1.17.2.2.0', '—'),
        'designated_root': root_raw,
        'root_priority': root_priority,
        'root_mac': root_mac,
        'root_cost': stp_data.get('1.3.6.1.2.1.17.2.6.0', '—'),
        'root_port': stp_data.get('1.3.6.1.2.1.17.2.7.0', '—'),
        'max_age': stp_data.get('1.3.6.1.2.1.17.2.8.0', '—'),
        'hello_time': stp_data.get('1.3.6.1.2.1.17.2.9.0', '—'),
        'forward_delay': stp_data.get('1.3.6.1.2.1.17.2.11.0', '—'),
    }

async def get_device_stack(ip: str, community: str) -> dict:
    """StackWise info via CISCO-STACKWISE-MIB (1.3.6.1.4.1.9.9.500)."""
    import asyncio

    sw_num, sw_role, sw_priority, sw_mac, sw_image = await asyncio.gather(
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.500.1.2.1.1.1'),  # cswSwitchNumCurrent
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.500.1.2.1.1.3'),  # cswSwitchRole
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.500.1.2.1.1.4'),  # cswSwitchSwPriority
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.500.1.2.1.1.6'),  # cswSwitchMacAddress
        _snmp_walk(ip, community, '1.3.6.1.4.1.9.9.500.1.2.1.1.8'),  # cswSwitchSoftwareImage
    )

    ROLE_MAP = {'1': 'Master', '2': 'Member', '3': 'notMember', '4': 'standby'}

    members = []
    for idx in sw_num:
        mac_raw = sw_mac.get(idx, '')
        mac_fmt = mac_raw
        if mac_raw.startswith('0x') and len(mac_raw) == 14:
            raw = mac_raw[2:]
            mac_fmt = ':'.join([raw[i:i+2] for i in range(0, len(raw), 2)])

        members.append({
            'index': idx,
            'switch_num': sw_num.get(idx, idx),
            'role': ROLE_MAP.get(sw_role.get(idx, ''), sw_role.get(idx, '—')),
            'priority': sw_priority.get(idx, '—'),
            'mac_address': mac_fmt,
            'software_image': sw_image.get(idx, '—'),
        })

    return {'members': members}

async def get_port_traffic(ip: str, community: str, port_index: str) -> dict:
    """Fetches real-time traffic counters for a specific port."""
    import time
    
    # Try 64-bit counters first (ifHCInOctets, ifHCOutOctets), fallback to 32-bit (ifInOctets, ifOutOctets)
    oids = [
        f'1.3.6.1.2.1.31.1.1.1.6.{port_index}',   # ifHCInOctets
        f'1.3.6.1.2.1.31.1.1.1.10.{port_index}',  # ifHCOutOctets
        f'1.3.6.1.2.1.2.2.1.10.{port_index}',     # ifInOctets
        f'1.3.6.1.2.1.2.2.1.16.{port_index}'      # ifOutOctets
    ]
    
    data = await _snmp_get(ip, community, oids)
    
    in_octets = data.get(f'1.3.6.1.2.1.31.1.1.1.6.{port_index}')
    out_octets = data.get(f'1.3.6.1.2.1.31.1.1.1.10.{port_index}')
    
    if not in_octets:
        in_octets = data.get(f'1.3.6.1.2.1.2.2.1.10.{port_index}', '0')
    if not out_octets:
        out_octets = data.get(f'1.3.6.1.2.1.2.2.1.16.{port_index}', '0')
        
    try:
        in_bytes = int(in_octets) if in_octets else 0
        out_bytes = int(out_octets) if out_octets else 0
    except ValueError:
        in_bytes = 0
        out_bytes = 0
        
    return {
        "timestamp": time.time(),
        "in_bytes": in_bytes,
        "out_bytes": out_bytes
    }


async def _async_poll_device_telemetry(device_id: int, ip_address: str, discovery_source: str):
    import json
    import asyncio
    from datetime import datetime
    from app.models.network import DeviceTelemetry
    from app.db import SessionLocal
    from app.models.settings import SystemSetting
    
    if not ip_address:
        return
        
    db_session = SessionLocal()
    try:

        
        # Get SNMP community
        comm = "public"
        comm_str = discovery_source or ""
        if "COMMUNITY:" in comm_str.upper():
            for p in comm_str.split(","):
                if p.upper().startswith("COMMUNITY:"):
                    comm = p[len("COMMUNITY:"):]
                    break
        else:
            global_comm = db_session.query(SystemSetting).filter(SystemSetting.setting_key == 'snmp_community').first()
            if global_comm and global_comm.setting_value:
                comm = global_comm.setting_value
                
        ip = ip_address
        
        # Limit total telemetry tasks to 2 at a time to respect switch CPU
        sem = asyncio.Semaphore(2)
        
        async def run_with_sem(coro):
            async with sem:
                return await coro

        results = await asyncio.gather(
            run_with_sem(get_switch_ports(ip, comm)),
            run_with_sem(get_arp_table(ip, comm)),
            run_with_sem(get_device_power(ip, comm)),
            run_with_sem(get_device_fans(ip, comm)),
            run_with_sem(get_device_temperature(ip, comm)),
            run_with_sem(get_device_summary(ip, comm)),
            run_with_sem(get_device_hardware_software(ip, comm)),
            run_with_sem(get_device_sfp(ip, comm)),
            run_with_sem(get_device_vlans(ip, comm)),
            run_with_sem(get_device_stp(ip, comm)),
            run_with_sem(get_device_stack(ip, comm)),
            run_with_sem(get_cdp_neighbors(ip, comm)),
            return_exceptions=True
        )
        
        def get_result(idx, default):
            return results[idx] if not isinstance(results[idx], Exception) else default
            
        ports = get_result(0, [])
        arp = get_result(1, {})
        power = get_result(2, {})
        fans = get_result(3, {})
        temp = get_result(4, {})
        summary = get_result(5, {})
        hw_sw = get_result(6, {})
        sfp = get_result(7, {})
        vlans = get_result(8, {})
        stp = get_result(9, {})
        stack = get_result(10, {})
        cdp = get_result(11, [])
        
        # Yield to the event loop so HTTP requests aren't starved
        await asyncio.sleep(0)
        
        summary_data = {
            "power": power,
            "fans": fans,
            "environment": temp,
            "arp": arp,
            "summary": summary,
            "hw-sw": hw_sw,
            "sfp": sfp,
            "vlans": vlans,
            "stp": stp,
            "stack": stack,
            "cdp": cdp
        }
        
        # Update or create telemetry
        telemetry = db_session.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == device_id).first()
        if not telemetry:
            telemetry = DeviceTelemetry(device_id=device_id)
            db_session.add(telemetry)
            
        telemetry.ports_data_json = json.dumps(ports)
        telemetry.summary_data_json = json.dumps(summary_data)
        telemetry.last_polled_at = datetime.utcnow()
        
        db_session.commit()
        logger.info(f"Successfully polled full telemetry for switch {ip_address}")
    except Exception as e:
        logger.error(f"Error polling telemetry for {ip_address}: {e}")
        db_session.rollback()
    finally:
        db_session.close()

def sync_poll_device_telemetry(device_id: int, ip_address: str, discovery_source: str):
    import asyncio
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_poll_device_telemetry(device_id, ip_address, discovery_source))
    finally:
        loop.close()

async def poll_device_telemetry(device_id: int, ip_address: str, discovery_source: str):
    """
    Dispatches the telemetry polling to a background thread to prevent PySNMP 
    ASN.1 decoding from freezing the FastAPI event loop.
    """
    import asyncio
    if not ip_address:
        return
    await asyncio.to_thread(sync_poll_device_telemetry, device_id, ip_address, discovery_source)


async def _async_poll_fast_traffic(device_id: int, ip_address: str, discovery_source: str):
    """Ultra-fast SNMP poll that ONLY fetches traffic and status for the 10-second interval."""
    from app.models.network import PortTelemetryHistory
    from app.db import engine
    from datetime import datetime
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
    
    if not ip_address: return
    
    db_session = SessionLocal()
    try:
        comm = "public"
        comm_str = discovery_source or ""
        if "COMMUNITY:" in comm_str.upper():
            for p in comm_str.split(","):
                if p.upper().startswith("COMMUNITY:"):
                    comm = p[len("COMMUNITY:"):]
                    break
        else:
            from app.models.settings import SystemSetting
            global_comm = db_session.query(SystemSetting).filter(SystemSetting.setting_key == 'snmp_community').first()
            if global_comm and global_comm.setting_value:
                comm = global_comm.setting_value
                
        eng = _get_snmp_engine()
        admin, oper, hc_in, hc_out = await asyncio.gather(
            _snmp_walk(ip_address, comm, '1.3.6.1.2.1.2.2.1.7', eng),
            _snmp_walk(ip_address, comm, '1.3.6.1.2.1.2.2.1.8', eng),
            _snmp_walk(ip_address, comm, '1.3.6.1.2.1.31.1.1.1.6', eng),
            _snmp_walk(ip_address, comm, '1.3.6.1.2.1.31.1.1.1.10', eng)
        )
            
        try:
            PortTelemetryHistory.__table__.create(engine, checkfirst=True)
        except Exception:
            pass
            
        now = datetime.utcnow()
        for idx in admin.keys():
            ib = hc_in.get(idx)
            ob = hc_out.get(idx)
            history = PortTelemetryHistory(
                device_id=device_id,
                port_index=str(idx),
                in_bytes=int(ib) if ib else 0,
                out_bytes=int(ob) if ob else 0,
                admin_status=str(admin.get(idx, '')),
                oper_status=str(oper.get(idx, '')),
                timestamp=now
            )
            db_session.add(history)
            
        db_session.commit()
    except Exception as e:
        logger.warning(f"Fast traffic poll error for {ip_address}: {e}")
        db_session.rollback()
    finally:
        db_session.close()

async def poll_fast_port_traffic():
    """Runs the ultra-fast port traffic history check across all switches."""
    db_session = SessionLocal()
    from app.models.network import DiscoveredDevice
    try:
        switches = db_session.query(DiscoveredDevice).filter(
            DiscoveredDevice.device_type.ilike('%switch%')
        ).all()
        
        # We can poll many more switches concurrently since it's just 4 OIDs
        sem = asyncio.Semaphore(20)
        
        async def poll_with_sem(d):
            async with sem:
                await _async_poll_fast_traffic(d.id, d.ip_address, d.discovery_source)
                
        await asyncio.gather(*(poll_with_sem(d) for d in switches))
    finally:
        db_session.close()


async def poll_all_switch_telemetry():
    """Background routine to poll telemetry from all known active switches."""
    from app.db import SessionLocal
    from app.models.network import DiscoveredDevice
    import asyncio
    
    logger.info("=== poll_all_switch_telemetry() CALLED ===")
    db = SessionLocal()
    try:
        switches = db.query(DiscoveredDevice).filter(
            DiscoveredDevice.status != 'IGNORED',
            DiscoveredDevice.snmp_status == 'CONNECTED',
            DiscoveredDevice.device_type.in_(['Switch', 'Router'])
        ).all()
        
        if not switches:
            logger.info("No active switches/routers found for telemetry polling.")
            return
            
        logger.info(f"Polling telemetry for {len(switches)} devices...")
        
        # Poll ONE switch at a time sequentially with pauses between each.
        for sw in switches:
            local_db = SessionLocal()
            try:
                local_device = local_db.query(DiscoveredDevice).filter(DiscoveredDevice.id == sw.id).first()
                if local_device:
                    await poll_device_telemetry(local_device.id, local_device.ip_address, local_device.discovery_source)
            except Exception as e:
                logger.error(f"Error polling telemetry for device {sw.ip_address}: {e}")
            finally:
                local_db.close()
            
            # Breathe between switches so the event loop can serve HTTP requests
            await asyncio.sleep(2)
            
        logger.info("=== poll_all_switch_telemetry() COMPLETED ===")
    except Exception as e:
        logger.error(f"Failed to complete telemetry polling: {e}")
    finally:
        db.close()
