"""Admin API routes including Active Directory integration."""

from fastapi import APIRouter, HTTPException
import logging
from ldap3 import Server, Connection, ALL, SUBTREE, ALL_ATTRIBUTES
from app.config import settings
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

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

            search_filter = '(&(objectClass=user)(objectCategory=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))'  # Only active users
            attributes = ['sAMAccountName', 'displayName', 'mail', 'department', 'title', 'company']

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

                users.append({
                    "username": get_attr('sAMAccountName'),
                    "name": get_attr('displayName'),
                    "email": get_attr('mail'),
                    "department": get_attr('department'),
                    "title": get_attr('title'),
                    "company": get_attr('company')
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

