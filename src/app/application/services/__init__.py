"""Application services package.

Avoid eager imports here to prevent pulling runtime infrastructure/config
dependencies at import time. Import concrete services from their modules:
`from app.application.services.product_service import ProductService`.
"""

__all__: list[str] = []
