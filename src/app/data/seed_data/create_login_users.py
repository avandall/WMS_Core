#!/usr/bin/env python3
"""
Create users with known passwords for dashboard login.
"""

import os
import sys
import bcrypt
from sqlalchemy import create_engine, text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../'))

try:
    from app.core.settings import settings
except ImportError:
    print("Error: Could not import WMS settings.")
    sys.exit(1)

def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_login_users():
    """Create users with known passwords."""
    try:
        # Connect to database
        engine = create_engine(settings.database_url)
        
        # Define users with known passwords (using valid system roles)
        users_with_passwords = [
            ('admin@wms.vn', 'admin123', 'admin', 'Administrator', 1),
            ('warehouse@wms.vn', 'warehouse123', 'warehouse', 'Warehouse Manager', 1),
            ('sales@wms.vn', 'sales123', 'sales', 'Sales Staff', 1),
            ('accountant@wms.vn', 'account123', 'accountant', 'Accountant', 1),
        ]
        
        with engine.connect() as conn:
            # Clear existing users
            print("🗑️  Clearing existing users...")
            conn.execute(text("DELETE FROM users"))
            conn.commit()
            
            # Insert users with known passwords
            print("👥 Creating users with known passwords...")
            for email, password, role, full_name, is_active in users_with_passwords:
                hashed_pwd = hash_password(password)
                conn.execute(text("""
                    INSERT INTO users (email, hashed_password, role, full_name, is_active, created_at) 
                    VALUES (:email, :hashed_password, :role, :full_name, :is_active, NOW())
                """), {
                    "email": email,
                    "hashed_password": hashed_pwd,
                    "role": role,
                    "full_name": full_name,
                    "is_active": is_active
                })
                print(f"  ✅ Created user: {email} (password: {password})")
            
            conn.commit()
        
        print("\n🎉 Login credentials created successfully!")
        print("\n📋 Dashboard Login Credentials:")
        print("┌─────────────────────┬─────────────────┬─────────────────┐")
        print("│ Email                │ Password        │ Role            │")
        print("├─────────────────────┼─────────────────┼─────────────────┤")
        print("│ admin@wms.vn         │ admin123        │ Administrator   │")
        print("│ warehouse@wms.vn     │ warehouse123    │ Warehouse       │")
        print("│ sales@wms.vn         │ sales123        │ Sales           │")
        print("│ accountant@wms.vn    │ account123      │ Accountant      │")
        print("└─────────────────────┴─────────────────┴─────────────────┘")
        
        print(f"\n🌐 Dashboard URL: http://localhost:8080")
        print("🔑 Use any of the above credentials to login!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating login users: {e}")
        return False

if __name__ == '__main__':
    create_login_users()
