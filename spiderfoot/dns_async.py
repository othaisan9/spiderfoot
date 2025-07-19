"""Asynchronous DNS Resolver for SpiderFoot

High-performance DNS resolution with caching, concurrent queries,
and intelligent fallback mechanisms.
"""

from __future__ import annotations
import asyncio
import socket
import time
from typing import Optional, List, Dict, Any, Union, Set, Tuple
from ipaddress import ip_address, IPv4Address, IPv6Address
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

try:
    import aiodns
    import pycares
    AIODNS_AVAILABLE = True
except ImportError:
    AIODNS_AVAILABLE = False

from .rate_limiter import RateLimiter


class AsyncDnsResolver:
    """Asynchronous DNS resolver with caching and rate limiting.
    
    Features:
        - Concurrent DNS queries with connection pooling
        - Intelligent caching with TTL support
        - Rate limiting to prevent overwhelming DNS servers
        - Fallback to multiple DNS servers
        - Support for A, AAAA, CNAME, MX, TXT, PTR records
        - IPv4 and IPv6 resolution
        - Reverse DNS lookups
        - Batch processing for multiple domains
    """
    
    def __init__(self,
                 nameservers: Optional[List[str]] = None,
                 timeout: float = 5.0,
                 max_concurrent: int = 50,
                 cache_ttl: int = 300,
                 rate_limiter: Optional[RateLimiter] = None) -> None:
        """Initialize the async DNS resolver.
        
        Args:
            nameservers: List of DNS servers to use
            timeout: DNS query timeout in seconds
            max_concurrent: Maximum concurrent queries
            cache_ttl: Default cache TTL in seconds
            rate_limiter: Rate limiter instance
        """
        self.nameservers = nameservers or [
            '8.8.8.8',      # Google
            '1.1.1.1',      # Cloudflare
            '208.67.222.222', # OpenDNS
            '9.9.9.9'       # Quad9
        ]
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.cache_ttl = cache_ttl
        self.rate_limiter = rate_limiter
        
        # DNS cache: {query_key: (result, timestamp, ttl)}
        self._cache: Dict[str, Tuple[Any, float, int]] = {}
        
        # Statistics
        self.stats = defaultdict(int)
        
        # Create aiodns resolver if available
        self._resolver = None
        if AIODNS_AVAILABLE:
            self._resolver = aiodns.DNSResolver(
                nameservers=self.nameservers,
                timeout=timeout
            )
        
        self.logger = logging.getLogger(f"spiderfoot.{self.__class__.__name__}")
        
        # Semaphore for concurrent queries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
    def _cache_key(self, name: str, record_type: str) -> str:
        """Generate cache key for DNS query."""
        return f"{name.lower()}:{record_type}"
        
    def _is_cached(self, cache_key: str) -> bool:
        """Check if result is cached and not expired."""
        if cache_key not in self._cache:
            return False
            
        result, timestamp, ttl = self._cache[cache_key]
        if time.time() - timestamp > ttl:
            del self._cache[cache_key]
            return False
            
        return True
        
    def _get_cached(self, cache_key: str) -> Any:
        """Get cached result."""
        if self._is_cached(cache_key):
            result, _, _ = self._cache[cache_key]
            self.stats['cache_hits'] += 1
            return result
        return None
        
    def _set_cache(self, cache_key: str, result: Any, ttl: Optional[int] = None) -> None:
        """Set cached result."""
        ttl = ttl or self.cache_ttl
        self._cache[cache_key] = (result, time.time(), ttl)
        
    async def _query_with_fallback(self, name: str, record_type: str) -> Any:
        """Query DNS with fallback to multiple servers."""
        last_error = None
        
        # Try aiodns first if available
        if self._resolver:
            try:
                if record_type == 'A':
                    result = await self._resolver.query(name, 'A')
                    return [r.host for r in result]
                elif record_type == 'AAAA':
                    result = await self._resolver.query(name, 'AAAA')
                    return [r.host for r in result]
                elif record_type == 'CNAME':
                    result = await self._resolver.query(name, 'CNAME')
                    return result.cname
                elif record_type == 'MX':
                    result = await self._resolver.query(name, 'MX')
                    return [(r.host, r.priority) for r in result]
                elif record_type == 'TXT':
                    result = await self._resolver.query(name, 'TXT')
                    return [r.text for r in result]
                elif record_type == 'PTR':
                    result = await self._resolver.query(name, 'PTR')
                    return result.name
                    
            except Exception as e:
                last_error = e
                self.logger.debug(f"aiodns query failed for {name} {record_type}: {e}")
        
        # Fallback to asyncio's built-in resolver
        try:
            if record_type == 'A':
                result = await asyncio.get_event_loop().getaddrinfo(
                    name, None, family=socket.AF_INET
                )
                return [r[4][0] for r in result]
            elif record_type == 'AAAA':
                result = await asyncio.get_event_loop().getaddrinfo(
                    name, None, family=socket.AF_INET6
                )
                return [r[4][0] for r in result]
                
        except Exception as e:
            last_error = e
            self.logger.debug(f"asyncio resolver failed for {name} {record_type}: {e}")
        
        if last_error:
            raise last_error
        return None
        
    @asynccontextmanager
    async def _rate_limited_query(self, server: str = "default"):
        """Context manager for rate-limited DNS queries."""
        async with self._semaphore:
            if self.rate_limiter:
                await self.rate_limiter.acquire(f"dns:{server}")
            try:
                yield
            finally:
                if self.rate_limiter:
                    await self.rate_limiter.release(f"dns:{server}")
                    
    async def resolve_a(self, name: str) -> List[str]:
        """Resolve A record (IPv4 addresses)."""
        cache_key = self._cache_key(name, 'A')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(name, 'A'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['a_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"A record query failed for {name}: {e}")
                self.stats['a_failures'] += 1
                
        return []
        
    async def resolve_aaaa(self, name: str) -> List[str]:
        """Resolve AAAA record (IPv6 addresses)."""
        cache_key = self._cache_key(name, 'AAAA')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(name, 'AAAA'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['aaaa_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"AAAA record query failed for {name}: {e}")
                self.stats['aaaa_failures'] += 1
                
        return []
        
    async def resolve_any(self, name: str) -> List[str]:
        """Resolve both A and AAAA records."""
        tasks = [
            self.resolve_a(name),
            self.resolve_aaaa(name)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_ips = []
        for result in results:
            if isinstance(result, list):
                all_ips.extend(result)
                
        return all_ips
        
    async def resolve_cname(self, name: str) -> Optional[str]:
        """Resolve CNAME record."""
        cache_key = self._cache_key(name, 'CNAME')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(name, 'CNAME'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['cname_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"CNAME query failed for {name}: {e}")
                self.stats['cname_failures'] += 1
                
        return None
        
    async def resolve_mx(self, name: str) -> List[Tuple[str, int]]:
        """Resolve MX records."""
        cache_key = self._cache_key(name, 'MX')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(name, 'MX'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['mx_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"MX query failed for {name}: {e}")
                self.stats['mx_failures'] += 1
                
        return []
        
    async def resolve_txt(self, name: str) -> List[str]:
        """Resolve TXT records."""
        cache_key = self._cache_key(name, 'TXT')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(name, 'TXT'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['txt_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"TXT query failed for {name}: {e}")
                self.stats['txt_failures'] += 1
                
        return []
        
    async def resolve_ptr(self, ip: str) -> Optional[str]:
        """Reverse DNS lookup (PTR record)."""
        try:
            # Validate IP address
            ip_obj = ip_address(ip)
            if isinstance(ip_obj, IPv4Address):
                # Create reverse IP for IPv4
                octets = str(ip_obj).split('.')
                reverse_name = f"{'.'.join(reversed(octets))}.in-addr.arpa"
            else:
                # Create reverse IP for IPv6
                hex_chars = ip_obj.exploded.replace(':', '')
                reverse_name = f"{'.'.join(reversed(hex_chars))}.ip6.arpa"
                
        except Exception as e:
            self.logger.error(f"Invalid IP address for PTR lookup: {ip}")
            return None
            
        cache_key = self._cache_key(reverse_name, 'PTR')
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
            
        async with self._rate_limited_query():
            try:
                result = await asyncio.wait_for(
                    self._query_with_fallback(reverse_name, 'PTR'),
                    timeout=self.timeout
                )
                
                if result:
                    self._set_cache(cache_key, result)
                    self.stats['ptr_queries'] += 1
                    return result
                    
            except Exception as e:
                self.logger.debug(f"PTR query failed for {ip}: {e}")
                self.stats['ptr_failures'] += 1
                
        return None
        
    async def batch_resolve_a(self, names: List[str]) -> Dict[str, List[str]]:
        """Resolve A records for multiple domains concurrently."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def resolve_with_semaphore(name: str) -> Tuple[str, List[str]]:
            async with semaphore:
                result = await self.resolve_a(name)
                return (name, result)
                
        tasks = [resolve_with_semaphore(name) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                name, ips = result
                output[name] = ips
            elif isinstance(result, Exception):
                self.logger.error(f"Batch resolve error: {result}")
                
        return output
        
    async def batch_resolve_ptr(self, ips: List[str]) -> Dict[str, Optional[str]]:
        """Reverse DNS lookup for multiple IPs concurrently."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def resolve_with_semaphore(ip: str) -> Tuple[str, Optional[str]]:
            async with semaphore:
                result = await self.resolve_ptr(ip)
                return (ip, result)
                
        tasks = [resolve_with_semaphore(ip) for ip in ips]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for result in results:
            if isinstance(result, tuple) and len(result) == 2:
                ip, hostname = result
                output[ip] = hostname
            elif isinstance(result, Exception):
                self.logger.error(f"Batch PTR resolve error: {result}")
                
        return output
        
    def clear_cache(self) -> None:
        """Clear DNS cache."""
        self._cache.clear()
        self.logger.info("DNS cache cleared")
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self._cache)
        expired_entries = 0
        
        current_time = time.time()
        for result, timestamp, ttl in self._cache.values():
            if current_time - timestamp > ttl:
                expired_entries += 1
                
        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'valid_entries': total_entries - expired_entries,
            'cache_hit_rate': self.stats['cache_hits'] / max(1, sum(
                self.stats[k] for k in self.stats if k.endswith('_queries')
            ))
        }
        
    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        stats = dict(self.stats)
        stats.update(self.get_cache_stats())
        return stats


class DnsResolverPool:
    """Pool of DNS resolvers for load balancing."""
    
    def __init__(self, 
                 pool_size: int = 3,
                 nameserver_groups: Optional[List[List[str]]] = None,
                 **kwargs) -> None:
        """Initialize resolver pool.
        
        Args:
            pool_size: Number of resolvers in pool
            nameserver_groups: Groups of nameservers for each resolver
            **kwargs: Arguments passed to AsyncDnsResolver
        """
        self.pool_size = pool_size
        self.nameserver_groups = nameserver_groups or [
            ['8.8.8.8', '8.8.4.4'],      # Google
            ['1.1.1.1', '1.0.0.1'],      # Cloudflare
            ['208.67.222.222', '208.67.220.220'],  # OpenDNS
        ]
        
        self.resolvers: List[AsyncDnsResolver] = []
        self.current_resolver = 0
        
        # Create resolver pool
        for i in range(pool_size):
            nameservers = self.nameserver_groups[i % len(self.nameserver_groups)]
            resolver = AsyncDnsResolver(nameservers=nameservers, **kwargs)
            self.resolvers.append(resolver)
            
    def _get_resolver(self) -> AsyncDnsResolver:
        """Get next resolver from pool (round-robin)."""
        resolver = self.resolvers[self.current_resolver]
        self.current_resolver = (self.current_resolver + 1) % len(self.resolvers)
        return resolver
        
    async def resolve_a(self, name: str) -> List[str]:
        """Resolve A record using pool."""
        resolver = self._get_resolver()
        return await resolver.resolve_a(name)
        
    async def resolve_aaaa(self, name: str) -> List[str]:
        """Resolve AAAA record using pool."""
        resolver = self._get_resolver()
        return await resolver.resolve_aaaa(name)
        
    async def resolve_any(self, name: str) -> List[str]:
        """Resolve both A and AAAA records using pool."""
        resolver = self._get_resolver()
        return await resolver.resolve_any(name)
        
    async def resolve_ptr(self, ip: str) -> Optional[str]:
        """Reverse DNS lookup using pool."""
        resolver = self._get_resolver()
        return await resolver.resolve_ptr(ip)
        
    def get_combined_stats(self) -> Dict[str, Any]:
        """Get combined statistics from all resolvers."""
        combined = defaultdict(int)
        
        for resolver in self.resolvers:
            stats = resolver.get_stats()
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    combined[key] += value
                    
        return dict(combined)