from __future__ import annotations

import os
import uvicorn


def main() -> None:
    workers = int(os.getenv("UVICORN_WORKERS", "1"))
    if workers > 1:
        # Khi dùng workers > 1, uvicorn bắt buộc nhận import string để load app trong từng worker process
        uvicorn.run(
            "api_gateway.app:create_app",
            factory=True,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            workers=workers,
        )
    else:
        from api_gateway.app import create_app
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()

