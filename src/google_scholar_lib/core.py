from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .backends.pool import SeleniumBackendPool

from .models import GoogleScholarResponse, SearchParameters

class ScraperBackend(ABC):
    @abstractmethod
    async def search(self, params: SearchParameters) -> GoogleScholarResponse:
        pass

class GoogleScholar:
    def __init__(self, backend: str = 'selenium', pool: Optional['SeleniumBackendPool'] = None):
        """
        Initialize GoogleScholar client.

        Args:
            backend: Backend name (only 'selenium' supported)
            pool: Optional SeleniumBackendPool instance for pooled mode
        """
        self.backend_name = backend
        self.pool = pool
        self._backend = self._load_backend(backend, pool)

    def _load_backend(self, backend_name: str, pool: Optional['SeleniumBackendPool'] = None) -> ScraperBackend:
        """
        Load the specified backend.

        Args:
            backend_name: Name of backend to load
            pool: Optional pool instance to pass to backend

        Returns:
            ScraperBackend instance
        """
        if backend_name == 'selenium':
            from .backends.selenium_backend import SeleniumBackend
            return SeleniumBackend(pool=pool)
        else:
            raise ValueError(f"Unknown backend: {backend_name}. Only 'selenium' is supported.")

    async def search(self,
                    engine: str = "google_scholar",
                    q: Optional[str] = None,
                    **kwargs) -> GoogleScholarResponse:
        """
        Generic search entry point mirroring SearchApi.
        Now async to support pool-based backends.
        """
        params = SearchParameters(engine=engine, q=q, **kwargs)
        return await self._backend.search(params)

    # --- Convenience Wrappers ---

    async def search_scholar(self, query: str, **kwargs) -> GoogleScholarResponse:
        """
        Search for publications.
        """
        return await self.search(engine="google_scholar", q=query, **kwargs)

    async def search_author(self, author_id: str, **kwargs) -> GoogleScholarResponse:
        """
        Search for author details.
        """
        return await self.search(engine="google_scholar_author", author_id=author_id, **kwargs)

    async def search_cite(self, data_cid: str, **kwargs) -> GoogleScholarResponse:
        """
        Get citations for a specific article.
        """
        return await self.search(engine="google_scholar_cite", data_cid=data_cid, **kwargs)
