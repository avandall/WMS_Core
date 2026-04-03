#!/usr/bin/env python3
"""
Show current login credentials for the WMS dashboard.
"""

print("🎯 WMS Dashboard Login Credentials")
print("=" * 50)
print("🌐 Dashboard URL: http://localhost:8080")
print()
print("📋 Available Users:")
print("┌─────────────────────┬─────────────────┬─────────────────┐")
print("│ Email                │ Password        │ Role            │")
print("├─────────────────────┼─────────────────┼─────────────────┤")
print("│ admin@wms.vn         │ admin123        │ Administrator   │")
print("│ warehouse@wms.vn     │ warehouse123    │ Warehouse       │")
print("│ sales@wms.vn         │ sales123        │ Sales           │")
print("│ accountant@wms.vn    │ account123      │ Accountant      │")
print("└─────────────────────┴─────────────────┴─────────────────┘")
print()
print("🔑 Recommended: Use 'admin@wms.vn' with 'admin123' for full access")
print()
print("💡 If you need to reset passwords, run:")
print("   docker compose exec api python /app/src/app/data/seed_data/create_login_users.py")
