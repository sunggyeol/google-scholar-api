from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import urllib.parse
from datetime import datetime
import os
import random
import platform
import shutil

from ..core import ScraperBackend
from ..models import (
    GoogleScholarResponse, SearchParameters, SearchMetadata, SearchInformation,
    OrganicResult, Author, Pagination, AuthorProfile
)
from ..utils import random_sleep, random_sleep_long

class SeleniumBackend(ScraperBackend):
    BASE_URL = "https://scholar.google.com"

    def __init__(self, headless: bool = True):
        chrome_options = Options()

        # --- 1. DETECT ARCHITECTURE ---
        # Cloud is 'x86_64', Jetson is 'aarch64'
        arch = platform.machine()
        is_arm = arch in ('aarch64', 'arm64')
        
        # --- 2. STABILITY FLAGS (Universal) ---
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-software-rasterizer")
        
        # Memory Saver (Crucial for 1GB Cloud RAM & Shared Jetson RAM)
        chrome_options.add_argument("--js-flags=--max-old-space-size=512")
        
        # --- 3. ANTI-BLOCKING ---
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        if headless:
            chrome_options.add_argument("--headless=new")

        # --- 4. DRIVER SETUP (Auto-Switching) ---
        service = None
        
        # Define paths based on OS
        if is_arm:
            # === JETSON / ARM CONFIG ===
            print(f"DEBUG: ARM64 Architecture detected ({arch}). Using Jetson paths.")
            
            # Jetson usually puts Chromium here
            possible_drivers = [
                "/usr/lib/chromium-browser/chromedriver",  # Standard Ubuntu ARM
                "/usr/bin/chromedriver",
                "/snap/bin/chromium.chromedriver"
            ]
            
            # On Jetson, we often MUST tell Selenium where the browser binary is
            browser_bin = "/usr/bin/chromium-browser"
            if os.path.exists(browser_bin):
                chrome_options.binary_location = browser_bin
                
        else:
            # === CLOUD / x86 CONFIG ===
            print(f"DEBUG: x86_64 Architecture detected ({arch}). Using Cloud paths.")
            
            # Standard Debian Cloud path
            possible_drivers = ["/usr/bin/chromedriver"]
            
            # On Cloud Debian, we do NOT set binary_location (let the driver find it)
            # This prevents version mismatch errors.

        # Find the driver
        for d_path in possible_drivers:
            if os.path.exists(d_path):
                print(f"Using system ChromeDriver: {d_path}")
                service = Service(d_path)
                break

        # Fallback (Auto-Install) - Only if system driver is missing
        if not service:
            print("System driver not found, attempting auto-install...")
            try:
                service = Service(ChromeDriverManager().install())
            except Exception as e:
                print(f"Auto-install failed: {e}")
                service = Service()

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

    def __del__(self):
        if hasattr(self, 'driver'):
            try: self.driver.quit()
            except: pass

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
            raise NotImplementedError(f"Engine {params.engine} not implemented.")

    def _build_url(self, params: SearchParameters, base_path: str) -> str:
        query_params = {}
        if params.q: query_params['q'] = params.q
        if params.start > 0: query_params['start'] = params.start
        if params.hl: query_params['hl'] = params.hl
        if params.author_id: query_params['user'] = params.author_id
        
        if params.engine == "google_scholar_profiles":
             query_params['view_op'] = 'search_authors'
             query_params['mauthors'] = params.q
             if 'q' in query_params: del query_params['q']

        return f"{self.BASE_URL}/{base_path}?{urllib.parse.urlencode(query_params)}"

    def _search_scholar(self, params: SearchParameters) -> GoogleScholarResponse:
        url = self._build_url(params, "scholar")
        start_time = time.time()
        
        print(f"DEBUG: Navigating to {url}")
        self.driver.get(url)
        random_sleep()
        
        if "sorry" in self.driver.current_url:
             print("WARNING: Captcha Page Detected!")

        results = []
        elements = self.driver.find_elements(By.CSS_SELECTOR, '.gs_r')
        
        for i, elem in enumerate(elements):
            try:
                if "gs_or" not in elem.get_attribute("class"): continue

                title_e = elem.find_element(By.CSS_SELECTOR, '.gs_rt')
                title = title_e.text
                try: link = title_e.find_element(By.TAG_NAME, 'a').get_attribute('href')
                except: link = None

                try: snippet = elem.find_element(By.CSS_SELECTOR, '.gs_rs').text
                except: snippet = ""

                # Robust Author Extraction
                pub_info = ""
                authors_list = []
                try: 
                    pub_info_elem = elem.find_element(By.CSS_SELECTOR, '.gs_a')
                    pub_info = pub_info_elem.text
                    for a_tag in pub_info_elem.find_elements(By.TAG_NAME, 'a'):
                         try:
                             a_link = a_tag.get_attribute('href')
                             if 'user=' in a_link:
                                 parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(a_link).query)
                                 a_id = parsed_q.get('user', [None])[0]
                                 authors_list.append(Author(name=a_tag.text, id=a_id, link=a_link))
                         except: pass
                except: pass

                results.append(OrganicResult(
                    position=i, title=title, link=link, snippet=snippet, 
                    publication_info=pub_info, authors=authors_list
                ))
            except: continue

        req_time = time.time() - start_time
        return GoogleScholarResponse(
            search_metadata=SearchMetadata(
                created_at=datetime.utcnow().isoformat(),
                request_time_taken=req_time,
                request_url=url,
                status="Success" if results else "Empty"
            ),
            search_parameters=params,
            search_information=SearchInformation(total_results=len(results)),
            organic_results=results
        )

    def _search_profiles(self, params: SearchParameters) -> GoogleScholarResponse:
        print(f"DEBUG: Starting Robust Profile Search for '{params.q}'...")
        start_time = time.time()

        # 1. Search Publications first
        pub_params = SearchParameters(engine="google_scholar", q=params.q, num=10)
        pub_results = self._search_scholar(pub_params)
        
        found_id = None
        profiles = []
        
        # 2. Look for Author ID in results
        for res in pub_results.organic_results:
            if not res.authors: continue
            for author in res.authors:
                q_parts = params.q.split()
                if q_parts[-1].lower() in author.name.lower() and author.id:
                    found_id = author.id
                    print(f"DEBUG: Found Author ID: {found_id}")
                    break
            if found_id: break

        # 3. If ID found, fetch the actual profile
        if found_id:
            auth_params = SearchParameters(
                engine="google_scholar_author", author_id=found_id, hl=params.hl
            )
            try:
                auth_res = self._search_author(auth_params)
                if auth_res.author:
                    profiles.append(auth_res.author)
            except Exception as e:
                print(f"DEBUG: Error fetching profile: {e}")
        else:
            print("DEBUG: No matching Author ID found.")

        return GoogleScholarResponse(
            search_metadata=SearchMetadata(
                created_at=datetime.utcnow().isoformat(),
                request_time_taken=time.time() - start_time,
                request_url="robust_profile_search"
            ),
            search_parameters=params,
            profiles=profiles
        )

    def _search_author(self, params: SearchParameters) -> GoogleScholarResponse:
         url = self._build_url(params, "citations")
         start_time = time.time()
         self.driver.get(url)
         random_sleep()
         
         try: name = self.driver.find_element(By.ID, 'gsc_prf_in').text
         except: name = "Unknown"
         
         try: aff = self.driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
         except: aff = ""

         profile = AuthorProfile(name=name, author_id=params.author_id, affiliations=aff)
         
         articles = []
         try:
             rows = self.driver.find_elements(By.CSS_SELECTOR, '.gsc_a_tr')
             for row in rows:
                 title_e = row.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                 articles.append(OrganicResult(title=title_e.text, link=title_e.get_attribute('href')))
         except: pass

         return GoogleScholarResponse(
             search_metadata=SearchMetadata(created_at=datetime.utcnow().isoformat(), request_time_taken=time.time()-start_time),
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
         
         citations = []
         try:
             rows = self.driver.find_elements(By.CSS_SELECTOR, '#gs_citt tr')
             for row in rows:
                 title = row.find_element(By.CSS_SELECTOR, '.gs_cith').text
                 snippet = row.find_element(By.CSS_SELECTOR, '.gs_citr').text
                 citations.append({"title": title, "snippet": snippet})
         except: pass

         return GoogleScholarResponse(
             search_metadata=SearchMetadata(created_at=datetime.utcnow().isoformat()),
             search_parameters=params,
             citations=citations
         )