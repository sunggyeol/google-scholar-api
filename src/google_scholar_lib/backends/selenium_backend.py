from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time
import urllib.parse
from datetime import datetime
import os
import random
import platform
import shutil
from typing import Optional, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .pool import SeleniumBackendPool

from ..core import ScraperBackend
from ..models import (
    GoogleScholarResponse, SearchParameters, SearchMetadata, SearchInformation,
    OrganicResult, Author, Pagination, AuthorProfile, InlineLinks, Resource
)
from ..utils import random_sleep, random_sleep_long

class SeleniumBackend(ScraperBackend):
    BASE_URL = "https://scholar.google.com"

    def __init__(self, pool: Optional['SeleniumBackendPool'] = None, headless: bool = True):
        """
        Initialize SeleniumBackend.

        Args:
            pool: Optional SeleniumBackendPool instance for pooled mode
            headless: Headless mode (ignored if pool provided, pool handles this)
        """
        self.pool = pool

        # Pooled mode: Don't create driver, acquire from pool per-request
        if pool is not None:
            self.driver = None
            self._owns_driver = False
            logger.info("SeleniumBackend initialized in pooled mode")
            return

        # Legacy mode: Create own driver (backward compatibility)
        logger.warning("SeleniumBackend initialized in legacy mode (no pool) - not recommended for production")
        self._owns_driver = True

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
        # Only quit if we own the driver (legacy mode)
        if self._owns_driver and hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass

    async def search(self, params: SearchParameters) -> GoogleScholarResponse:
        """
        Route search request to appropriate engine.
        Now async to support pool-based driver acquisition.
        """
        if params.engine == "google_scholar":
            return await self._search_scholar(params)
        elif params.engine == "google_scholar_author":
            return await self._search_author(params)
        elif params.engine == "google_scholar_cite":
            return await self._search_cite(params)
        elif params.engine == "google_scholar_profiles":
            return await self._search_profiles(params)
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

    async def _search_scholar(self, params: SearchParameters) -> GoogleScholarResponse:
        """Search for publications (pooled or legacy mode)"""
        if self.pool:
            # Pooled mode: Acquire driver from pool
            async with self.pool.acquire_driver() as (driver, metrics):
                return await self._execute_scholar_search(driver, params, metrics)
        else:
            # Legacy mode: Use own driver
            return await self._execute_scholar_search(self.driver, params, None)

    async def _execute_scholar_search(self, driver, params: SearchParameters, metrics=None) -> GoogleScholarResponse:
        """Execute scholar search with given driver"""
        url = self._build_url(params, "scholar")
        start_time = time.time()

        logger.debug(f"Navigating to {url}")
        try:
            driver.get(url)
        except TimeoutException:
            logger.error(f"Page load timeout for {url}")
            raise  # Will be caught in endpoint and converted to 504

        random_sleep()

        # Check for blocking (pooled mode only)
        if self.pool and metrics:
            is_blocked = await self.pool.check_for_blocking(driver, metrics)
            if is_blocked:
                logger.error(f"Driver {metrics.driver_id} is blocked by Google Scholar")
                # Return empty results instead of crashing
                return GoogleScholarResponse(
                    search_metadata=SearchMetadata(
                        created_at=datetime.utcnow().isoformat(),
                        request_time_taken=time.time() - start_time,
                        request_url=url,
                        status="Blocked"
                    ),
                    search_parameters=params,
                    search_information=SearchInformation(total_results=0),
                    organic_results=[]
                )

        # Legacy CAPTCHA detection (for backward compatibility)
        if "sorry" in driver.current_url:
            logger.warning("CAPTCHA page detected!")

        results = []
        elements = driver.find_elements(By.CSS_SELECTOR, '.gs_r')

        for i, elem in enumerate(elements):
            try:
                if "gs_or" not in elem.get_attribute("class"):
                    continue

                title_e = elem.find_element(By.CSS_SELECTOR, '.gs_rt')
                title = title_e.text
                try:
                    link = title_e.find_element(By.TAG_NAME, 'a').get_attribute('href')
                except:
                    link = None

                try:
                    snippet = elem.find_element(By.CSS_SELECTOR, '.gs_rs').text
                except:
                    snippet = ""

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
                        except:
                            pass
                except:
                    pass

                # Extract citation count and inline links
                inline_links = None
                cited_by_count = 0
                resources_list = []
                result_id = None

                try:
                    # Extract result_id (data-cid) for citations
                    result_id = elem.get_attribute('data-cid')
                except:
                    pass

                try:
                    # Look for footer links section (specifically the .gs_flb variant, not .gs_ggs)
                    gs_fl = elem.find_element(By.CSS_SELECTOR, '.gs_ri .gs_fl')

                    # Extract citation count
                    cited_by_dict = None
                    related_link = None
                    versions_dict = None

                    for a_tag in gs_fl.find_elements(By.TAG_NAME, 'a'):
                        try:
                            a_text = a_tag.text
                            a_href = a_tag.get_attribute('href')

                            # "Cited by XXX" link
                            if a_text.startswith('Cited by'):
                                try:
                                    count_str = a_text.replace('Cited by', '').strip()
                                    cited_by_count = int(count_str)

                                    # Extract cites_id from URL
                                    parsed_url = urllib.parse.urlparse(a_href)
                                    parsed_q = urllib.parse.parse_qs(parsed_url.query)
                                    cites_id = parsed_q.get('cites', [None])[0]

                                    cited_by_dict = {
                                        'total': cited_by_count,
                                        'link': a_href,
                                        'cites_id': cites_id
                                    }
                                except (ValueError, AttributeError):
                                    pass

                            # "Related articles" link
                            elif 'Related articles' in a_text:
                                related_link = a_href

                            # "All X versions" link
                            elif 'version' in a_text.lower():
                                try:
                                    version_count = int(''.join(filter(str.isdigit, a_text)))
                                    parsed_url = urllib.parse.urlparse(a_href)
                                    parsed_q = urllib.parse.parse_qs(parsed_url.query)
                                    cluster_id = parsed_q.get('cluster', [None])[0]

                                    versions_dict = {
                                        'total': version_count,
                                        'link': a_href,
                                        'cluster_id': cluster_id
                                    }
                                except (ValueError, AttributeError):
                                    pass
                        except:
                            pass

                    # Create InlineLinks object if we have any data
                    if cited_by_dict or related_link or versions_dict:
                        inline_links = InlineLinks(
                            cited_by=cited_by_dict,
                            related_articles_link=related_link,
                            versions=versions_dict
                        )
                except:
                    pass

                # Extract PDF/HTML resources
                try:
                    gs_ggs = elem.find_elements(By.CSS_SELECTOR, '.gs_or_ggsm a')
                    for res_link in gs_ggs:
                        try:
                            res_text = res_link.text
                            res_href = res_link.get_attribute('href')

                            # Determine format (PDF, HTML, etc.)
                            format_type = None
                            if '[PDF]' in res_text or res_href.endswith('.pdf'):
                                format_type = 'PDF'
                            elif '[HTML]' in res_text:
                                format_type = 'HTML'

                            resources_list.append(Resource(
                                name=res_text.strip('[]'),
                                format=format_type,
                                link=res_href
                            ))
                        except:
                            pass
                except:
                    pass

                results.append(OrganicResult(
                    position=i,
                    title=title,
                    link=link,
                    snippet=snippet,
                    publication_info=pub_info,
                    authors=authors_list,
                    inline_links=inline_links,
                    cited_by_count=cited_by_count,
                    resources=resources_list,
                    result_id=result_id
                ))
            except:
                continue

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

    async def _search_profiles(self, params: SearchParameters) -> GoogleScholarResponse:
        """Search for author profiles (pooled or legacy mode)"""
        logger.debug(f"Starting Robust Profile Search for '{params.q}'...")
        start_time = time.time()

        # 1. Search Publications first
        pub_params = SearchParameters(engine="google_scholar", q=params.q, num=10)
        pub_results = await self._search_scholar(pub_params)

        found_id = None
        profiles = []

        # 2. Look for Author ID in results
        for res in pub_results.organic_results:
            if not res.authors:
                continue
            for author in res.authors:
                q_parts = params.q.split()
                if q_parts[-1].lower() in author.name.lower() and author.id:
                    found_id = author.id
                    logger.debug(f"Found Author ID: {found_id}")
                    break
            if found_id:
                break

        # 3. If ID found, fetch the actual profile
        if found_id:
            auth_params = SearchParameters(
                engine="google_scholar_author", author_id=found_id, hl=params.hl
            )
            try:
                auth_res = await self._search_author(auth_params)
                if auth_res.author:
                    profiles.append(auth_res.author)
            except Exception as e:
                logger.error(f"Error fetching profile: {e}")
        else:
            logger.debug("No matching Author ID found.")

        return GoogleScholarResponse(
            search_metadata=SearchMetadata(
                created_at=datetime.utcnow().isoformat(),
                request_time_taken=time.time() - start_time,
                request_url="robust_profile_search"
            ),
            search_parameters=params,
            profiles=profiles
        )

    async def _search_author(self, params: SearchParameters) -> GoogleScholarResponse:
        """Search for author profile (pooled or legacy mode)"""
        if self.pool:
            # Pooled mode: Acquire driver from pool
            async with self.pool.acquire_driver() as (driver, metrics):
                return await self._execute_author_search(driver, params, metrics)
        else:
            # Legacy mode: Use own driver
            return await self._execute_author_search(self.driver, params, None)

    async def _execute_author_search(self, driver, params: SearchParameters, metrics=None) -> GoogleScholarResponse:
        """Execute author search with given driver"""
        url = self._build_url(params, "citations")
        start_time = time.time()

        try:
            driver.get(url)
        except TimeoutException:
            logger.error(f"Page load timeout for author {params.author_id}")
            raise

        random_sleep()

        # Check for blocking (pooled mode only)
        if self.pool and metrics:
            is_blocked = await self.pool.check_for_blocking(driver, metrics)
            if is_blocked:
                logger.error(f"Driver {metrics.driver_id} is blocked by Google Scholar")
                # Return empty profile instead of crashing
                return GoogleScholarResponse(
                    search_metadata=SearchMetadata(
                        created_at=datetime.utcnow().isoformat(),
                        request_time_taken=time.time() - start_time,
                        status="Blocked"
                    ),
                    search_parameters=params,
                    author=AuthorProfile(name="Unknown", author_id=params.author_id, affiliations=""),
                    articles=[]
                )

        try:
            name = driver.find_element(By.ID, 'gsc_prf_in').text
        except:
            name = "Unknown"

        try:
            aff = driver.find_element(By.CSS_SELECTOR, '.gsc_prf_il').text
        except:
            aff = ""

        profile = AuthorProfile(name=name, author_id=params.author_id, affiliations=aff)

        articles = []
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, '.gsc_a_tr')
            for i, row in enumerate(rows):
                try:
                    # Extract title and link
                    title_e = row.find_element(By.CSS_SELECTOR, '.gsc_a_t a')
                    title = title_e.text
                    link = title_e.get_attribute('href')

                    # Extract authors from first .gs_gray div
                    authors_list = []
                    authors_text = ""
                    try:
                        gs_gray_divs = row.find_elements(By.CSS_SELECTOR, '.gsc_a_t .gs_gray')
                        if len(gs_gray_divs) >= 1:
                            authors_text = gs_gray_divs[0].text
                            # Parse author names (they're just text, no links on author profile pages)
                            if authors_text:
                                author_names = [name.strip() for name in authors_text.split(',')]
                                authors_list = [Author(name=name) for name in author_names if name]
                    except:
                        pass

                    # Extract publication info from second .gs_gray div
                    pub_info = ""
                    try:
                        gs_gray_divs = row.find_elements(By.CSS_SELECTOR, '.gsc_a_t .gs_gray')
                        if len(gs_gray_divs) >= 2:
                            pub_info = gs_gray_divs[1].text
                    except:
                        pass

                    # Extract citation count
                    cited_by_count = 0
                    inline_links = None
                    try:
                        cites_elem = row.find_element(By.CSS_SELECTOR, '.gsc_a_ac')
                        cites_text = cites_elem.text.strip()
                        if cites_text:
                            cited_by_count = int(cites_text)

                            # Try to extract the citation link
                            try:
                                cites_link = cites_elem.get_attribute('href')
                                if cites_link:
                                    # Extract cites_id from URL
                                    parsed_url = urllib.parse.urlparse(cites_link)
                                    parsed_q = urllib.parse.parse_qs(parsed_url.query)
                                    cites_id = parsed_q.get('cites', [None])[0]

                                    inline_links = InlineLinks(
                                        cited_by={
                                            'total': cited_by_count,
                                            'link': cites_link,
                                            'cites_id': cites_id
                                        }
                                    )
                            except:
                                pass
                    except:
                        pass

                    articles.append(OrganicResult(
                        position=i,
                        title=title,
                        link=link,
                        authors=authors_list,
                        publication_info=pub_info,
                        cited_by_count=cited_by_count,
                        inline_links=inline_links
                    ))
                except:
                    continue
        except:
            pass

        return GoogleScholarResponse(
            search_metadata=SearchMetadata(created_at=datetime.utcnow().isoformat(), request_time_taken=time.time()-start_time),
            search_parameters=params,
            author=profile,
            articles=articles
        )

    async def _search_cite(self, params: SearchParameters) -> GoogleScholarResponse:
        """Search for citation formats (pooled or legacy mode)"""
        if self.pool:
            # Pooled mode: Acquire driver from pool
            async with self.pool.acquire_driver() as (driver, metrics):
                return await self._execute_cite_search(driver, params, metrics)
        else:
            # Legacy mode: Use own driver
            return await self._execute_cite_search(self.driver, params, None)

    async def _execute_cite_search(self, driver, params: SearchParameters, metrics=None) -> GoogleScholarResponse:
        """Execute citation search with given driver"""
        cid = params.q or params.cites
        url = f"{self.BASE_URL}/scholar?q=info:{cid}:scholar.google.com&output=cite&hl={params.hl}"
        start_time = time.time()

        try:
            driver.get(url)
        except TimeoutException:
            logger.error(f"Page load timeout for citation {cid}")
            raise

        random_sleep()

        # Check for blocking (pooled mode only)
        if self.pool and metrics:
            is_blocked = await self.pool.check_for_blocking(driver, metrics)
            if is_blocked:
                logger.error(f"Driver {metrics.driver_id} is blocked by Google Scholar")
                # Return empty citations instead of crashing
                return GoogleScholarResponse(
                    search_metadata=SearchMetadata(created_at=datetime.utcnow().isoformat(), status="Blocked"),
                    search_parameters=params,
                    citations=[]
                )

        citations = []
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, '#gs_citt tr')
            for row in rows:
                title = row.find_element(By.CSS_SELECTOR, '.gs_cith').text
                snippet = row.find_element(By.CSS_SELECTOR, '.gs_citr').text
                citations.append({"title": title, "snippet": snippet})
        except:
            pass

        return GoogleScholarResponse(
            search_metadata=SearchMetadata(created_at=datetime.utcnow().isoformat()),
            search_parameters=params,
            citations=citations
        )