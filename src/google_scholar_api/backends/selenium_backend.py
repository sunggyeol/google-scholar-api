from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from typing import List
import time
import urllib.parse
from datetime import datetime

from ..core import ScraperBackend
from ..models import (
    GoogleScholarResponse, SearchParameters, SearchMetadata, SearchInformation,
    OrganicResult, Author, Resource, InlineLinks, AuthorProfile, AuthorAffiliation,
    CoAuthor, Pagination, Article
)
from ..utils import random_sleep, random_sleep_long

class SeleniumBackend(ScraperBackend):
    BASE_URL = "https://scholar.google.com"

    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        # chrome_options.add_argument("--headless") 
        
        service = None
        
        # Check for ARM64 Linux (Jetson/Raspberry Pi) environment to avoid Exec format error
        import platform
        import os
        
        if platform.system() == 'Linux' and platform.machine() in ('aarch64', 'arm64'):
            # Common paths for apt-installed chromedriver on Ubuntu/Debian ARM64
            system_driver_paths = [
                "/usr/bin/chromedriver",
                "/usr/lib/chromium-browser/chromedriver",
                "/usr/local/bin/chromedriver"
            ]
            for path in system_driver_paths:
                if os.path.exists(path):
                    print(f"Detected ARM64 system. Using system chromedriver at: {path}")
                    service = Service(path)
                    break
            
            if not service:
                 print("Warning: ARM64 detected but system chromedriver not found. Attempting webdriver-manager (may fail).")

        if not service:
             # Standard behavior for x86_64 Windows/Mac/Linux
             try:
                service = Service(ChromeDriverManager().install())
             except Exception as e:
                print(f"ChromeDriverManager failed: {e}. Falling back to default PATH.")
                service = Service() # Try default PATH
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def __del__(self):
        if hasattr(self, 'driver'):
            try:
                self.driver.quit()
            except:
                pass

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
             # Fallback or Todo
             raise NotImplementedError(f"Engine {params.engine} not fully implemented in Selenium backend yet.")

    def _build_url(self, params: SearchParameters, base_path: str) -> str:
        # Reuse logic? Or copy-paste. Copy paste for now to avoid mixins complexity.
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
        # NOTE: Direct profile search (view_op=search_authors) is heavily blocked by login walls.
        # We default to a robust strategy: finding the author via publication search.
        
        print(f"DEBUG: Starting Robust Profile Search for '{params.q}'...")
        
        start_time = time.time()
        
        # 1. Search Publications
        pub_params = SearchParameters(
            engine="google_scholar",
            q=params.q,
            num=10 # fetch a few to increase chance
        )
        # Use internal call to avoid recursion or dispatch loop
        pub_results = self._search_scholar(pub_params)
        
        # 2. Find matching Author ID from publication results
        found_id = None
        for res in pub_results.organic_results:
            for author in res.authors:
                # Simple name matching logic
                # Split query into parts and check if at least last name matches
                q_parts = params.q.split()
                if q_parts[-1].lower() in author.name.lower() and author.id:
                        found_id = author.id
                        break
            if found_id:
                break
        
        profiles = []
        if found_id:
            print(f"DEBUG: Found author ID via publication search: {found_id}")
            # 3. Fetch the author profile using the ID
            auth_params = SearchParameters(
                engine="google_scholar_author",
                author_id=found_id,
                hl=params.hl
            )
            try:
                auth_res = self._search_author(auth_params)
                if auth_res.author:
                    # Convert to AuthorProfile list format
                    profiles.append(auth_res.author)
            except Exception as e:
                print(f"Error fetching detailed profile for ID {found_id}: {e}")
        else:
             print(f"DEBUG: Could not find author ID for '{params.q}' in publication results.")
        
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
        
        start_time = time.time()
        self.driver.get(url)
        random_sleep()
        req_time = time.time() - start_time
        
        # Check captcha
        if "sorry" in self.driver.current_url:
             print("Block detected! Please solve captcha.")
             random_sleep_long()
        
        metadata = SearchMetadata(
             created_at=datetime.utcnow().isoformat(),
             request_time_taken=req_time,
             request_url=url
        )

        results = []
        elements = self.driver.find_elements(By.CSS_SELECTOR, '.gs_r.gs_or.gs_scl')
        
        for i, elem in enumerate(elements):
            try:
                try:
                    title_e = elem.find_element(By.CSS_SELECTOR, '.gs_rt a')
                    title = title_e.text
                    link = title_e.get_attribute('href')
                except:
                    title = elem.find_element(By.CSS_SELECTOR, '.gs_rt').text
                    link = None
                
                try:
                     snippet = elem.find_element(By.CSS_SELECTOR, '.gs_rs').text
                except:
                     snippet = None
                
                try:
                     pub_info_elem = elem.find_element(By.CSS_SELECTOR, '.gs_a')
                     pub_info = pub_info_elem.text
                     
                     # Extract authors with links
                     authors_list = []
                     for a_tag in pub_info_elem.find_elements(By.TAG_NAME, 'a'):
                         try:
                             a_link = a_tag.get_attribute('href')
                             if 'user=' in a_link:
                                 parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(a_link).query)
                                 a_id = parsed_q.get('user', [None])[0]
                                 authors_list.append(Author(name=a_tag.text, id=a_id, link=a_link))
                         except:
                             pass
                except:
                     pub_info = None
                     authors_list = []
                     
                res = OrganicResult(
                    position=i,
                    title=title,
                    link=link,
                    snippet=snippet,
                    publication_info=pub_info,
                    authors=authors_list
                )
                results.append(res)
            except Exception as e:
                print(f"Selenium parse error: {e}")

        # Pagination
        pagination = None
        try:
            pagination = Pagination(current=params.start // params.num + 1)
            # Find next button
            try:
                next_e = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]") # Simple text check
                pagination.next = next_e.get_attribute('href')
            except:
                pass
        except:
            pass

        return GoogleScholarResponse(
            search_metadata=metadata,
            search_parameters=params,
            search_information=SearchInformation(total_results=self._parse_total_results()),
            organic_results=results,
            pagination=pagination
        )

    def _parse_total_results(self):
        try:
             # Try to find the stats div
             stats_div = self.driver.find_element(By.CSS_SELECTOR, '#gs_ab_md .gs_ab_mdw')
             txt = stats_div.text
             import re
             m = re.search(r'([\d,]+)\s+results', txt)
             if m:
                 return int(m.group(1).replace(',', ''))
        except:
             return None
        return None

    def _search_author(self, params: SearchParameters) -> GoogleScholarResponse:
         url = self._build_url(params, "citations")
         start_time = time.time()
         self.driver.get(url)
         random_sleep()
         req_time = time.time() - start_time
         
         metadata = SearchMetadata(
             request_url=url,
             request_time_taken=req_time
         )
         
         try:
             name = self.driver.find_element(By.ID, 'gsc_prf_in').text
         except:
             name = "Unknown"
             
         profile = AuthorProfile(name=name, author_id=params.author_id)
         
         # Articles
         articles = []
         rows = self.driver.find_elements(By.CSS_SELECTOR, '.gsc_a_tr')
         for row in rows:
             try:
                 title_e = row.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                 title = title_e.text
                 link = title_e.get_attribute('href')
                 articles.append(OrganicResult(title=title, link=link))
             except:
                 pass
                 
         return GoogleScholarResponse(
             search_metadata=metadata,
             search_parameters=params,
             author=profile,
             articles=articles
         )

    def _search_cite(self, params: SearchParameters) -> GoogleScholarResponse:
         cid = params.q or params.cites
         url = f"{self.BASE_URL}/scholar?q=info:{cid}:scholar.google.com&output=cite&hl={params.hl}"
         
         start_time = time.time()
         self.driver.get(url)
         random_sleep()
         req_time = time.time() - start_time
         
         metadata = SearchMetadata(
             created_at=datetime.utcnow().isoformat(),
             request_time_taken=req_time,
             request_url=url
         )
         
         citations = []
         links = []
         
         try:
             # Parse table rows
             rows = self.driver.find_elements(By.CSS_SELECTOR, '#gs_citt tr')
             for row in rows:
                 title = row.find_element(By.CSS_SELECTOR, '.gs_cith').text
                 snippet = row.find_element(By.CSS_SELECTOR, '.gs_citr').text
                 citations.append({"title": title, "snippet": snippet})
                 
             # Parse links
             link_elems = self.driver.find_elements(By.CSS_SELECTOR, '.gs_citi a')
             for le in link_elems:
                 links.append({
                     "title": le.text,
                     "link": le.get_attribute('href')
                 })
         except Exception as e:
             print(f"Selenium cite parse error: {e}")
             
         return GoogleScholarResponse(
             search_metadata=metadata,
             search_parameters=params,
             citations=citations,
             links=links
         )


