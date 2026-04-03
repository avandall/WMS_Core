"""Application utilities (compatibility).

These helpers were present in `src-old/app/utils/application`.
They are currently not part of the clean-architecture "core" but are kept as
small, dependency-free helpers for transitional code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generic, List, TypeVar

from app.core.exceptions import ApplicationError

T = TypeVar("T")


@dataclass
class PaginatedResult(Generic[T]):
    items: List[T]
    total_count: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class PaginationUtils:
    @staticmethod
    def paginate_list(items: List[T], page: int = 1, page_size: int = 10) -> PaginatedResult[T]:
        if page < 1:
            raise ApplicationError("Page must be >= 1")
        if page_size < 1:
            raise ApplicationError("Page size must be >= 1")

        total_count = len(items)
        total_pages = (total_count + page_size - 1) // page_size

        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        return PaginatedResult(
            items=items[start_index:end_index],
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @staticmethod
    def validate_pagination_params(page: int, page_size: int, max_page_size: int = 100) -> None:
        if page < 1:
            raise ApplicationError("Page must be >= 1")
        if page_size < 1 or page_size > max_page_size:
            raise ApplicationError(f"Page size must be between 1 and {max_page_size}")


class SortingUtils:
    @staticmethod
    def sort_by_field(items: List[Dict[str, Any]], field: str, reverse: bool = False) -> List[Dict[str, Any]]:
        return sorted(items, key=lambda x: x.get(field, ""), reverse=reverse)

    @staticmethod
    def sort_by_attribute(items: List[T], attribute: str, reverse: bool = False) -> List[T]:
        return sorted(items, key=lambda x: getattr(x, attribute, ""), reverse=reverse)


class FilterUtils:
    @staticmethod
    def filter_by_field(items: List[Dict[str, Any]], field: str, value: Any) -> List[Dict[str, Any]]:
        return [item for item in items if item.get(field) == value]

    @staticmethod
    def filter_by_condition(items: List[T], condition_func) -> List[T]:
        return [item for item in items if condition_func(item)]


class SearchUtils:
    @staticmethod
    def search_text(
        items: List[Dict[str, Any]],
        search_field: str,
        query: str,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        if not case_sensitive:
            query = query.lower()

        def matches(item: Dict[str, Any]) -> bool:
            value = str(item.get(search_field, ""))
            if not case_sensitive:
                value = value.lower()
            return query in value

        return [item for item in items if matches(item)]

    @staticmethod
    def search_multiple_fields(
        items: List[Dict[str, Any]],
        fields: List[str],
        query: str,
        case_sensitive: bool = False,
    ) -> List[Dict[str, Any]]:
        if not case_sensitive:
            query = query.lower()

        def matches(item: Dict[str, Any]) -> bool:
            for field in fields:
                value = str(item.get(field, ""))
                if not case_sensitive:
                    value = value.lower()
                if query in value:
                    return True
            return False

        return [item for item in items if matches(item)]


__all__ = [
    "PaginatedResult",
    "PaginationUtils",
    "SortingUtils",
    "FilterUtils",
    "SearchUtils",
]
