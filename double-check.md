1. ### Issue description
`login_auth()` references `os.getenv` before any `import os` is executed, because `os` is not imported at module level.

### Issue Context
There is an `import os` later inside the function, but it appears after `os.getenv("SECRET_KEY")`, so it cannot prevent the crash.

### Fix Focus Areas
- Add `import os` at the top of `Services/api-gateway/src/api_gateway/routes.py`.
- Optionally remove the redundant inner `import os`.

#### Files/lines
- Services/api-gateway/src/api_gateway/routes.py[1-5]
- Services/api-gateway/src/api_gateway/routes.py[57-64]

2. ### Issue description
The gateway’s `/api/{path}` handler includes hardcoded responses for permissions and change-password that bypass normal auth/routing and can mislead clients.

### Issue Context
These branches are reachable via the public `/api/{path}` route and do not validate a token (permissions) or perform any password update (change-password).

### Fix Focus Areas
- Remove these hardcoded branches and implement the endpoints in the normal router with `Depends(get_current_user)`.
- Or require Authorization for `/api/users/permissions` and delegate both operations to identity-service RPCs.
- If not implemented, return `501 Not Implemented` instead of success for change-password.

#### Files/lines
- Services/api-gateway/src/api_gateway/app.py[171-195]

3. ### Issue description
`write_transaction()` returns `int(transaction.id)` without guaranteeing that the ORM has flushed the insert, and with `auto_commit=False` the repository does not commit.

### Issue Context
`InventoryRepo` is instantiated with default `auto_commit=False` in the gRPC servicer; `_commit_if_auto()` only commits when auto-commit is enabled.

### Fix Focus Areas
- Call `self.session.flush()` after `self.session.add(transaction)` (before reading `transaction.id`).
- Alternatively, change `_commit_if_auto()` usage here to flush even when auto-commit is disabled.

#### Files/lines
- Services/inventory-service/src/app/modules/inventory/infrastructure/repositories/inventory_repo.py[495-500]
- Services/inventory-service/src/app/shared/core/transaction.py[26-42]
- Services/inventory-service/src/inventory_service/grpc_servicer.py[24-31]