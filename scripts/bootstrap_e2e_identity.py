from __future__ import annotations

import os
import sys

# Add the identity service to the path
sys.path.insert(0, "/home/avandall/project/WMS-Project-main/Services/identity-service/src")

from app.modules.users.application.services.user_service import UserService
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.auth import create_token
from app.shared.core.database import SessionLocal, init_db
from app.shared.core.settings import settings


def main() -> None:
    email = os.getenv("E2E_ADMIN_EMAIL", "gateway-e2e-admin@example.com")
    password = os.getenv("E2E_ADMIN_PASSWORD", "GatewayE2EAdmin123!")
    role = os.getenv("E2E_ADMIN_ROLE", "admin")

    # Set DATABASE_URL for the identity service
    os.environ["DATABASE_URL"] = "sqlite:////tmp/wms-identity.db"
    os.environ["SECRET_KEY"] = "wms-local-dev-secret"

    init_db()
    db = SessionLocal()
    try:
        service = UserService(UserRepo(db))
        user = service.user_repo.get_by_email(email)
        if user is None:
            user = service.create_user(
                email=email,
                password=password,
                role=role,
                full_name="Gateway E2E Admin",
            )
            db.commit()
        token = create_token(
            str(user.user_id),
            settings.access_token_expire_minutes,
            {"role": user.role},
        )
        print(token)
    finally:
        db.close()


if __name__ == "__main__":
    main()
