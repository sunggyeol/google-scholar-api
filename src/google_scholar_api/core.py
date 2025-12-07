from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from .models import GoogleScholarResponse, SearchParameters

class ScraperBackend(ABC):
    @abstractmethod
    def search(self, params: SearchParameters) -> GoogleScholarResponse:
        pass

class GoogleScholar:
    def __init__(self, backend: str = 'selenium'):
        self.backend_name = backend
        self._backend = self._load_backend(backend)

    def _load_backend(self, backend_name: str) -> ScraperBackend:
        if backend_name == 'selenium':
            from .backends.selenium_backend import SeleniumBackend
            return SeleniumBackend()
        else:
            raise ValueError(f"Unknown backend: {backend_name}. Only 'selenium' is supported.")

    def search(self, 
               engine: str = "google_scholar", 
               q: Optional[str] = None, 
               **kwargs) -> GoogleScholarResponse:
        """
        Generic search entry point mirroring SearchApi.
        """
        params = SearchParameters(engine=engine, q=q, **kwargs)
        return self._backend.search(params)

    # --- Convenience Wrappers ---

    def search_scholar(self, query: str, **kwargs) -> GoogleScholarResponse:
        """
        Search for publications.
        """
        return self.search(engine="google_scholar", q=query, **kwargs)

    def search_author(self, author_id: str, **kwargs) -> GoogleScholarResponse:
        """
        Search for author details.
        """
        return self.search(engine="google_scholar_author", author_id=author_id, **kwargs)

    def search_cite(self, data_cid: str, **kwargs) -> GoogleScholarResponse:
        """
        Get citations for a specific article.
        """
        return self.search(engine="google_scholar_cite", data_cid=data_cid, **kwargs)
