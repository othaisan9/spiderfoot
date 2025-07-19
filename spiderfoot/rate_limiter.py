"""Rate Limiter for SpiderFoot

Token bucket algorithm implementation for rate limiting API calls
and preventing overwhelming target servers.
"""

from __future__ import annotations
import asyncio
import time
from collections import defaultdict
from typing import Dict, Optional, Union
import logging


class RateLimiter:
    """Async rate limiter using token bucket algorithm.
    
    Supports both global rate limiting and per-resource limiting.
    Uses a token bucket algorithm where tokens are replenished at
    a fixed rate and consumed by requests.
    """
    
    def __init__(self,
                 global_limit: int = 10,
                 per_second: float = 1.0,
                 burst_size: Optional[int] = None) -> None:
        """Initialize the rate limiter.
        
        Args:
            global_limit: Maximum concurrent operations
            per_second: Token replenishment rate
            burst_size: Maximum burst size (defaults to global_limit)
        """
        self.global_limit = global_limit
        self.per_second = per_second
        self.burst_size = burst_size or global_limit
        
        # Token buckets per resource
        self._buckets: Dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.burst_size, self.per_second)
        )
        
        # Global semaphore for concurrent operations
        self._global_semaphore = asyncio.Semaphore(global_limit)
        
        # Resource-specific semaphores
        self._resource_semaphores: Dict[str, asyncio.Semaphore] = {}
        
        # Statistics
        self.stats: Dict[str, int] = defaultdict(int)
        self.logger = logging.getLogger(f"spiderfoot.{self.__class__.__name__}")
        
    async def acquire(self, resource: str = "default", tokens: int = 1) -> None:
        """Acquire permission to proceed with rate-limited operation.
        
        Args:
            resource: Resource identifier (e.g., domain name)
            tokens: Number of tokens to consume
        """
        # Global rate limiting
        await self._global_semaphore.acquire()
        
        # Per-resource rate limiting
        if resource not in self._resource_semaphores:
            # Create a semaphore with 1/10th of global limit per resource
            limit = max(1, self.global_limit // 10)
            self._resource_semaphores[resource] = asyncio.Semaphore(limit)
            
        resource_sem = self._resource_semaphores[resource]
        await resource_sem.acquire()
        
        # Token bucket rate limiting
        bucket = self._buckets[resource]
        await bucket.consume(tokens)
        
        # Update statistics
        self.stats[f"{resource}_requests"] += 1
        self.stats["total_requests"] += 1
        
        self.logger.debug(f"Rate limit acquired for {resource} ({tokens} tokens)")
        
    async def release(self, resource: str = "default") -> None:
        """Release rate limit resources.
        
        Args:
            resource: Resource identifier
        """
        # Release semaphores
        self._global_semaphore.release()
        
        if resource in self._resource_semaphores:
            self._resource_semaphores[resource].release()
            
        self.logger.debug(f"Rate limit released for {resource}")
        
    def set_limit(self, resource: str, per_second: float, burst_size: Optional[int] = None) -> None:
        """Set custom rate limit for specific resource.
        
        Args:
            resource: Resource identifier
            per_second: Tokens per second
            burst_size: Maximum burst size
        """
        burst = burst_size or int(per_second * 2)
        self._buckets[resource] = TokenBucket(burst, per_second)
        self.logger.info(f"Set rate limit for {resource}: {per_second}/s, burst: {burst}")
        
    def get_stats(self) -> Dict[str, Union[int, float]]:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = dict(self.stats)
        
        # Add bucket information
        stats["active_buckets"] = len(self._buckets)
        stats["active_resources"] = list(self._buckets.keys())
        
        return stats
        
    async def wait_if_needed(self, resource: str = "default") -> float:
        """Check if rate limit would block and return wait time.
        
        Args:
            resource: Resource identifier
            
        Returns:
            Seconds to wait (0 if no wait needed)
        """
        bucket = self._buckets[resource]
        return bucket.time_until_token()


class TokenBucket:
    """Token bucket implementation for rate limiting.
    
    Tokens are added at a fixed rate and consumed by operations.
    Operations block until tokens are available.
    """
    
    def __init__(self, capacity: int, refill_rate: float) -> None:
        """Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        
    async def consume(self, tokens: int = 1) -> None:
        """Consume tokens from the bucket.
        
        Blocks until enough tokens are available.
        
        Args:
            tokens: Number of tokens to consume
        """
        async with self._lock:
            while True:
                self._refill()
                
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                    
                # Calculate wait time
                needed = tokens - self._tokens
                wait_time = needed / self.refill_rate
                
                # Wait for tokens
                await asyncio.sleep(wait_time)
                
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self._tokens = min(self.capacity, self._tokens + tokens_to_add)
        
        self._last_refill = now
        
    def time_until_token(self, tokens: int = 1) -> float:
        """Calculate time until tokens are available.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds until tokens available (0 if available now)
        """
        self._refill()
        
        if self._tokens >= tokens:
            return 0.0
            
        needed = tokens - self._tokens
        return needed / self.refill_rate


class DomainRateLimiter(RateLimiter):
    """Specialized rate limiter for per-domain limiting.
    
    Useful for respecting robots.txt crawl-delay and being
    polite to target servers.
    """
    
    def __init__(self,
                 default_delay: float = 1.0,
                 max_concurrent_per_domain: int = 2) -> None:
        """Initialize domain rate limiter.
        
        Args:
            default_delay: Default delay between requests to same domain
            max_concurrent_per_domain: Max concurrent requests per domain
        """
        super().__init__(
            global_limit=max_concurrent_per_domain * 10,
            per_second=1.0 / default_delay
        )
        
        self.default_delay = default_delay
        self.max_concurrent_per_domain = max_concurrent_per_domain
        
        # Domain-specific delays (e.g., from robots.txt)
        self._domain_delays: Dict[str, float] = {}
        
    def set_domain_delay(self, domain: str, delay: float) -> None:
        """Set custom delay for specific domain.
        
        Args:
            domain: Domain name
            delay: Delay in seconds between requests
        """
        self._domain_delays[domain] = delay
        self.set_limit(domain, 1.0 / delay, burst_size=1)
        
    def get_domain_delay(self, domain: str) -> float:
        """Get delay for domain.
        
        Args:
            domain: Domain name
            
        Returns:
            Delay in seconds
        """
        return self._domain_delays.get(domain, self.default_delay)


# Example usage for different API services
class ApiRateLimits:
    """Pre-configured rate limits for common APIs."""
    
    SHODAN = {"per_second": 1.0, "burst_size": 1}  # 1 request/second
    VIRUSTOTAL = {"per_second": 4.0 / 60, "burst_size": 4}  # 4 requests/minute
    CENSYS = {"per_second": 0.4, "burst_size": 1}  # 2.5 seconds between requests
    HUNTER = {"per_second": 10.0 / 60, "burst_size": 10}  # 10 requests/minute
    SECURITYTRAILS = {"per_second": 2.0, "burst_size": 5}  # 2 requests/second
    GITHUB = {"per_second": 30.0 / 60, "burst_size": 10}  # 30 requests/minute
    
    @classmethod
    def configure_limiter(cls, limiter: RateLimiter) -> None:
        """Configure rate limiter with API limits.
        
        Args:
            limiter: Rate limiter to configure
        """
        for api, limits in cls.__dict__.items():
            if isinstance(limits, dict) and not api.startswith("_"):
                limiter.set_limit(
                    api.lower(),
                    limits["per_second"],
                    limits["burst_size"]
                )