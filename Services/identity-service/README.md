# Identity Service

Scaffold ban đầu cho Identity Service.

Phạm vi extract (Phase 1):
- Auth (login/refresh, token)
- Users
- Roles/permissions (thông qua user role + permissions helpers)

Nguồn code hiện tại (monolith):
- `Services/wms-monolith/src/app/api/v1/endpoints/auth.py`
- `Services/wms-monolith/src/app/api/v1/endpoints/users/`
- `Services/wms-monolith/src/app/modules/users/`
