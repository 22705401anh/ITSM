from sqlalchemy.orm import Session
from app.models.settings import SystemSetting
from app.config import settings

def get_ldap_config(db: Session) -> dict:
    """Fetch LDAP settings from the database, falling back to environment variables."""
    def get_setting(key, default):
        s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
        return s.setting_value if s else default

    return {
        "server": get_setting("ldap_server", settings.LDAP_SERVER),
        "port": int(get_setting("ldap_port", settings.LDAP_PORT)),
        "base_dn": get_setting("ldap_base_dn", settings.LDAP_BASE_DN),
        "bind_dn": get_setting("ldap_bind_dn", settings.LDAP_BIND_DN),
        "password": get_setting("ldap_password", settings.LDAP_PASSWORD)
    }
