from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

# --- Shared Models ---

class SearchMetadata(BaseModel):
    id: Optional[str] = None
    status: str = "Success"
    created_at: Optional[str] = None
    request_time_taken: Optional[float] = None
    parsing_time_taken: Optional[float] = None
    total_time_taken: Optional[float] = None
    request_url: Optional[str] = None
    html_url: Optional[str] = None
    json_url: Optional[str] = None

class SearchParameters(BaseModel):
    engine: str
    q: Optional[str] = None
    cites: Optional[str] = None
    cluster: Optional[str] = None
    author_id: Optional[str] = None
    hl: str = "en"
    lr: Optional[str] = None
    google_domain: str = "google.com"
    # Other filters
    as_ylo: Optional[str] = None
    as_yhi: Optional[str] = None
    scisbd: Optional[int] = None # Sort by date
    as_vis: Optional[int] = None # exclude citations
    as_sdt: Optional[str] = None
    start: int = 0
    num: int = 10

class SearchInformation(BaseModel):
    total_results: Optional[int] = None
    time_taken_displayed: Optional[float] = None
    query_displayed: Optional[str] = None
    page: int = 1

class Pagination(BaseModel):
    current: int = 1
    next: Optional[str] = None
    other_pages: Dict[str, str] = {}

# --- Google Scholar Engine Models ---

class InlineLinks(BaseModel):
    cited_by: Optional[Dict[str, Any]] = None # {cites_id, total, link}
    related_articles_link: Optional[str] = None
    versions: Optional[Dict[str, Any]] = None # {cluster_id, total, link}
    cached_page_link: Optional[str] = None
    cite_link: Optional[str] = None # Link to open citation modal

class Resource(BaseModel):
    name: Optional[str] = None
    format: Optional[str] = None # PDF, HTML
    link: Optional[str] = None

class Author(BaseModel):
    name: str
    id: Optional[str] = None
    link: Optional[str] = None

class OrganicResult(BaseModel):
    position: Optional[int] = None
    title: str
    link: Optional[str] = None
    result_id: Optional[str] = None # data-cid
    publication_info: Optional[str] = None
    snippet: Optional[str] = None
    resources: List[Resource] = []
    authors: List[Author] = []
    inline_links: Optional[InlineLinks] = None
    cited_by_count: int = 0 # Helper for simplified view

# Backward compatibility / Alias
Article = OrganicResult

# --- Google Scholar Author Engine Models ---

class AuthorAffiliation(BaseModel):
    title: str # e.g. "machine learning"
    link: Optional[str] = None

class AuthorProfile(BaseModel):
    name: str
    author_id: Optional[str] = None
    affiliations: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    thumbnail: Optional[str] = None
    interests: List[AuthorAffiliation] = []
    cited_by: Optional[Dict[str, Any]] = None # Statistics table

class CoAuthor(BaseModel):
    name: str
    author_id: Optional[str] = None
    affiliation: Optional[str] = None
    link: Optional[str] = None
    thumbnail: Optional[str] = None

# --- Main Combine Response ---

class GoogleScholarResponse(BaseModel):
    search_metadata: SearchMetadata
    search_parameters: SearchParameters
    search_information: Optional[SearchInformation] = None
    organic_results: List[OrganicResult] = []
    # For Author Engine
    author: Optional[AuthorProfile] = None
    articles: List[OrganicResult] = [] # Author articles
    co_authors: List[CoAuthor] = []
    # For Profiles Engine (Author Search)
    profiles: List[AuthorProfile] = []
    # For Cite Engine / Bibtex
    citations: List[Dict[str, str]] = [] # e.g. [{"title": "MLA", "snippet": "..."}]
    links: List[Dict[str, str]] = [] # e.g. BibTeX link
    pagination: Optional[Pagination] = None
