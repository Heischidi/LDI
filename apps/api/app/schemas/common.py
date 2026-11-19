"""Shared pagination and response envelope schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Consistent paginated API list response."""

    items: list[T]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """Simple confirmation message response."""

    message: str
    detail: str | None = None
