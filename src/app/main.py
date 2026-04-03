from __future__ import annotations

import uvicorn

from app.api import app
from app.core.settings import settings


def main() -> None:
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()

