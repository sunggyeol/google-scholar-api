import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
import urllib.parse
from datetime import datetime
import time

from ..core import ScraperBackend
from ..models import (
    GoogleScholarResponse, SearchParameters, SearchMetadata, SearchInformation,
    OrganicResult, Author, Resource, InlineLinks, AuthorProfile, AuthorAffiliation,
    CoAuthor, Pagination, Article
)
from ..utils import get_random_user_agent, random_sleep

class RequestsBackend(ScraperBackend):
    BASE_URL = "https://scholar.google.com"

    def _get_soup(self, url: str):
        headers = {'User-Agent': get_random_user_agent()}
        random_sleep()
        start_time = time.time()
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return None, 0, 0
            
        request_time = time.time() - start_time
        soup = BeautifulSoup(response.text, 'html.parser')
        parsing_time = time.time() - start_time - request_time
        return soup, request_time, parsing_time

    def search(self, params: SearchParameters) -> GoogleScholarResponse:
        if params.engine == "google_scholar":
            return self._search_scholar(params)
        elif params.engine == "google_scholar_author":
            return self._search_author(params)
        elif params.engine == "google_scholar_cite":
            return self._search_cite(params)
        elif params.engine == "google_scholar_profiles":
            return self._search_profiles(params)
        else:
            raise ValueError(f"Unsupported engine: {params.engine}")

    def _build_url(self, params: SearchParameters, base_path: str) -> str:
        query_params = {}
        if params.q: query_params['q'] = params.q
        if params.cites: query_params['cites'] = params.cites
        if params.cluster: query_params['cluster'] = params.cluster
        if params.hl: query_params['hl'] = params.hl
        if params.lr: query_params['lr'] = params.lr
        if params.as_ylo: query_params['as_ylo'] = params.as_ylo
        if params.as_yhi: query_params['as_yhi'] = params.as_yhi
        if params.scisbd: query_params['scisbd'] = params.scisbd
        if params.as_vis: query_params['as_vis'] = params.as_vis
        if params.as_sdt: query_params['as_sdt'] = params.as_sdt
        if params.start > 0: query_params['start'] = params.start
        if params.author_id: query_params['user'] = params.author_id
        
        # For profiles engine
        if params.engine == "google_scholar_profiles":
             # Override or add mauthors
             query_params['view_op'] = 'search_authors'
             query_params['mauthors'] = params.q
             if 'q' in query_params: del query_params['q']

        return f"{self.BASE_URL}/{base_path}?{urllib.parse.urlencode(query_params)}"

    def _search_profiles(self, params: SearchParameters) -> GoogleScholarResponse:
        # Robust Strategy: Skip search_authors (blocked) and go straight to finding author via publication search.
        print(f"DEBUG(Requests): Starting Robust Profile Search for '{params.q}'...")
        
        start_time = time.time()
        
        # 1. Search Publications
        pub_params = SearchParameters(
            engine="google_scholar",
            q=params.q,
            num=10
        )
        pub_results = self._search_scholar(pub_params)
        
        # 2. Find matching Author ID
        found_id = None
        if pub_results and pub_results.organic_results:
            for res in pub_results.organic_results:
                    for author in res.authors:
                        q_parts = params.q.split()
                        if q_parts[-1].lower() in author.name.lower() and author.id:
                            found_id = author.id
                            break
                    if found_id:
                        break
        
        profiles = []
        if found_id:
            print(f"DEBUG(Requests): Found author ID: {found_id}")
            auth_params = SearchParameters(
                engine="google_scholar_author",
                author_id=found_id,
                hl=params.hl
            )
            try:
                auth_res = self._search_author(auth_params)
                if auth_res.author:
                    profiles.append(auth_res.author)
            except Exception as e:
                print(f"Error fetching detailed profile for ID {found_id}: {e}")
        else:
             print(f"DEBUG(Requests): Could not find author ID for '{params.q}' in publication results.")

        req_time = time.time() - start_time
        metadata = SearchMetadata(
             created_at=datetime.utcnow().isoformat(),
             request_time_taken=req_time,
             request_url=f"robust_search({params.q})"
        )

        return GoogleScholarResponse(
            search_metadata=metadata,
            search_parameters=params,
            profiles=profiles
        )

    def _search_scholar(self, params: SearchParameters) -> GoogleScholarResponse:
        url = self._build_url(params, "scholar")
        soup, req_time, parse_time = self._get_soup(url)
        
        metadata = SearchMetadata(
            created_at=datetime.utcnow().isoformat(),
            request_time_taken=req_time,
            parsing_time_taken=parse_time,
            total_time_taken=req_time+parse_time,
            request_url=url
        )

        if not soup:
            return GoogleScholarResponse(search_metadata=metadata, search_parameters=params)

        # Parse organic results
        results = []
        for i, res in enumerate(soup.select('.gs_r.gs_or.gs_scl')):
            try:
                title_tag = res.select_one('.gs_rt a')
                title = title_tag.get_text() if title_tag else res.select_one('.gs_rt').get_text()
                link = title_tag['href'] if title_tag else None
                data_cid = res.get('data-cid')
                
                snippet = res.select_one('.gs_rs').get_text() if res.select_one('.gs_rs') else None
                pub_info_tag = res.select_one('.gs_a')
                pub_info = pub_info_tag.get_text() if pub_info_tag else None
                
                authors_list = []
                if pub_info_tag:
                    for a_tag in pub_info_tag.select('a'):
                        try:
                            a_link = f"{self.BASE_URL}{a_tag['href']}"
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(a_link).query)
                            a_id = parsed.get('user', [None])[0]
                            authors_list.append(Author(name=a_tag.get_text(), id=a_id, link=a_link))
                        except:
                            pass

                # Inline links
                inline = InlineLinks()
                cited_by_tag = res.find('a', string=lambda t: t and 'Cited by' in t)
                if cited_by_tag:
                    cites_id = urllib.parse.parse_qs(urllib.parse.urlparse(cited_by_tag['href']).query).get('cites', [None])[0]
                    inline.cited_by = {
                        'total': int(cited_by_tag.get_text().split()[-1]),
                        'link': f"{self.BASE_URL}{cited_by_tag['href']}",
                        'cites_id': cites_id
                    }
                
                related_tag = res.find('a', string=lambda t: t and 'Related articles' in t)
                if related_tag:
                    inline.related_articles_link = f"{self.BASE_URL}{related_tag['href']}"
                    
                versions_tag = res.find('a', string=lambda t: t and 'versions' in t)
                if versions_tag:
                     cluster_id = urllib.parse.parse_qs(urllib.parse.urlparse(versions_tag['href']).query).get('cluster', [None])[0]
                     inline.versions = {
                         'total': int(versions_tag.get_text().split()[1]),
                         'link': f"{self.BASE_URL}{versions_tag['href']}",
                         'cluster_id': cluster_id
                     }

                results.append(OrganicResult(
                    position=i,
                    title=title,
                    link=link,
                    result_id=data_cid,
                    snippet=snippet,
                    publication_info=pub_info,
                    authors=authors_list,
                    inline_links=inline
                ))
            except Exception as e:
                print(f"Error parsing result {i}: {e}")

        # Parse Total Results (approx)
        total_results = None
        stats_div = soup.select_one('#gs_ab_md .gs_ab_mdw')
        if stats_div:
             txt = stats_div.get_text()
             import re
             m = re.search(r'([\d,]+)\s+results', txt)
             if m:
                 total_results = int(m.group(1).replace(',', ''))

        # Parse Pagination
        pagination = None
        if soup:
            pagination = Pagination(current=params.start // params.num + 1)
            # Find next button
            # Note: logic for next button is tricky because text might vary by language
            next_tag = soup.find('a', string=lambda t: t and 'Next' in t)
            if not next_tag:
                 # fallback to icon span check
                 next_icon = soup.select_one('.gs_ico_nav_next')
                 if next_icon and next_icon.parent.name == 'a':
                     next_tag = next_icon.parent

            if next_tag and next_tag.has_attr('href'):
                pagination.next = f"{self.BASE_URL}{next_tag['href']}"
            
            # Other pages
            other_pages = {}
            for p_tag in soup.select('#gs_n td a'):
                page_num = p_tag.get_text()
                if page_num and page_num.isdigit():
                     other_pages[page_num] = f"{self.BASE_URL}{p_tag['href']}"
            pagination.other_pages = other_pages

        return GoogleScholarResponse(
            search_metadata=metadata,
            search_parameters=params,
            search_information=SearchInformation(total_results=total_results),
            organic_results=results,
            pagination=pagination
        )

    def _search_author(self, params: SearchParameters) -> GoogleScholarResponse:
        url = self._build_url(params, "citations")
        
        soup, req_time, parse_time = self._get_soup(url)
        metadata = SearchMetadata(
            created_at=datetime.utcnow().isoformat(),
            request_time_taken=req_time,
            parsing_time_taken=parse_time,
            total_time_taken=req_time+parse_time,
            request_url=url
        )
        
        if not soup:
             return GoogleScholarResponse(search_metadata=metadata, search_parameters=params)
             
        # Extract Author Profile
        name = soup.select_one('#gsc_prf_in').get_text() if soup.select_one('#gsc_prf_in') else "Unknown"
        aff = soup.select_one('.gsc_prf_il').get_text() if soup.select_one('.gsc_prf_il') else None
        
        interests = []
        for int_tag in soup.select('#gsc_prf_int a'):
            interests.append(AuthorAffiliation(title=int_tag.get_text(), link=f"{self.BASE_URL}{int_tag['href']}"))
            
        profile = AuthorProfile(
            name=name,
            author_id=params.author_id,
            affiliations=aff,
            interests=interests
        )

        # Extract Articles
        articles = []
        for row in soup.select('.gsc_a_tr'):
             title_tag = row.select_one('.gsc_a_t a')
             title = title_tag.get_text()
             link = f"{self.BASE_URL}{title_tag['href']}"
             pub = row.select_one('.gsc_a_at+ .gs_gray').get_text() # approx
             
             articles.append(OrganicResult(
                 title=title,
                 link=link,
                 publication_info=pub,
             ))

        return GoogleScholarResponse(
            search_metadata=metadata,
            search_parameters=params,
            author=profile,
            articles=articles
        )

    def _search_cite(self, params: SearchParameters) -> GoogleScholarResponse:
        cid = params.q or params.cites 
        url = f"{self.BASE_URL}/scholar?q=info:{cid}:scholar.google.com&output=cite&hl={params.hl}"
        
        soup, req_time, parse_time = self._get_soup(url)
        metadata = SearchMetadata(
            created_at=datetime.utcnow().isoformat(),
            request_time_taken=req_time,
            parsing_time_taken=parse_time,
            total_time_taken=req_time+parse_time,
            request_url=url
        )

        if not soup:
             return GoogleScholarResponse(search_metadata=metadata, search_parameters=params)

        citations = []
        links = []

        # Parse output=cite content
        for row in soup.select('#gs_citt tr'):
            try:
                title = row.select_one('.gs_cith').get_text(strip=True)
                snippet = row.select_one('.gs_citr').get_text(strip=True)
                citations.append({"title": title, "snippet": snippet})
            except:
                pass

        # Parse links (BibTeX, EndNote, etc)
        for link_tag in soup.select('.gs_citi a'):
            links.append({
                "title": link_tag.get_text(strip=True),
                "link": link_tag['href']
            })

        return GoogleScholarResponse(
            search_metadata=metadata,
            search_parameters=params,
            citations=citations,
            links=links
        )
