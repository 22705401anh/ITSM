from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models.user import User

def revoke_ad_access():
    db = SessionLocal()
    try:
        # Find all AD users who currently have access
        ad_users = db.query(User).filter(User.hashed_password == "AD_MANAGED_USER", User.is_active == True).all()
        count = len(ad_users)
        
        for user in ad_users:
            user.is_active = False
            
        db.commit()
        print(f"Successfully revoked access for {count} AD users.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    revoke_ad_access()
