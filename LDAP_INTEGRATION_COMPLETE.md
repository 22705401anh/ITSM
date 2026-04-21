# Active Directory / LDAP Integration Added!

I have built the live Active Directory Users page you requested using the `ldap3` library to communicate directly with your LDAP server.

## What's Changed
1. **Added the `ldap3` dependency** (`pip install ldap3`).
2. **Configuration Setup**: Added your LDAP credentials (`MAGEAD101.ma.kostal.int`) into your backend configuration. 
3. **Backend Service**: Created a new endpoint (`/api/admin/ad-users`) in `ITSM/app/api/admin.py` that connects, binds, and searches Active Directory for active users in real-time.
4. **Frontend View**: Built `ad_users.html` which creates a beautiful, searchable table displaying users dynamically queried straight from AD.

## Important Step - Add Config to `.env`
Open your `ITSM/.env` file and paste the following at the bottom. **Without this, the connection will fail!**

```ini
# LDAP Integration
LDAP_SERVER=ldap://MAGEAD101.ma.kostal.int
LDAP_PORT=389
LDAP_BASE_DN=DC=ma,DC=kostal,DC=int
LDAP_BIND_DN=CN=kaziz999,OU=GE,OU=USR,DC=ma,DC=kostal,DC=int
LDAP_PASSWORD=jkfnJKF#44
```

## Next Steps
Once you restart your Python server (`python ITSM.py`), you can navigate to:

?? **http://localhost:8000/admin/ad-users**

This page will:
- Connect to `ma.kostal.int`
- Securely fetch all active users
- Display their Username, Name, Email, Department, Title, and Company.
- Allow you to search through them instantly in real-time.

Please restart your server, add the variables to `.env`, and give the page a try! Let me know if you need any adjustments to the domain attributes (e.g., retrieving phone numbers or locations).