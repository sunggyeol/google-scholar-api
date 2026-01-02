"""
Selenium WebDriver Connection Pool

Manages a pool of Selenium WebDriver instances for concurrent request handling.
Includes health monitoring, auto-recovery, rate limiting, and adaptive scaling.

Optimized for low-memory cloud environments (1GB RAM).
"""

import asyncio
import os
import platform
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple
from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException


class DriverRateLimiter:
    """
    Per-driver rate limiter using sliding window algorithm.

    Prevents Google Scholar from blocking individual drivers by limiting
    requests to 10 per minute per driver.
    """

    def __init__(self, max_requests_per_minute: int = 10):
        self.max_rpm = max_requests_per_minute
        self.request_times: List[float] = []

    async def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove requests older than 1 minute (sliding window)
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.max_rpm:
            # Calculate wait time until oldest request falls out of window
            oldest_request = self.request_times[0]
            wait_time = 60 - (now - oldest_request) + 0.1  # +0.1s buffer

            if wait_time > 0:
                logger.debug(
                    f"Rate limit reached ({self.max_rpm} req/min) - waiting {wait_time:.1f}s",
                    extra={"event": "rate_limit.wait", "wait_time": wait_time}
                )
                await asyncio.sleep(wait_time)

        # Record this request
        self.request_times.append(now)


class DriverMetrics:
    """
    Tracks per-driver usage metrics and health status.
    """

    def __init__(self, driver_id: int):
        self.driver_id = driver_id
        self.request_count = 0
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.restart_count = 0
        self.rate_limiter = DriverRateLimiter(max_requests_per_minute=10)
        self.is_quarantined = False
        self.quarantine_time: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for API responses"""
        return {
            "driver_id": self.driver_id,
            "request_count": self.request_count,
            "age_seconds": int(time.time() - self.created_at),
            "last_used_seconds_ago": int(time.time() - self.last_used_at),
            "restart_count": self.restart_count,
            "is_quarantined": self.is_quarantined
        }


class SeleniumBackendPool:
    """
    Connection pool for Selenium WebDriver instances.

    Features:
    - Pre-warmed driver pool for low-latency requests
    - Health monitoring and auto-recovery
    - Automatic driver recycling to prevent memory leaks
    - CAPTCHA detection and driver quarantine
    - Per-driver rate limiting (anti-blocking)
    - Adaptive pool sizing based on demand
    - Comprehensive metrics tracking

    Optimized for 1GB RAM environments (e2-micro instances).
    """

    def __init__(
        self,
        pool_size: int = 1,
        max_pool_size: int = 2,
        max_requests_per_driver: int = 50,
        driver_startup_timeout: int = 10,
        acquire_timeout: int = 10,
        health_check_interval: int = 30
    ):
        """
        Initialize the pool (does not create drivers yet - call initialize())

        Args:
            pool_size: Initial number of drivers (1 for 1GB RAM)
            max_pool_size: Maximum drivers during scaling (2 for 1GB RAM)
            max_requests_per_driver: Recycle driver after N requests
            driver_startup_timeout: Timeout for driver creation (seconds)
            acquire_timeout: Max wait time for driver acquisition (seconds)
            health_check_interval: Health check frequency (seconds)
        """
        self.pool_size = pool_size
        self.max_pool_size = max_pool_size
        self.max_requests_per_driver = max_requests_per_driver
        self.driver_startup_timeout = driver_startup_timeout
        self.acquire_timeout = acquire_timeout
        self.health_check_interval = health_check_interval

        # Driver pool (asyncio.Queue for thread-safe FIFO)
        self._drivers: asyncio.Queue = asyncio.Queue(maxsize=max_pool_size)
        self._driver_metrics: Dict[int, DriverMetrics] = {}
        self._initialized = False
        self._shutdown_event = asyncio.Event()

        # Health monitoring
        self._health_check_task: Optional[asyncio.Task] = None
        self._blocked_drivers: Dict[int, float] = {}  # driver_id -> block_time

        # Adaptive scaling
        self.current_pool_size = pool_size
        self._scale_up_threshold = 0.8  # Scale up if >80% utilized
        self._scale_down_threshold = 0.3  # Scale down if <30% utilized
        self._last_scale_time = time.time()
        self._scale_cooldown = 60  # Don't scale more than once per minute

        # Pool-level metrics
        self.total_acquisitions = 0
        self.total_releases = 0
        self.total_driver_restarts = 0
        self.total_blocked_drivers = 0

        logger.info(
            f"SeleniumBackendPool configured",
            extra={
                "event": "pool.init",
                "pool_size": pool_size,
                "max_pool_size": max_pool_size,
                "max_requests_per_driver": max_requests_per_driver
            }
        )

    async def initialize(self):
        """
        Pre-warm the pool with drivers during FastAPI startup.

        Raises:
            Exception: If driver initialization fails
        """
        logger.info(
            f"Initializing Selenium pool with {self.pool_size} drivers...",
            extra={"event": "pool.initialize.start", "pool_size": self.pool_size}
        )

        # Create initial drivers
        for driver_id in range(self.pool_size):
            try:
                driver, metrics = await self._create_driver(driver_id)
                await self._drivers.put((driver, metrics))
                self._driver_metrics[driver_id] = metrics
                logger.info(
                    f"Driver {driver_id} initialized successfully",
                    extra={"event": "pool.driver.created", "driver_id": driver_id}
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize driver {driver_id}: {e}",
                    extra={"event": "pool.driver.init_failed", "driver_id": driver_id, "error": str(e)}
                )
                raise

        # Start background health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health check task started")

        self._initialized = True
        logger.info(
            f"Pool initialized successfully with {self.pool_size} drivers",
            extra={"event": "pool.initialize.complete", "pool_size": self.pool_size}
        )

    async def _create_driver(self, driver_id: int) -> Tuple[webdriver.Chrome, DriverMetrics]:
        """
        Create a single Chrome WebDriver instance.

        Reuses Chrome options and service discovery logic from selenium_backend.py.

        Args:
            driver_id: Unique identifier for this driver

        Returns:
            Tuple of (driver, metrics)

        Raises:
            Exception: If driver creation fails
        """
        logger.debug(
            f"Creating driver {driver_id}",
            extra={"event": "pool.driver.create_start", "driver_id": driver_id}
        )

        try:
            # === Chrome Options Setup (from selenium_backend.py) ===
            chrome_options = Options()

            # Detect architecture
            arch = platform.machine()
            is_arm = arch in ('aarch64', 'arm64')

            # Stability flags (universal)
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-software-rasterizer")

            # Memory optimization (crucial for 1GB RAM)
            chrome_options.add_argument("--js-flags=--max-old-space-size=512")

            # Anti-blocking user agent
            chrome_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Headless mode (always on for pool)
            chrome_options.add_argument("--headless=new")

            # === Service Setup (platform-specific) ===
            service = None

            if is_arm:
                # ARM/Jetson paths
                logger.debug(f"ARM64 architecture detected ({arch})")
                possible_drivers = [
                    "/usr/lib/chromium-browser/chromedriver",
                    "/usr/bin/chromedriver",
                    "/snap/bin/chromium.chromedriver"
                ]
                browser_bin = "/usr/bin/chromium-browser"
                if os.path.exists(browser_bin):
                    chrome_options.binary_location = browser_bin
            else:
                # x86/Cloud paths
                logger.debug(f"x86_64 architecture detected ({arch})")
                possible_drivers = ["/usr/bin/chromedriver"]

            # Find system driver
            for d_path in possible_drivers:
                if os.path.exists(d_path):
                    logger.debug(f"Using system ChromeDriver: {d_path}")
                    service = Service(d_path)
                    break

            # Fallback to auto-install (not recommended for production)
            if not service:
                logger.warning("System ChromeDriver not found, using fallback")
                service = Service()

            # === Create Driver ===
            driver = webdriver.Chrome(service=service, options=chrome_options)

            # Set page load timeout (for 504 error handling)
            driver.set_page_load_timeout(30)

            # Create metrics tracker
            metrics = DriverMetrics(driver_id)

            logger.debug(
                f"Driver {driver_id} created successfully",
                extra={"event": "pool.driver.created", "driver_id": driver_id}
            )

            return driver, metrics

        except Exception as e:
            logger.error(
                f"Driver creation failed for driver {driver_id}: {e}",
                extra={"event": "pool.driver.create_failed", "driver_id": driver_id, "error": str(e)}
            )
            raise

    async def acquire(self, timeout: Optional[float] = None) -> Tuple[webdriver.Chrome, DriverMetrics]:
        """
        Acquire a driver from the pool.

        Args:
            timeout: Max wait time in seconds (uses acquire_timeout if None)

        Returns:
            Tuple of (driver, metrics)

        Raises:
            asyncio.TimeoutError: If no driver available within timeout (caller should return 503)
        """
        timeout = timeout or self.acquire_timeout

        logger.debug(
            "Acquiring driver from pool",
            extra={
                "event": "pool.acquire.start",
                "available": self._drivers.qsize(),
                "pool_size": self.current_pool_size
            }
        )

        try:
            driver, metrics = await asyncio.wait_for(
                self._drivers.get(),
                timeout=timeout
            )

            # Update metrics
            metrics.request_count += 1
            metrics.last_used_at = time.time()
            self.total_acquisitions += 1

            # Apply per-driver rate limiting (Phase 3)
            await metrics.rate_limiter.wait_if_needed()

            logger.info(
                f"Acquired driver {metrics.driver_id}",
                extra={
                    "event": "pool.acquire.success",
                    "driver_id": metrics.driver_id,
                    "request_count": metrics.request_count,
                    "queue_length": self.current_pool_size - self._drivers.qsize()
                }
            )

            # Check if we should scale up (Phase 3)
            asyncio.create_task(self._adaptive_scaling_check())

            return driver, metrics

        except asyncio.TimeoutError:
            logger.warning(
                f"Pool exhausted - no driver available after {timeout}s",
                extra={
                    "event": "pool.acquire.timeout",
                    "timeout": timeout,
                    "pool_size": self.current_pool_size
                }
            )
            raise  # Caller converts to 503

    async def release(self, driver: webdriver.Chrome, metrics: DriverMetrics):
        """
        Release driver back to pool or recycle if stale.

        Args:
            driver: WebDriver instance to release
            metrics: Associated metrics tracker
        """
        self.total_releases += 1

        logger.debug(
            f"Releasing driver {metrics.driver_id}",
            extra={
                "event": "pool.release.start",
                "driver_id": metrics.driver_id,
                "request_count": metrics.request_count
            }
        )

        # Check if driver should be recycled
        if metrics.request_count >= self.max_requests_per_driver:
            logger.info(
                f"Driver {metrics.driver_id} reached {metrics.request_count} requests - recycling",
                extra={
                    "event": "pool.driver.recycle_threshold",
                    "driver_id": metrics.driver_id,
                    "request_count": metrics.request_count
                }
            )
            await self._recycle_driver(driver, metrics)
        else:
            # Return to pool
            await self._drivers.put((driver, metrics))
            logger.debug(
                f"Driver {metrics.driver_id} returned to pool",
                extra={
                    "event": "pool.release.success",
                    "driver_id": metrics.driver_id,
                    "available": self._drivers.qsize()
                }
            )

    async def _recycle_driver(self, old_driver: webdriver.Chrome, metrics: DriverMetrics):
        """
        Replace old driver with fresh one to prevent memory leaks.

        Args:
            old_driver: Driver to close
            metrics: Metrics of old driver
        """
        driver_id = metrics.driver_id

        logger.info(
            f"Recycling driver {driver_id}",
            extra={"event": "pool.driver.recycle_start", "driver_id": driver_id}
        )

        try:
            # Close old driver
            try:
                old_driver.quit()
                logger.debug(f"Closed old driver {driver_id}")
            except Exception as e:
                logger.warning(f"Error closing old driver {driver_id}: {e}")

            # Create new driver with same ID
            new_driver, new_metrics = await self._create_driver(driver_id)
            new_metrics.restart_count = metrics.restart_count + 1

            # Update metrics tracking
            self._driver_metrics[driver_id] = new_metrics
            self.total_driver_restarts += 1

            # Add back to pool
            await self._drivers.put((new_driver, new_metrics))

            logger.info(
                f"Driver {driver_id} recycled successfully (restart #{new_metrics.restart_count})",
                extra={
                    "event": "pool.driver.recycle_success",
                    "driver_id": driver_id,
                    "restart_count": new_metrics.restart_count
                }
            )

        except Exception as e:
            logger.error(
                f"Driver recycling failed for driver {driver_id}: {e}",
                extra={"event": "pool.driver.recycle_failed", "driver_id": driver_id, "error": str(e)}
            )
            # Don't add back to pool - pool size will be reduced
            # Health check will detect this and may scale up

    # === Phase 2: Health Monitoring ===

    async def _health_check_loop(self):
        """Background task - checks driver health every N seconds"""
        logger.info(
            f"Health check loop started (interval: {self.health_check_interval}s)",
            extra={"event": "pool.health_check.start"}
        )

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.health_check_interval)

                if self._shutdown_event.is_set():
                    break

                await self._perform_health_check()

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Health check error: {e}",
                    extra={"event": "pool.health_check.error", "error": str(e)}
                )

    async def _perform_health_check(self):
        """Check all drivers for responsiveness"""
        logger.debug(
            "Performing health check on all drivers",
            extra={"event": "pool.health_check.perform"}
        )

        # Snapshot current pool
        current_drivers = []
        check_count = min(self._drivers.qsize(), self.current_pool_size)

        for _ in range(check_count):
            try:
                driver, metrics = await asyncio.wait_for(self._drivers.get(), timeout=1)
                current_drivers.append((driver, metrics))
            except asyncio.TimeoutError:
                break

        # Check each driver
        healthy_count = 0
        unhealthy_count = 0

        for driver, metrics in current_drivers:
            is_healthy = await self._is_driver_responsive(driver, metrics)

            if is_healthy:
                # Return healthy driver to pool
                await self._drivers.put((driver, metrics))
                healthy_count += 1
            else:
                # Replace unhealthy driver
                logger.warning(
                    f"Driver {metrics.driver_id} is unresponsive - replacing",
                    extra={"event": "pool.health_check.unresponsive", "driver_id": metrics.driver_id}
                )
                await self._recycle_driver(driver, metrics)
                unhealthy_count += 1

        logger.debug(
            f"Health check complete: {healthy_count} healthy, {unhealthy_count} recycled",
            extra={
                "event": "pool.health_check.complete",
                "healthy": healthy_count,
                "unhealthy": unhealthy_count
            }
        )

    async def _is_driver_responsive(self, driver: webdriver.Chrome, metrics: DriverMetrics) -> bool:
        """
        Check if driver is responsive.

        Args:
            driver: Driver to check
            metrics: Driver metrics

        Returns:
            True if healthy, False if needs replacement
        """
        try:
            # Simple responsiveness check with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, lambda: driver.current_url),
                timeout=3.0
            )
            return True

        except asyncio.TimeoutError:
            logger.warning(
                f"Driver {metrics.driver_id} timeout during health check",
                extra={"event": "pool.health_check.timeout", "driver_id": metrics.driver_id}
            )
            return False
        except WebDriverException as e:
            logger.warning(
                f"Driver {metrics.driver_id} WebDriver error: {e}",
                extra={"event": "pool.health_check.webdriver_error", "driver_id": metrics.driver_id}
            )
            return False
        except Exception as e:
            logger.warning(
                f"Driver {metrics.driver_id} health check failed: {e}",
                extra={"event": "pool.health_check.failed", "driver_id": metrics.driver_id, "error": str(e)}
            )
            return False

    async def check_for_blocking(self, driver: webdriver.Chrome, metrics: DriverMetrics) -> bool:
        """
        Check if driver is blocked/CAPTCHA'd by Google Scholar.

        Call this after each request in selenium_backend.py

        Args:
            driver: Driver to check
            metrics: Driver metrics

        Returns:
            True if blocked, False if OK
        """
        try:
            # Get page source (run in executor to avoid blocking)
            loop = asyncio.get_event_loop()
            page_source = await loop.run_in_executor(None, lambda: driver.page_source.lower())

            # Detection patterns - only check for explicit blocking pages
            # Don't check empty title as it can be a false positive
            blocked_patterns = [
                "our systems have detected unusual traffic",
                "please show you're not a robot"
            ]

            for pattern in blocked_patterns:
                if pattern in page_source:
                    logger.warning(
                        f"Driver {metrics.driver_id} detected as blocked: '{pattern}' found",
                        extra={
                            "event": "pool.blocking.detected",
                            "driver_id": metrics.driver_id,
                            "pattern": pattern
                        }
                    )
                    return True

            return False

        except Exception as e:
            logger.error(
                f"Block detection error for driver {metrics.driver_id}: {e}",
                extra={"event": "pool.blocking.error", "driver_id": metrics.driver_id, "error": str(e)}
            )
            return False

    async def quarantine_driver(self, driver: webdriver.Chrome, metrics: DriverMetrics):
        """
        Quarantine blocked driver - recycle immediately.

        Args:
            driver: Blocked driver
            metrics: Driver metrics
        """
        logger.warning(
            f"Quarantining driver {metrics.driver_id} due to blocking detection",
            extra={"event": "pool.driver.quarantine", "driver_id": metrics.driver_id}
        )

        metrics.is_quarantined = True
        metrics.quarantine_time = time.time()
        self._blocked_drivers[metrics.driver_id] = metrics.quarantine_time
        self.total_blocked_drivers += 1

        # Immediately recycle
        await self._recycle_driver(driver, metrics)

    # === Phase 3: Adaptive Scaling ===

    async def _adaptive_scaling_check(self):
        """Check if pool should scale up/down based on utilization"""
        # Check cooldown period
        if time.time() - self._last_scale_time < self._scale_cooldown:
            return

        available = self._drivers.qsize()
        if self.current_pool_size == 0:
            return  # Avoid division by zero

        utilization = 1 - (available / self.current_pool_size)

        logger.debug(
            f"Pool utilization: {utilization:.1%}",
            extra={
                "event": "pool.scaling.check",
                "utilization": round(utilization * 100, 1),
                "available": available,
                "pool_size": self.current_pool_size
            }
        )

        # Scale up if highly utilized
        if utilization > self._scale_up_threshold and self.current_pool_size < self.max_pool_size:
            await self._scale_pool(self.current_pool_size + 1)

        # Scale down if under-utilized
        elif utilization < self._scale_down_threshold and self.current_pool_size > self.pool_size:
            await self._scale_pool(self.current_pool_size - 1)

    async def _scale_pool(self, new_size: int):
        """
        Scale pool to new size.

        Args:
            new_size: Target pool size
        """
        logger.info(
            f"Scaling pool from {self.current_pool_size} to {new_size}",
            extra={
                "event": "pool.scaling.start",
                "old_size": self.current_pool_size,
                "new_size": new_size
            }
        )

        if new_size > self.current_pool_size:
            # Add drivers
            for i in range(new_size - self.current_pool_size):
                driver_id = self.current_pool_size + i
                try:
                    driver, metrics = await self._create_driver(driver_id)
                    await self._drivers.put((driver, metrics))
                    self._driver_metrics[driver_id] = metrics
                    logger.info(f"Added driver {driver_id} to pool")
                except Exception as e:
                    logger.error(f"Failed to add driver {driver_id}: {e}")

        elif new_size < self.current_pool_size:
            # Scale down - let natural recycling handle reduction
            logger.info("Scaling down - excess drivers will be removed during recycling")

        self.current_pool_size = new_size
        self._last_scale_time = time.time()

        logger.info(
            f"Pool scaled to {new_size} drivers",
            extra={"event": "pool.scaling.complete", "pool_size": new_size}
        )

    # === Shutdown ===

    async def shutdown(self):
        """Gracefully close all drivers during FastAPI shutdown"""
        self._shutdown_event.set()
        logger.info(
            "Shutting down Selenium pool...",
            extra={"event": "pool.shutdown.start"}
        )

        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            logger.debug("Health check task cancelled")

        # Close all drivers
        closed_count = 0
        while not self._drivers.empty():
            try:
                driver, metrics = await asyncio.wait_for(self._drivers.get(), timeout=1)
                try:
                    driver.quit()
                    closed_count += 1
                    logger.debug(f"Closed driver {metrics.driver_id}")
                except Exception as e:
                    logger.warning(f"Error closing driver {metrics.driver_id}: {e}")
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

        logger.info(
            f"Pool shutdown complete - {closed_count} drivers closed",
            extra={"event": "pool.shutdown.complete", "drivers_closed": closed_count}
        )

        self._initialized = False

    # === Context Manager ===

    @asynccontextmanager
    async def acquire_driver(self):
        """
        Context manager for safe acquire/release pattern.

        Usage in SeleniumBackend:
            async with self.pool.acquire_driver() as (driver, metrics):
                driver.get(url)
                # ... scraping logic
        """
        driver, metrics = await self.acquire()
        try:
            yield driver, metrics
        finally:
            await self.release(driver, metrics)

    # === Phase 4: Metrics ===

    def get_metrics(self) -> dict:
        """
        Get comprehensive pool metrics for /health endpoint.

        Returns:
            Dictionary with pool status and driver details
        """
        available = self._drivers.qsize()
        busy = self.current_pool_size - available
        utilization = (busy / self.current_pool_size * 100) if self.current_pool_size > 0 else 0

        return {
            "pool_size": self.current_pool_size,
            "max_pool_size": self.max_pool_size,
            "available_drivers": available,
            "busy_drivers": busy,
            "utilization_percent": round(utilization, 2),
            "total_acquisitions": self.total_acquisitions,
            "total_releases": self.total_releases,
            "total_driver_restarts": self.total_driver_restarts,
            "total_blocked_drivers": self.total_blocked_drivers,
            "blocked_drivers_count": len(self._blocked_drivers),
            "initialized": self._initialized,
            "driver_details": [
                metrics.to_dict()
                for metrics in self._driver_metrics.values()
            ]
        }
