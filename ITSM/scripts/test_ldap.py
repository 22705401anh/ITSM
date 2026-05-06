from ldap3 import Server, Connection, ALL, SUBTREE
import os
from dotenv import load_dotenv

load_dotenv()

LDAP_SERVER = os.environ.get("LDAP_SERVER")
LDAP_BIND_DN = os.environ.get("LDAP_BIND_DN")
LDAP_PASSWORD = os.environ.get("LDAP_PASSWORD")

print(f"Testing LDAP connection to {LDAP_SERVER} on Global Catalog port 3268...")

try:
    server = Server(LDAP_SERVER, port=3268, get_info=ALL)
    conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_PASSWORD, auto_bind=True)
    
    # Global Catalog search base can be empty or the root of the forest
    search_base = "DC=kostal,DC=int"
    search_filter = '(&(objectClass=user)(objectCategory=person)(sAMAccountName=bouzk001))'
    
    print(f"Searching base {search_base}...")
    conn.search(search_base, search_filter, search_scope=SUBTREE, attributes=['sAMAccountName', 'displayName', 'mail'])
    
    for entry in conn.entries:
        print(f"Found: {entry.sAMAccountName} - {entry.displayName} - {entry.mail}")
        
    print(f"Total found: {len(conn.entries)}")
except Exception as e:
    print(f"Error: {e}")
