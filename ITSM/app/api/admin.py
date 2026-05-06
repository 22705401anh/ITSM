"""Admin API routes including Active Directory integration."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import logging
from ldap3 import Server, Connection, ALL, SUBTREE, ALL_ATTRIBUTES
from app.config import settings
import asyncio
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db import get_db, create_engine_for_url
from app.models.user import User
from app.models.settings import SystemSetting
from app.config import settings
from app.utils.ldap_config import get_ldap_config
from pydantic import BaseModel
from typing import Optional, List, Dict
import smtplib
import os
import json

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/users")
async def get_local_users(db: Session = Depends(get_db)):
    """Fetch all active local users from the SQL database."""
    try:
        users = db.query(User).order_by(User.full_name).all()
        return [{
            "id": u.id, 
            "username": u.username, 
            "full_name": u.full_name, 
            "email": u.email,
            "is_active": u.is_active,
            "role": u.role,
            "assigned_pages": u.assigned_pages,
            "auth_type": "ldap" if u.hashed_password == "AD_MANAGED_USER" else "local"
        } for u in users]
    except Exception as e:
        logger.error(f"Error fetching local users: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch local users")

@router.get("/users/{user_id}")
async def get_user_details(user_id: int, db: Session = Depends(get_db)):
    """Fetch specific user details."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "department": getattr(user, 'department', None),
        "title": getattr(user, 'title', None),
        "is_active": user.is_active,
        "ad_active": getattr(user, 'ad_active', True)
    }

@router.post("/users/{user_id}/revoke")
async def revoke_user_access(user_id: int, db: Session = Depends(get_db)):
    """Revoke a user's login access by deactivating their account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    logger.info(f"Access revoked for user: {user.username}")
    return {"message": f"Access revoked for '{user.username}'"}

@router.post("/users/{user_id}/grant")
async def grant_user_access(user_id: int, db: Session = Depends(get_db)):
    """Grant a user login access by activating their account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    db.commit()
    logger.info(f"Access granted for user: {user.username}")
    return {"message": f"Access granted for '{user.username}'"}

class UserRoleUpdate(BaseModel):
    role: str

@router.post("/users/{user_id}/role")
async def update_user_role(user_id: int, payload: UserRoleUpdate, db: Session = Depends(get_db)):
    """Update a user's role."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if payload.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role specified")
        
    user.role = payload.role
    db.commit()
    logger.info(f"Role updated for user {user.username} to {payload.role}")
    return {"status": "success", "message": f"User role updated to {payload.role}"}

class PermissionsUpdate(BaseModel):
    assigned_pages: str

@router.post("/users/{user_id}/permissions")
async def update_user_permissions(user_id: int, permissions: PermissionsUpdate, db: Session = Depends(get_db)):
    """Update a user's assigned pages."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.assigned_pages = permissions.assigned_pages
    db.commit()
    
    return {"status": "success", "message": "User permissions updated successfully"}

@router.get("/users/{user_id}/hardware")
async def get_user_hardware(user_id: int, db: Session = Depends(get_db)):
    """Fetch current and historical hardware assignments for a user."""
    from app.models.hardware import PC, Monitor, DockingStation, Phone, AssetAssignment

    # Current assignments
    pcs = db.query(PC).filter(PC.current_user_id == user_id).all()
    monitors = db.query(Monitor).filter(Monitor.current_user_id == user_id).all()
    docks = db.query(DockingStation).filter(DockingStation.current_user_id == user_id).all()
    phones = db.query(Phone).filter(Phone.current_user_id == user_id).all()

    current = []
    for hw in pcs: current.append({"type": "pc", "id": hw.id, "model": hw.model, "serial_number": hw.serial_number})
    for hw in monitors: current.append({"type": "monitor", "id": hw.id, "model": hw.model, "serial_number": hw.serial_number})
    for hw in docks: current.append({"type": "docking_station", "id": hw.id, "model": hw.model, "serial_number": hw.serial_number})
    for hw in phones: current.append({"type": "phone", "id": hw.id, "model": hw.model, "serial_number": hw.serial_number, "phone_number": hw.phone_number})

    # History (assignments)
    from sqlalchemy import or_
    assignments = db.query(AssetAssignment).filter(
        or_(AssetAssignment.new_user_id == user_id, AssetAssignment.previous_user_id == user_id)
    ).order_by(AssetAssignment.assigned_date.desc()).all()

    history = []
    for a in assignments:
        hw_type = "Unknown"
        hw_serial = ""
        hw_model = ""
        hw_id = None
        
        if a.pc:
            hw_type = "pc"
            hw_serial = a.pc.serial_number
            hw_model = a.pc.model
            hw_id = a.pc.id
        elif a.monitor:
            hw_type = "monitor"
            hw_serial = a.monitor.serial_number
            hw_model = a.monitor.model
            hw_id = a.monitor.id
        elif a.docking_station:
            hw_type = "docking_station"
            hw_serial = a.docking_station.serial_number
            hw_model = a.docking_station.model
            hw_id = a.docking_station.id
        elif a.phone:
            hw_type = "phone"
            hw_serial = a.phone.serial_number
            hw_model = a.phone.model
            hw_id = a.phone.id

        # Determine if this was an assignment TO the user or RETURN FROM the user
        action = ""
        date_val = a.assigned_date

        if a.new_user_id == user_id:
            if a.is_active:
                action = "Assigned"
            else:
                action = "Returned"
                if a.returned_date:
                    date_val = a.returned_date
        elif a.previous_user_id == user_id:
            action = "Transferred"

        history.append({
            "id": a.id,
            "action": action,
            "hw_type": hw_type,
            "hw_serial": hw_serial,
            "hw_model": hw_model,
            "hw_id": hw_id,
            "date": date_val.isoformat() if date_val else None,
            "notes": a.notes
        })

    return {
        "current": current,
        "history": history
    }

@router.get("/ad-users")
async def get_ad_users(db: Session = Depends(get_db)):
    """Fetch user list from Active Directory in real-time."""
    try:
        ldap_cfg = get_ldap_config(db)
        # Add timeout to prevent hanging
        loop = asyncio.get_event_loop()

        def ldap_query(cfg):
            logger.info(f"Connecting to LDAP server: {cfg['server']}:{cfg['port']}")
            server = Server(cfg['server'], port=cfg['port'], get_info=ALL)

            logger.info(f"Binding with DN: {cfg['bind_dn']}")
            conn = Connection(
                server, 
                user=cfg['bind_dn'], 
                password=cfg['password'], 
                auto_bind=True
            )

            search_filter = '(&(objectClass=user)(objectCategory=person))'  # All users including disabled
            attributes = ['sAMAccountName', 'displayName', 'mail', 'department', 'telephoneNumber', 'company', 'userAccountControl', 'thumbnailPhoto']

            logger.info(f"Searching with filter: {search_filter}")
            conn.search(
                search_base=ldap_cfg['base_dn'],
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=1000
            )

            users = []
            logger.info(f"Processing {len(conn.entries)} entries from LDAP")
            import base64
            for entry in conn.entries:
                def get_attr(attr_name):
                    if attr_name in entry and entry[attr_name]:
                        val = str(entry[attr_name])
                        if val and val != "[]" and val != "None":
                            return val
                    return ""

                uac_str = get_attr('userAccountControl')
                try:
                    uac = int(uac_str) if uac_str else 0
                except ValueError:
                    uac = 0
                is_active = not bool(uac & 2)

                # Extract image
                profile_image = None
                if 'thumbnailPhoto' in entry and entry['thumbnailPhoto'] and entry['thumbnailPhoto'].value:
                    try:
                        photo_bytes = entry['thumbnailPhoto'].value
                        b64_photo = base64.b64encode(photo_bytes).decode('utf-8')
                        profile_image = f"data:image/jpeg;base64,{b64_photo}"
                    except Exception as e:
                        logger.warning(f"Error encoding photo for {get_attr('sAMAccountName')}: {e}")

                users.append({
                    "username": get_attr('sAMAccountName'),
                    "name": get_attr('displayName'),
                    "email": get_attr('mail'),
                    "department": get_attr('department'),
                    "phone": get_attr('telephoneNumber'),
                    "company": get_attr('company'),
                    "profile_image": profile_image,
                    "is_active": is_active
                })

            conn.unbind()
            logger.info(f"Successfully retrieved {len(users)} users from LDAP")
            return users

        # Run the LDAP query in a thread pool to prevent blocking
        users = await asyncio.wait_for(
            loop.run_in_executor(None, ldap_query, ldap_cfg),
            timeout=30
        )

        # Sort users by name
        users.sort(key=lambda x: x['name'] or '')

        return users

    except asyncio.TimeoutError:
        logger.error("LDAP query timed out after 30 seconds")
        raise HTTPException(status_code=500, detail="LDAP query timed out - the server may be unreachable or slow")
    except Exception as e:
        logger.error(f"Error communicating with Active Directory: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch AD users: {str(e)}")

@router.post("/sync-ad-users")
async def sync_ad_users(db: Session = Depends(get_db)):
    """Fetch user list from Active Directory and sync to the local database."""
    try:
        users_from_ad = await get_ad_users()
        
        synced_count = 0
        for ad_user in users_from_ad:
            username = ad_user.get("username")
            if not username or username.endswith('$') or username == 'None':
                continue
                
            email = ad_user.get("email") or f"{username}@local"
            name = ad_user.get("name") or username
            department = ad_user.get("department") or ""
            phone = ad_user.get("phone") or ""
            profile_image = ad_user.get("profile_image")
            
            is_active = ad_user.get("is_active", True)
            
            # Check if user exists in SQL DB
            db_user = db.query(User).filter(User.username == username).first()
            if not db_user:
                # If new AD User, import to SQL db
                new_user = User(
                    username=username,
                    email=email.lower(),
                    full_name=name,
                    department=department,
                    phone=phone,
                    profile_image=profile_image,
                    hashed_password="AD_MANAGED_USER",
                    is_active=False,  # Users have no login access by default
                    ad_active=is_active
                )
                db.add(new_user)
                synced_count += 1
            else:
                # Update existing
                updated = False
                if db_user.full_name != name:
                    db_user.full_name = name
                    updated = True
                if db_user.email != email.lower():
                    db_user.email = email.lower()
                    updated = True
                if db_user.department != department:
                    db_user.department = department
                    updated = True
                if db_user.phone != phone:
                    db_user.phone = phone
                    updated = True
                if profile_image and db_user.profile_image != profile_image:
                    db_user.profile_image = profile_image
                    updated = True
                
                # Update employment status from AD
                if getattr(db_user, 'ad_active', True) != is_active:
                    db_user.ad_active = is_active
                    updated = True
                    
                # We intentionally DO NOT update db_user.is_active so IT retains manual access control
                    
                if updated:
                    synced_count += 1
                    
        db.commit()
        return {"message": "AD users successfully synced to local database", "synced_count": synced_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing AD users: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync AD users: {str(e)}")


@router.post("/import-ad-user")
async def import_ad_user(payload: dict, db: Session = Depends(get_db)):
    """Import a single AD user into the local database for ITSM login.
    The user will authenticate via LDAP with their AD credentials.
    """
    username = payload.get("username", "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # Check if user already exists locally
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"User '{username}' already exists in the system")

    # Fetch user info from AD
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
        
        server = Server(settings.LDAP_SERVER, port=settings.LDAP_PORT, get_info=ALL)
        conn = Connection(
            server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_PASSWORD,
            auto_bind=True
        )

        search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
        conn.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['sAMAccountName', 'displayName', 'mail', 'department', 'telephoneNumber', 'company', 'thumbnailPhoto', 'userAccountControl']
        )

        if not conn.entries:
            conn.unbind()
            raise HTTPException(status_code=404, detail=f"User '{username}' not found in Active Directory")

        entry = conn.entries[0]
        
        def get_attr(attr_name):
            if attr_name in entry and entry[attr_name]:
                val = str(entry[attr_name])
                if val and val != "[]" and val != "None":
                    return val
            return ""

        ad_name = get_attr('displayName') or username
        ad_email = get_attr('mail') or f"{username}@ma.kostal.int"
        ad_department = get_attr('department') or ""
        ad_phone = get_attr('telephoneNumber') or ""
        
        uac_str = get_attr('userAccountControl')
        try:
            uac = int(uac_str) if uac_str else 0
        except ValueError:
            uac = 0
        ad_is_active = not bool(uac & 2)
        
        ad_profile_image = None
        if 'thumbnailPhoto' in entry and entry['thumbnailPhoto'] and entry['thumbnailPhoto'].value:
            try:
                import base64
                photo_bytes = entry['thumbnailPhoto'].value
                b64_photo = base64.b64encode(photo_bytes).decode('utf-8')
                ad_profile_image = f"data:image/jpeg;base64,{b64_photo}"
            except Exception as e:
                logger.warning(f"Error encoding photo for {username}: {e}")

        conn.unbind()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching AD user {username}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch user from AD: {str(e)}")

    # Create the local user with AD_MANAGED_USER marker
    try:
        new_user = User(
            username=username,
            email=ad_email.lower(),
            full_name=ad_name,
            department=ad_department,
            phone=ad_phone,
            profile_image=ad_profile_image,
            hashed_password="AD_MANAGED_USER",
            is_active=False,  # IT must explicitly grant access
            ad_active=ad_is_active
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"AD user '{username}' imported successfully")
        return {
            "message": f"User '{username}' imported from AD successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "full_name": new_user.full_name,
                "email": new_user.email,
                "department": new_user.department,
                "phone": new_user.phone
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating AD user {username}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

@router.get("/ad/search")
async def search_ad_global(q: str, limit: int = 20, db: Session = Depends(get_db)):
    """Search for users across the entire AD forest via Global Catalog."""
    if not q or len(q) < 3:
        return []

    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
        
        # Connect using GC port 3268 for global forest search
        server = Server(settings.LDAP_SERVER, port=3268, get_info=ALL)
        conn = Connection(
            server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_PASSWORD,
            auto_bind=True
        )

        search_base = "DC=kostal,DC=int"
        
        # Escape special characters
        safe_q = q.replace('(', '').replace(')', '').replace('\\', '').replace('*', '')
        search_filter = f'(&(objectClass=user)(objectCategory=person)(|(sAMAccountName=*{safe_q}*)(displayName=*{safe_q}*)(mail=*{safe_q}*)))'
        
        conn.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['sAMAccountName', 'displayName', 'mail', 'department', 'company'],
            size_limit=limit
        )

        results = []
        for entry in conn.entries:
            def get_attr(attr_name):
                if attr_name in entry and entry[attr_name]:
                    val = str(entry[attr_name])
                    if val and val != "[]" and val != "None":
                        return val
                return ""

            username = get_attr('sAMAccountName')
            if not username:
                continue
                
            db_user = db.query(User).filter(User.username == username).first()
            is_active_locally = db_user.is_active if db_user else False

            results.append({
                "username": username,
                "full_name": get_attr('displayName') or username,
                "email": get_attr('mail'),
                "department": get_attr('department'),
                "company": get_attr('company'),
                "is_active_locally": is_active_locally,
                "is_imported": db_user is not None,
                "user_id": db_user.id if db_user else None
            })

        return results
    except Exception as e:
        logger.error(f"Error searching global AD: {e}")
        raise HTTPException(status_code=500, detail="Failed to search Active Directory")

@router.post("/ad/grant")
async def grant_global_ad_access(payload: dict, db: Session = Depends(get_db)):
    """Import an AD user from the global catalog and grant them access."""
    username = payload.get("username", "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    # If already exists locally, just grant access
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.is_active = True
        db.commit()
        return {"message": f"Access granted for '{username}'", "user_id": existing.id}

    # Fetch user info from AD (Global Catalog)
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
        
        server = Server(settings.LDAP_SERVER, port=3268, get_info=ALL)
        conn = Connection(
            server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_PASSWORD,
            auto_bind=True
        )

        search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
        conn.search(
            search_base="DC=kostal,DC=int",
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=['sAMAccountName', 'displayName', 'mail', 'department', 'telephoneNumber', 'company', 'thumbnailPhoto']
        )

        if not conn.entries:
            conn.unbind()
            raise HTTPException(status_code=404, detail=f"User '{username}' not found in Active Directory")

        entry = conn.entries[0]
        
        def get_attr(attr_name):
            if attr_name in entry and entry[attr_name]:
                val = str(entry[attr_name])
                if val and val != "[]" and val != "None":
                    return val
            return ""

        ad_name = get_attr('displayName') or username
        ad_email = get_attr('mail') or f"{username}@ma.kostal.int"
        ad_department = get_attr('department') or ""
        ad_phone = get_attr('telephoneNumber') or ""
        ad_company = get_attr('company') or ""
        
        ad_profile_image = None
        if 'thumbnailPhoto' in entry and entry['thumbnailPhoto'] and entry['thumbnailPhoto'].value:
            try:
                import base64
                photo_bytes = entry['thumbnailPhoto'].value
                b64_photo = base64.b64encode(photo_bytes).decode('utf-8')
                ad_profile_image = f"data:image/jpeg;base64,{b64_photo}"
            except Exception as e:
                pass

        conn.unbind()

        # Create user and grant access
        new_user = User(
            username=username,
            email=ad_email.lower(),
            full_name=ad_name,
            department=ad_department,
            phone=ad_phone,
            profile_image=ad_profile_image,
            hashed_password="AD_MANAGED_USER",
            is_active=True  # explicitly grant access
        )
        db.add(new_user)
        db.commit()
        
        logger.info(f"AD user '{username}' imported and granted access")
        return {"message": f"User '{username}' imported and granted access"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fetch/create user: {str(e)}")

# --- Settings API ---

DB_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "config", "database.json")

class DatabaseSettings(BaseModel):
    db_type: str = "SQLITE"
    database_url_primary: Optional[str] = None
    database_url_secondary: Optional[str] = None

class NotificationSettings(BaseModel):
    email_notif: bool = True
    in_app_notif: bool = True
    ticket_notif: bool = True
    it_alert_email: Optional[str] = None

class LDAPSettings(BaseModel):
    ldap_server: str
    ldap_port: int
    ldap_base_dn: str
    ldap_bind_dn: str
    ldap_password: Optional[str] = None

class SMTPSettings(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    test_email: Optional[str] = None

class SNMPSettings(BaseModel):
    snmp_version: str = "v2c"
    snmp_community: str = "public"
    snmp_port: int = 161
    snmp_timeout: int = 5
    auto_discovery_enabled: bool = True
    auto_discovery_subnets: str = "10.141.10.0/24"

@router.get("/settings/snmp", response_model=SNMPSettings)
async def get_snmp_settings(db: Session = Depends(get_db)):
    """Fetch current global SNMP settings from the DB."""
    def get_setting(key, default=""):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        return s.setting_value if s else default
        
    return {
        "snmp_version": get_setting("snmp_version", "v2c"),
        "snmp_community": get_setting("snmp_community", "public"),
        "snmp_port": int(get_setting("snmp_port", 161)),
        "snmp_timeout": int(get_setting("snmp_timeout", 5)),
        "auto_discovery_enabled": get_setting("auto_discovery_enabled", "true").lower() == "true",
        "auto_discovery_subnets": get_setting("auto_discovery_subnets", "10.141.10.0/24")
    }

@router.post("/settings/snmp")
async def save_snmp_settings(payload: SNMPSettings, db: Session = Depends(get_db)):
    """Save global SNMP settings to the DB."""
    def set_setting(key, value):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if not s:
            s = SystemSetting(setting_key=key, setting_value=str(value))
            db.add(s)
        else:
            s.setting_value = str(value)
            
    try:
        set_setting("snmp_version", payload.snmp_version)
        set_setting("snmp_community", payload.snmp_community)
        set_setting("snmp_port", payload.snmp_port)
        set_setting("snmp_timeout", payload.snmp_timeout)
        set_setting("auto_discovery_enabled", str(payload.auto_discovery_enabled).lower())
        set_setting("auto_discovery_subnets", payload.auto_discovery_subnets)
        db.commit()
        return {"message": "SNMP settings saved successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save SNMP settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save settings")


@router.get("/settings/smtp", response_model=SMTPSettings)
async def get_smtp_settings(db: Session = Depends(get_db)):
    """Fetch current SMTP settings from the DB."""
    def get_setting(key, default=""):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        return s.setting_value if s else default
        
    return {
        "smtp_host": get_setting("smtp_host", ""),
        "smtp_port": int(get_setting("smtp_port", 587)),
        "smtp_user": get_setting("smtp_user", ""),
        "smtp_password": get_setting("smtp_password", ""),
        "smtp_from": get_setting("smtp_from", "KOSTALITSM@kostal.com")
    }

@router.post("/settings/smtp")
async def save_smtp_settings(payload: SMTPSettings, db: Session = Depends(get_db)):
    """Save SMTP settings to the DB."""
    def set_setting(key, value):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if not s:
            s = SystemSetting(setting_key=key, setting_value=str(value))
            db.add(s)
        else:
            s.setting_value = str(value)
            
    try:
        set_setting("smtp_host", payload.smtp_host)
        set_setting("smtp_port", payload.smtp_port)
        set_setting("smtp_user", payload.smtp_user or "")
        set_setting("smtp_password", payload.smtp_password or "")
        if payload.smtp_from:
            set_setting("smtp_from", payload.smtp_from)
        
        db.commit()
        return {"message": "SMTP settings saved successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save SMTP settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.get("/settings/notifications", response_model=NotificationSettings)
async def get_notification_settings(db: Session = Depends(get_db)):
    """Fetch current Notification settings from the DB."""
    def get_setting(key, default="true"):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        return s.setting_value if s else default
        
    return {
        "email_notif": get_setting("notif_email", "true").lower() == "true",
        "in_app_notif": get_setting("notif_in_app", "true").lower() == "true",
        "ticket_notif": get_setting("notif_ticket", "true").lower() == "true",
        "it_alert_email": get_setting("it_alert_email", "")
    }

@router.post("/settings/notifications")
async def save_notification_settings(payload: NotificationSettings, db: Session = Depends(get_db)):
    """Save Notification settings to the DB."""
    def set_setting(key, value):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if not s:
            s = SystemSetting(setting_key=key, setting_value=str(value).lower())
            db.add(s)
        else:
            s.setting_value = str(value).lower()
            
    try:
        set_setting("notif_email", payload.email_notif)
        set_setting("notif_in_app", payload.in_app_notif)
        set_setting("notif_ticket", payload.ticket_notif)
        if payload.it_alert_email is not None:
            set_setting("it_alert_email", payload.it_alert_email)
        db.commit()
        return {"message": "Notification settings saved successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save Notification settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.get("/settings/ldap", response_model=LDAPSettings)
async def get_ldap_settings_endpoint(db: Session = Depends(get_db)):
    """Fetch current LDAP settings from the DB."""
    cfg = get_ldap_config(db)
    return {
        "ldap_server": cfg["server"],
        "ldap_port": cfg["port"],
        "ldap_base_dn": cfg["base_dn"],
        "ldap_bind_dn": cfg["bind_dn"],
        "ldap_password": cfg["password"]
    }

@router.post("/settings/ldap")
async def save_ldap_settings_endpoint(payload: LDAPSettings, db: Session = Depends(get_db)):
    """Save LDAP settings to the DB."""
    def set_setting(key, value):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        if not s:
            s = SystemSetting(setting_key=key, setting_value=str(value))
            db.add(s)
        else:
            s.setting_value = str(value)
            
    # Validate connection before saving
    password = payload.ldap_password
    if not password:
        cfg = get_ldap_config(db)
        password = cfg.get("password")
            
    try:
        server = Server(payload.ldap_server, port=payload.ldap_port, get_info=ALL)
        conn = Connection(
            server,
            user=payload.ldap_bind_dn,
            password=password,
            auto_bind=True,
            receive_timeout=5
        )
        conn.unbind()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot save: LDAP connection failed with these credentials. ({str(e)})")

    try:
        set_setting("ldap_server", payload.ldap_server)
        set_setting("ldap_port", payload.ldap_port)
        set_setting("ldap_base_dn", payload.ldap_base_dn)
        set_setting("ldap_bind_dn", payload.ldap_bind_dn)
        if payload.ldap_password:
            set_setting("ldap_password", payload.ldap_password)
        db.commit()
        return {"message": "LDAP settings saved successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save LDAP settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.post("/settings/ldap/test")
async def test_ldap_connection(payload: LDAPSettings, db: Session = Depends(get_db)):
    """Test a live LDAP connection without saving."""
    try:
        # If no password provided, try to fetch the existing one
        password = payload.ldap_password
        if not password:
            cfg = get_ldap_config(db)
            password = cfg.get("password")

        server = Server(payload.ldap_server, port=payload.ldap_port, get_info=ALL)
        conn = Connection(
            server,
            user=payload.ldap_bind_dn,
            password=password,
            auto_bind=True,
            receive_timeout=5
        )
        conn.unbind()
        return {"message": "LDAP Connection Successful!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"LDAP Connection Failed: {str(e)}")

@router.get("/settings/database/status")
async def get_database_status_live():
    """Fetch live connection status of active database engines."""
    from app.db import engine, sqlite_engine
    
    primary_name = engine.name if engine else "unknown"
    primary_status = "Connected (Active)" if engine else "Disconnected"
    
    fallback_name = sqlite_engine.name if sqlite_engine else "sqlite"
    fallback_status = "Connected (Hot Standby)" if sqlite_engine else "Disconnected"
    
    # If the primary is sqlite, it's just a single local architecture
    if primary_name == "sqlite":
        return {
            "architecture": "Standalone",
            "primary": {"engine": "SQLite (Local)", "status": "Connected (Active)"},
            "fallback": None
        }
        
    engine_map = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "mssql": "SQL Server",
        "sqlite": "SQLite"
    }
    
    return {
        "architecture": "High Availability",
        "primary": {"engine": engine_map.get(primary_name, primary_name.upper()), "status": primary_status},
        "fallback": {"engine": "SQLite (Local)", "status": fallback_status}
    }

@router.get("/settings/database", response_model=DatabaseSettings)
async def get_database_settings():
    """Fetch current database configuration from secure local file."""
    if os.path.exists(DB_CONFIG_PATH):
        try:
            with open(DB_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return DatabaseSettings(**data)
        except Exception as e:
            logger.error(f"Failed to read database.json: {e}")
            
    # Fallback to defaults
    return DatabaseSettings()

@router.post("/settings/database")
async def save_database_settings(payload: DatabaseSettings):
    """Save database configuration to secure local file."""
    try:
        os.makedirs(os.path.dirname(DB_CONFIG_PATH), exist_ok=True)
        with open(DB_CONFIG_PATH, "w") as f:
            json.dump(payload.dict(), f, indent=4)
        return {"message": "Database settings saved successfully. A server restart is required for changes to take effect."}
    except Exception as e:
        logger.error(f"Failed to write database.json: {e}")
        raise HTTPException(status_code=500, detail="Failed to save database settings to disk.")

@router.post("/settings/database/test")
async def test_database_connection(payload: DatabaseSettings):
    """Test a database connection payload without saving or restarting."""
    from sqlalchemy.exc import OperationalError
    
    url = payload.database_url_primary
    if not url:
        raise HTTPException(status_code=400, detail="Primary Connection String is required for testing.")
        
    try:
        engine = create_engine_for_url(url)
        with engine.connect() as conn:
            pass # successful ping
        return {"message": "Connection Successful!"}
    except OperationalError as e:
        raise HTTPException(status_code=400, detail=f"Connection Failed: {str(e.orig)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing connection: {str(e)}")

@router.get("/settings/database/export")
async def export_database():
    """Export the local SQLite database as a file download."""
    from app.db import engine
    
    if engine and engine.name != "sqlite":
        raise HTTPException(status_code=400, detail="Database file export is only supported for the local SQLite engine. Please use native administration tools for external databases.")
        
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Local database file not found.")
        
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    return FileResponse(db_path, filename=f"kostal-itsm-backup-{timestamp}.db", media_type="application/octet-stream")

@router.post("/settings/database/import")
async def import_database(file: UploadFile = File(...)):
    """Import a SQLite database file and overwrite the local db."""
    from app.db import engine
    
    if engine and engine.name != "sqlite":
        raise HTTPException(status_code=400, detail="Database file import is only supported for the local SQLite engine. Please use native administration tools for external databases.")
        
    if not file.filename.endswith(".db") and not file.filename.endswith(".sqlite3"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be a .db or .sqlite3 backup file.")
        
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    try:
        content = await file.read()
        with open(db_path, "wb") as f:
            f.write(content)
        return {"message": "Database restored successfully. A server restart is required."}
    except Exception as e:
        logger.error(f"Failed to restore database: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to write database file.")

@router.post("/settings/test-smtp")
async def test_smtp_settings(payload: SMTPSettings):
    """Test SMTP connection using the provided payload without saving."""
    if not payload.smtp_host:
        raise HTTPException(status_code=400, detail="SMTP Host is required for testing.")
        
    try:
        server = smtplib.SMTP(payload.smtp_host, payload.smtp_port)
        server.ehlo()
        if server.has_extn('STARTTLS'):
            server.starttls()
            server.ehlo()
            
        if payload.smtp_user and payload.smtp_password:
            server.login(payload.smtp_user, payload.smtp_password)
            
        message = "Connection successful! Authentication passed."
        
        # Send actual test email if address is provided
        if payload.test_email:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from app.config import settings
            
            msg = MIMEMultipart()
            msg["Subject"] = "KOSTAL ITSM - SMTP Connection Test"
            sender_email = payload.smtp_from or "KOSTALITSM@kostal.com"
            msg["From"] = sender_email
            msg["To"] = payload.test_email
            
            body = "Hello,\n\nIf you are reading this, the KOSTAL ITSM SMTP Configuration is working perfectly!\n\nBest regards,\nITSM System"
            msg.attach(MIMEText(body, "plain"))
            
            server.sendmail(sender_email, payload.test_email, msg.as_string())
            message = f"Connection successful! A test email was sent to {payload.test_email}."
            
        server.quit()
        return {"message": message}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="Authentication failed. Check your username and password.")
    except Exception as e:
        logger.error(f"SMTP Test Failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")
