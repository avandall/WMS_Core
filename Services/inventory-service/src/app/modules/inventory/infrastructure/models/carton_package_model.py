"""Re-export carton package and manifest models for inventory-service compatibility."""

from app.modules.documents.infrastructure.models.carton_package import (
    CartonPackageModel,
    CartonManifestItemModel,
)

__all__ = ["CartonPackageModel", "CartonManifestItemModel"]
