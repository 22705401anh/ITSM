import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.config import settings
from app.db import SessionLocal
from app.models.settings import SystemSetting

logger = logging.getLogger(__name__)

def get_db_setting(db, key, default):
    s = db.query(SystemSetting).filter(SystemSetting.setting_key == key).first()
    return s.setting_value if (s and s.setting_value) else default

def send_email(to_email: str, subject: str, body_html: str):
    """Sends an email using the configured SMTP server."""
    
    # Fetch settings dynamically
    db = SessionLocal()
    try:
        smtp_host = get_db_setting(db, "smtp_host", settings.SMTP_HOST)
        smtp_port = int(get_db_setting(db, "smtp_port", settings.SMTP_PORT))
        smtp_user = get_db_setting(db, "smtp_user", settings.SMTP_USER)
        smtp_pass = get_db_setting(db, "smtp_password", settings.SMTP_PASSWORD)
        smtp_from = get_db_setting(db, "smtp_from", "KOSTALITSM@kostal.com")
        email_enabled = get_db_setting(db, "notif_email", "true").lower() == "true"
    finally:
        db.close()
        
    if not smtp_host:
        logger.warning(f"SMTP is not configured. Skipping email to {to_email}.")
        return False
        
    if not email_enabled:
        logger.info(f"Global email notifications are disabled. Suppressed email to {to_email}.")
        return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to_email

        part = MIMEText(body_html, "html")
        msg.attach(part)

        logger.info(f"Connecting to SMTP server at {smtp_host}:{smtp_port}...")
        
        # Connect to SMTP
        server = smtplib.SMTP(smtp_host, smtp_port)
        
        # Identify ourselves, prompting server for supported features
        server.ehlo()
        
        # If we can encrypt this session, do it
        if server.has_extn('STARTTLS'):
            server.starttls()
            server.ehlo() # re-identify ourselves over TLS connection
            
        # Login if credentials are provided
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
            
        # Send email
        server.sendmail(smtp_from, to_email, msg.as_string())
        server.quit()
        
        logger.info(f"Successfully sent email to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
        return False

def send_manager_approval_email(manager_email: str, manager_name: str, request_id: int, employee_name: str):
    """Helper to send the onboarding approval notification."""
    if not manager_email:
        logger.warning(f"No manager email provided for request #{request_id}, skipping email.")
        return False
        
    subject = f"Action Required: IT Onboarding Approval for {employee_name}"
    
    # We construct a direct link to the approval portal (or the specific request ID if the portal supports it)
    # Right now, assuming the ITSM runs on the server hostname.
    approval_url = f"http://localhost:8000/onboarding" # In production, use a config variable for APP_URL
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #0d6efd;">IT Onboarding Request Approval</h2>
        <p>Hello <strong>{manager_name or 'Manager'}</strong>,</p>
        <p>A new HR onboarding request has been submitted for <strong>{employee_name}</strong>.</p>
        <p>As their Direct Manager, you are required to approve the request and select the necessary IT hardware and software access.</p>
        <br>
        <a href="{approval_url}" style="background-color: #0d6efd; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">Review and Approve</a>
        <br><br>
        <p>If the button above doesn't work, please navigate to the KOSTAL ITSM Portal -> HR Services -> Onboarding Dashboard.</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #777;">This is an automated message from the KOSTAL ITSM system.</p>
      </body>
    </html>
    """
    
    return send_email(manager_email, subject, html)
