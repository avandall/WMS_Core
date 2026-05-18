from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from app.modules.documents.domain.entities.document import Document, DocumentStatus


class IDocumentRepo(ABC):
    @abstractmethod
    def save(self, document: "Document") -> None:
        pass

    @abstractmethod
    def get(self, document_id: int) -> Optional["Document"]:
        pass

    @abstractmethod
    def get_all(self) -> List["Document"]:
        pass

    @abstractmethod
    def update_status(self, document_id: int, new_status: "DocumentStatus") -> None:
        pass

    @abstractmethod
    def delete(self, document_id: int) -> None:
        pass


# Alias for backward compatibility
DocumentRepo = IDocumentRepo
