"""Admin API routes including Active Directory integration."""

from fastapi import APIRouter, HTTPException
import logging
from ldap3 import Server, Connection, ALL, SUBTREE, ALL_ATTRIBUTES
from app.config import settings
import asyncio
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/users")
async def get_local_users(db: Session = Depends(get_db)):
    """Fetch all active local users from the SQL database."""
    try:
        users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
        return [{"id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email} for u in users]
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
        "is_active": user.is_active
    }

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
        
        if a.pc:
            hw_type = "pc"
            hw_serial = a.pc.serial_number
            hw_model = a.pc.model
        elif a.monitor:
            hw_type = "monitor"
            hw_serial = a.monitor.serial_number
            hw_model = a.monitor.model
        elif a.docking_station:
            hw_type = "docking_station"
            hw_serial = a.docking_station.serial_number
            hw_model = a.docking_station.model
        elif a.phone:
            hw_type = "phone"
            hw_serial = a.phone.serial_number
            hw_model = a.phone.model

        # Determine if this was an assignment TO the user or RETURN FROM the user
        action = ""
        if a.new_user_id == user_id:
            action = "Assigned"
        elif a.previous_user_id == user_id:
            action = "Returned"

        history.append({
            "id": a.id,
            "action": action,
            "hw_type": hw_type,
            "hw_serial": hw_serial,
            "hw_model": hw_model,
            "date": a.assigned_date.isoformat() if a.assigned_date else None,
            "notes": a.notes
        })

    return {
        "current": current,
        "history": history
    }

@router.get("/ad-users")
async def get_ad_users():
    """Fetch user list from Active Directory in real-time."""
    try:
        # Add timeout to prevent hanging
        loop = asyncio.get_event_loop()

        def ldap_query():
            logger.info(f"Connecting to LDAP server: {settings.LDAP_SERVER}:{settings.LDAP_PORT}")
            server = Server(settings.LDAP_SERVER, port=settings.LDAP_PORT, get_info=ALL)

            logger.info(f"Binding with DN: {settings.LDAP_BIND_DN}")
            conn = Connection(
                server, 
                user=settings.LDAP_BIND_DN, 
                password=settings.LDAP_PASSWORD, 
                auto_bind=True
            )

            search_filter = '(&(objectClass=user)(objectCategory=person))'  # All users including disabled
            attributes = ['sAMAccountName', 'displayName', 'mail', 'department', 'title', 'company', 'userAccountControl']

            logger.info(f"Searching with filter: {search_filter}")
            conn.search(
                search_base=settings.LDAP_BASE_DN,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=1000
            )

            users = []
            logger.info(f"Processing {len(conn.entries)} entries from LDAP")
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

                users.append({
                    "username": get_attr('sAMAccountName'),
                    "name": get_attr('displayName'),
                    "email": get_attr('mail'),
                    "department": get_attr('department'),
                    "title": get_attr('title'),
                    "company": get_attr('company'),
                    "is_active": is_active
                })

            conn.unbind()
            logger.info(f"Successfully retrieved {len(users)} users from LDAP")
            return users

        # Run the LDAP query in a thread pool to prevent blocking
        users = await asyncio.wait_for(
            loop.run_in_executor(None, ldap_query),
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
            
            is_active = ad_user.get("is_active", True)
            
            # Check if user exists in SQL DB
            db_user = db.query(User).filter(User.username == username).first()
            if not db_user:
                # If new AD User, import to SQL db
                new_user = User(
                    username=username,
                    email=email.lower(),
                    full_name=name,
                    hashed_password="AD_MANAGED_USER",
                    is_active=is_active
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
                if db_user.is_active != is_active:
                    db_user.is_active = is_active
                    updated = True
                    
                if updated:
                    synced_count += 1
                    
        db.commit()
        return {"message": "AD users successfully synced to local database", "synced_count": synced_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Error syncing AD users: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync AD users: {str(e)}")

