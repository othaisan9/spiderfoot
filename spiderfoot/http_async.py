"""Asynchronous HTTP Client for SpiderFoot

High-performance async HTTP client with connection pooling,
automatic retries, proxy support, and rate limiting.
"""

from __future__ import annotations
import asyncio
import json
import ssl
from typing import Optional, Dict, Any, Union, List, Tuple
from urllib.parse import urljoin, urlparse
import time
import logging
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientError

try:
    from aiohttp_socks import ProxyConnector
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    ProxyConnector = None

from .rate_limiter import RateLimiter


class AsyncHttpClient:
    """Asynchronous HTTP client with advanced features.
    
    Features:
        - Connection pooling
        - Automatic retries with exponential backoff
        - Proxy support (HTTP/SOCKS)
        - Rate limiting
        - Request/response logging
        - Custom headers and cookies
        - Streaming support
        - Timeout management
    """
    
    def __init__(self,
                 proxy: Optional[str] = None,
                 timeout: float = 30.0,
                 rate_limiter: Optional[RateLimiter] = None,
                 max_retries: int = 3,
                 max_connections: int = 100,
                 max_connections_per_host: int = 10,
                 headers: Optional[Dict[str, str]] = None,
                 verify_ssl: bool = True) -> None:
        """Initialize the async HTTP client.
        
        Args:
            proxy: Proxy URL (e.g., "socks5://localhost:9050")
            timeout: Default timeout in seconds
            rate_limiter: Rate limiter instance
            max_retries: Maximum number of retries
            max_connections: Total connection pool size
            max_connections_per_host: Max connections per host
            headers: Default headers to include
            verify_ssl: Whether to verify SSL certificates
        """
        self.proxy = proxy
        self.timeout = ClientTimeout(total=timeout)
        self.rate_limiter = rate_limiter
        self.max_retries = max_retries
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.default_headers = headers or {}
        self.verify_ssl = verify_ssl
        
        self._session: Optional[ClientSession] = None
        self._connector: Optional[Union[aiohttp.TCPConnector, ProxyConnector]] = None
        self.logger = logging.getLogger(f"spiderfoot.{self.__class__.__name__}")
        
        # Statistics
        self.stats = {
            "requests": 0,
            "errors": 0,
            "retries": 0,
            "total_time": 0.0
        }
        
    async def __aenter__(self) -> AsyncHttpClient:
        """Async context manager entry."""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
        
    async def _ensure_session(self) -> None:
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            # Create SSL context
            ssl_context = None
            if not self.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create connector
            if self.proxy:
                if self.proxy.startswith("socks") and SOCKS_AVAILABLE:
                    self._connector = ProxyConnector.from_url(self.proxy, ssl=ssl_context)
                else:
                    # Regular HTTP proxy handled by session or SOCKS not available
                    self._connector = aiohttp.TCPConnector(
                        limit=self.max_connections,
                        limit_per_host=self.max_connections_per_host,
                        ssl=ssl_context
                    )
            else:
                self._connector = aiohttp.TCPConnector(
                    limit=self.max_connections,
                    limit_per_host=self.max_connections_per_host,
                    ssl=ssl_context
                )
            
            # Create session
            self._session = ClientSession(
                connector=self._connector,
                timeout=self.timeout,
                headers=self.default_headers
            )
            
    async def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            # Wait a bit for connections to close properly
            await asyncio.sleep(0.1)
            
    async def _request(self,
                      method: str,
                      url: str,
                      headers: Optional[Dict[str, str]] = None,
                      params: Optional[Dict[str, Any]] = None,
                      data: Optional[Union[str, bytes, Dict[str, Any]]] = None,
                      json_data: Optional[Dict[str, Any]] = None,
                      cookies: Optional[Dict[str, str]] = None,
                      allow_redirects: bool = True,
                      timeout: Optional[float] = None,
                      stream: bool = False) -> aiohttp.ClientResponse:
        """Make an HTTP request with retries and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            headers: Request headers
            params: URL parameters
            data: Form data or raw body
            json_data: JSON data to send
            cookies: Cookies to include
            allow_redirects: Follow redirects
            timeout: Override default timeout
            stream: Return streaming response
            
        Returns:
            aiohttp ClientResponse object
            
        Raises:
            aiohttp.ClientError: On HTTP errors
            asyncio.TimeoutError: On timeout
        """
        await self._ensure_session()
        
        # Apply rate limiting
        domain = urlparse(url).netloc
        if self.rate_limiter:
            await self.rate_limiter.acquire(domain)
        
        # Merge headers
        req_headers = dict(self.default_headers)
        if headers:
            req_headers.update(headers)
        
        # Override timeout if specified
        req_timeout = ClientTimeout(total=timeout) if timeout else self.timeout
        
        # Prepare request kwargs
        kwargs = {
            "method": method,
            "url": url,
            "headers": req_headers,
            "params": params,
            "allow_redirects": allow_redirects,
            "timeout": req_timeout,
            "cookies": cookies,
            "proxy": self.proxy if not self.proxy or not self.proxy.startswith("socks") else None
        }
        
        if json_data:
            kwargs["json"] = json_data
        elif data:
            kwargs["data"] = data
        
        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            start_time = time.time()
            
            try:
                self.stats["requests"] += 1
                
                async with self._session.request(**kwargs) as response:
                    self.stats["total_time"] += time.time() - start_time
                    
                    # Log request
                    self.logger.debug(f"{method} {url} - Status: {response.status}")
                    
                    # Check for errors
                    response.raise_for_status()
                    
                    # Return response for streaming
                    if stream:
                        return response
                    
                    # Read content for non-streaming
                    await response.read()
                    return response
                    
            except (ClientError, asyncio.TimeoutError) as e:
                self.stats["errors"] += 1
                last_error = e
                
                # Log error
                self.logger.warning(f"Request failed ({attempt + 1}/{self.max_retries}): {e}")
                
                # Don't retry on certain errors
                if isinstance(e, aiohttp.ClientResponseError):
                    if e.status in [400, 401, 403, 404]:
                        raise
                
                # Exponential backoff
                if attempt < self.max_retries - 1:
                    self.stats["retries"] += 1
                    wait_time = (2 ** attempt) + (0.1 * asyncio.create_task(asyncio.sleep(0)).done())
                    await asyncio.sleep(wait_time)
                    
        # All retries failed
        raise last_error or ClientError("Request failed")
        
    async def get(self,
                  url: str,
                  headers: Optional[Dict[str, str]] = None,
                  params: Optional[Dict[str, Any]] = None,
                  **kwargs) -> Dict[str, Any]:
        """Make a GET request.
        
        Args:
            url: Target URL
            headers: Request headers
            params: URL parameters
            **kwargs: Additional arguments for _request
            
        Returns:
            Response data as dictionary
        """
        response = await self._request("GET", url, headers=headers, params=params, **kwargs)
        return await self._process_response(response)
        
    async def post(self,
                   url: str,
                   headers: Optional[Dict[str, str]] = None,
                   data: Optional[Union[str, bytes, Dict[str, Any]]] = None,
                   json_data: Optional[Dict[str, Any]] = None,
                   **kwargs) -> Dict[str, Any]:
        """Make a POST request.
        
        Args:
            url: Target URL
            headers: Request headers
            data: Form data or raw body
            json_data: JSON data to send
            **kwargs: Additional arguments for _request
            
        Returns:
            Response data as dictionary
        """
        response = await self._request("POST", url, headers=headers, 
                                     data=data, json_data=json_data, **kwargs)
        return await self._process_response(response)
        
    async def head(self,
                   url: str,
                   headers: Optional[Dict[str, str]] = None,
                   **kwargs) -> Dict[str, Any]:
        """Make a HEAD request.
        
        Args:
            url: Target URL
            headers: Request headers
            **kwargs: Additional arguments for _request
            
        Returns:
            Response headers as dictionary
        """
        response = await self._request("HEAD", url, headers=headers, **kwargs)
        return {
            "status": response.status,
            "headers": dict(response.headers),
            "url": str(response.url)
        }
        
    async def download(self,
                      url: str,
                      chunk_size: int = 8192,
                      progress_callback: Optional[Any] = None,
                      **kwargs) -> bytes:
        """Download content with optional progress callback.
        
        Args:
            url: Target URL
            chunk_size: Size of chunks to read
            progress_callback: Async callback(downloaded, total)
            **kwargs: Additional arguments for _request
            
        Returns:
            Downloaded content as bytes
        """
        response = await self._request("GET", url, stream=True, **kwargs)
        
        try:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunks = []
            
            async for chunk in response.content.iter_chunked(chunk_size):
                chunks.append(chunk)
                downloaded += len(chunk)
                
                if progress_callback:
                    await progress_callback(downloaded, total_size)
                    
            return b"".join(chunks)
            
        finally:
            response.close()
            
    async def _process_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Process response and return standardized data.
        
        Args:
            response: aiohttp response object
            
        Returns:
            Dictionary with response data
        """
        # Determine content type
        content_type = response.headers.get("Content-Type", "").lower()
        
        # Read content
        if "application/json" in content_type:
            try:
                content = await response.json()
            except json.JSONDecodeError:
                content = await response.text()
        elif "text" in content_type or "html" in content_type:
            content = await response.text()
        else:
            content = await response.read()
            
        return {
            "status": response.status,
            "headers": dict(response.headers),
            "content": content,
            "url": str(response.url),
            "cookies": {k: v.value for k, v in response.cookies.items()}
        }
        
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = dict(self.stats)
        if stats["requests"] > 0:
            stats["avg_time"] = stats["total_time"] / stats["requests"]
            stats["error_rate"] = stats["errors"] / stats["requests"]
        else:
            stats["avg_time"] = 0.0
            stats["error_rate"] = 0.0
            
        return stats
        
    async def batch_get(self,
                       urls: List[str],
                       max_concurrent: int = 10,
                       **kwargs) -> List[Dict[str, Any]]:
        """Fetch multiple URLs concurrently.
        
        Args:
            urls: List of URLs to fetch
            max_concurrent: Maximum concurrent requests
            **kwargs: Additional arguments for get()
            
        Returns:
            List of response data dictionaries
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.get(url, **kwargs)
                except Exception as e:
                    return {
                        "error": str(e),
                        "url": url,
                        "status": 0
                    }
                    
        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)