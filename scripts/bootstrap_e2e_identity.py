from __future__ import annotations

import os

from app.modules.users.application.services.user_service import UserService
from app.modules.users.infrastructure.repositories.user_repo import UserRepo
from app.shared.core.auth import create_token
from app.shared.core.database import SessionLocal, init_db
from app.shared.core.settings import settings


def main() -> None:
    email = os.getenv("E2E_ADMIN_EMAIL", "phase9-admin@example.com")
    password = os.getenv("E2E_ADMIN_PASSWORD", "Phase9Admin123!")
    role = os.getenv("E2E_ADMIN_ROLE", "admin")

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
                full_name="Phase 9 E2E Admin",
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
