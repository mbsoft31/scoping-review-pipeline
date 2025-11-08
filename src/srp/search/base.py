"""Base classes and interfaces for search adapters."""

from abc import ABC, abstractmethod
from typing import AsyncIterable, Optional
from datetime import date

from ..core.models import Paper


class SearchClient(ABC):
    """Abstract base class for all search adapters."""

    def __init__(self, config: dict):
        self.config = config
        self.source_name = self.__class__.__name__.replace("Client", "").lower()

    @abstractmethod
    async def search(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None,
    ) -> AsyncIterable[Paper]:
        """
        Execute search and yield papers.

        Args:
            query: Search query string
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Maximum number of papers to retrieve
            cursor: Pagination cursor (for cursor-based pagination)
            page: Page number (for offset-based pagination)

        Yields:
            Paper objects
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name}>"