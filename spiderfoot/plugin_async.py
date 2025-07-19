"""Asynchronous SpiderFoot Plugin Base Class

This module provides the async base class for SpiderFoot plugins,
enabling high-performance concurrent operations while maintaining
backward compatibility with synchronous plugins.
"""

from __future__ import annotations
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Set, TYPE_CHECKING
import logging
import time
from abc import abstractmethod

from .plugin import SpiderFootPlugin

if TYPE_CHECKING:
    from spiderfoot import SpiderFoot, SpiderFootEvent
    from .http_async import AsyncHttpClient
    from .rate_limiter import RateLimiter


class AsyncSpiderFootPlugin(SpiderFootPlugin):
    """Asynchronous SpiderFoot Plugin base class.
    
    This class extends SpiderFootPlugin to provide async/await support
    for high-performance concurrent operations. It maintains backward
    compatibility with the synchronous plugin system.
    
    Attributes:
        http_client: Async HTTP client with connection pooling
        dns_resolver: Async DNS resolver with caching
        rate_limiter: Rate limiting for API calls
        _event_loop: The event loop this plugin runs in
        _async_tasks: Set of running async tasks
    """
    
    def __init__(self) -> None:
        """Initialize the async plugin."""
        super().__init__()
        self.http_client: Optional[AsyncHttpClient] = None
        self.dns_resolver: Optional[AsyncDnsResolver] = None
        self.rate_limiter: Optional[RateLimiter] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
    async def setup_async(self, sf: SpiderFoot, opts: Dict[str, Any]) -> None:
        """Async setup method for initialization.
        
        Args:
            sf: SpiderFoot instance
            opts: Configuration options
        """
        # Call parent setup
        self.setup(sf, opts)
        
        # Initialize async components
        from .http_async import AsyncHttpClient
        from .rate_limiter import RateLimiter
        from .dns_async import AsyncDnsResolver
        
        # Create rate limiter
        self.rate_limiter = RateLimiter(
            global_limit=opts.get('_maxthreads', 10),
            per_second=opts.get('_requests_per_second', 10)
        )
        
        # Create HTTP client
        self.http_client = AsyncHttpClient(
            proxy=opts.get('_socks1type'),
            timeout=opts.get('_fetchtimeout', 30),
            rate_limiter=self.rate_limiter,
            max_retries=opts.get('_maxretries', 3)
        )
        
        # Create DNS resolver
        self.dns_resolver = AsyncDnsResolver(
            timeout=opts.get('_dns_timeout', 5.0),
            max_concurrent=opts.get('_dns_max_concurrent', 20),
            rate_limiter=self.rate_limiter
        )
        
        # Store event loop reference
        self._event_loop = asyncio.get_event_loop()
        
    async def cleanup_async(self) -> None:
        """Clean up async resources."""
        # Cancel all pending tasks
        for task in self._async_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._async_tasks:
            await asyncio.gather(*self._async_tasks, return_exceptions=True)
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.close()
            
        # Close DNS resolver (clear cache)
        if self.dns_resolver:
            self.dns_resolver.clear_cache()
            
        # Signal shutdown
        self._shutdown_event.set()
        
    @abstractmethod
    async def handleEvent_async(self, event: SpiderFootEvent) -> None:
        """Async event handler to be implemented by subclasses.
        
        Args:
            event: The SpiderFoot event to process
        """
        raise NotImplementedError("Subclasses must implement handleEvent_async")
        
    def handleEvent(self, event: SpiderFootEvent) -> None:
        """Synchronous wrapper for async event handling.
        
        This method allows async plugins to work with the existing
        synchronous plugin system.
        
        Args:
            event: The SpiderFoot event to process
        """
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            task = loop.create_task(self.handleEvent_async(event))
            self._async_tasks.add(task)
            task.add_done_callback(self._async_tasks.discard)
        except RuntimeError:
            # No event loop, run synchronously
            asyncio.run(self.handleEvent_async(event))
            
    async def _concurrent_fetch(self, urls: List[str], 
                               headers: Optional[Dict[str, str]] = None,
                               max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """Fetch multiple URLs concurrently.
        
        Args:
            urls: List of URLs to fetch
            headers: Optional headers to include
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of response data dictionaries
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.http_client.get(url, headers=headers)
                except Exception as e:
                    self.error(f"Error fetching {url}: {e}")
                    return {"error": str(e), "url": url}
        
        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)
        
    async def _batch_process(self, items: List[Any], 
                           processor_func: Any,
                           batch_size: int = 100,
                           max_concurrent: int = 10) -> List[Any]:
        """Process items in batches with concurrency control.
        
        Args:
            items: Items to process
            processor_func: Async function to process each item
            batch_size: Size of each batch
            max_concurrent: Max concurrent processing tasks
            
        Returns:
            List of processed results
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(item: Any) -> Any:
            async with semaphore:
                return await processor_func(item)
        
        # Process in batches
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_tasks = [process_with_semaphore(item) for item in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Filter out exceptions
            for result in batch_results:
                if not isinstance(result, Exception):
                    results.append(result)
                else:
                    self.error(f"Batch processing error: {result}")
                    
        return results
        
    @asynccontextmanager
    async def _rate_limited(self, resource: str = "default"):
        """Context manager for rate-limited operations.
        
        Args:
            resource: Resource identifier for rate limiting
            
        Example:
            async with self._rate_limited("shodan_api"):
                result = await self.http_client.get(url)
        """
        if self.rate_limiter:
            await self.rate_limiter.acquire(resource)
        try:
            yield
        finally:
            if self.rate_limiter:
                await self.rate_limiter.release(resource)
                
    async def _with_timeout(self, coro: Any, timeout: float) -> Any:
        """Execute coroutine with timeout.
        
        Args:
            coro: Coroutine to execute
            timeout: Timeout in seconds
            
        Returns:
            Coroutine result
            
        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        return await asyncio.wait_for(coro, timeout=timeout)
        
    def create_background_task(self, coro: Any) -> asyncio.Task:
        """Create a background task that's tracked by the plugin.
        
        Args:
            coro: Coroutine to run in background
            
        Returns:
            The created task
        """
        task = asyncio.create_task(coro)
        self._async_tasks.add(task)
        task.add_done_callback(self._async_tasks.discard)
        return task
        
    @property
    def is_async(self) -> bool:
        """Check if plugin is running in async mode."""
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False
            
    async def sleep(self, seconds: float) -> None:
        """Async sleep that checks for shutdown.
        
        Args:
            seconds: Seconds to sleep
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=seconds
            )
        except asyncio.TimeoutError:
            pass


class AsyncDnsResolver:
    """Placeholder for async DNS resolver.
    
    Will be implemented in a separate module.
    """
    pass