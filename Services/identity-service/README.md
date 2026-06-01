# Identity Service

Scaffold ban đầu cho Identity Service.

Phạm vi extract (Phase 1):
- Auth (login/refresh, token)
- Users
- Roles/permissions (thông qua user role + permissions helpers)

Code identity hiện nằm trong service này:
- `src/app/api/v1/endpoints/auth.py`
- `src/app/api/v1/endpoints/users/`
- `src/app/modules/users/`
