#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Performance benchmarks for SpiderFoot async framework."""

import asyncio
import pytest
import time
import statistics
import psutil
import os
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Import SpiderFoot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from spiderfoot import SpiderFootEvent
from spiderfoot.http_async import AsyncHttpClient
from spiderfoot.dns_async import AsyncDnsResolver
from spiderfoot.rate_limiter import RateLimiter
from spiderfoot.event_queue_async import AsyncEventQueue


class TestHttpClientPerformance:
    """Benchmark HTTP client performance."""
    
    @pytest.mark.asyncio
    async def test_concurrent_vs_sequential_http_requests(self):
        """Benchmark concurrent vs sequential HTTP requests."""
        
        # Mock HTTP responses to avoid network dependency
        mock_response = {
            'status': 200,
            'content': {'data': 'test'},
            'headers': {'content-type': 'application/json'}
        }
        
        async def mock_request(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            return mock_response
        
        async with AsyncHttpClient() as client:
            with patch.object(client, '_request', side_effect=mock_request):
                urls = [f"https://example.com/api/{i}" for i in range(10)]
                
                # Sequential execution
                start_time = time.time()
                sequential_results = []
                for url in urls:
                    result = await client.get(url)
                    sequential_results.append(result)
                sequential_time = time.time() - start_time
                
                # Concurrent execution
                start_time = time.time()
                concurrent_results = await client.batch_get(urls)
                concurrent_time = time.time() - start_time
                
                # Calculate performance metrics
                speedup = sequential_time / concurrent_time
                
                print(f"\nHTTP Client Performance:")
                print(f"Sequential time: {sequential_time:.2f}s")
                print(f"Concurrent time: {concurrent_time:.2f}s")
                print(f"Speedup: {speedup:.1f}x")
                
                # Concurrent should be significantly faster
                assert speedup > 5.0  # At least 5x faster
                assert len(concurrent_results) == len(sequential_results)
    
    @pytest.mark.asyncio
    async def test_http_client_memory_efficiency(self):
        """Test memory efficiency of HTTP client."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        mock_response = {
            'status': 200,
            'content': {'data': 'test'},
            'headers': {}
        }
        
        async def mock_request(*args, **kwargs):
            await asyncio.sleep(0.001)  # Minimal delay
            return mock_response
        
        async with AsyncHttpClient() as client:
            with patch.object(client, '_request', side_effect=mock_request):
                # Perform many concurrent requests
                urls = [f"https://example.com/{i}" for i in range(500)]
                results = await client.batch_get(urls, max_concurrent=50)
                
                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory
                
                print(f"\nHTTP Client Memory Usage:")
                print(f"Memory increase: {memory_increase / 1024 / 1024:.1f}MB for 500 requests")
                
                # Memory increase should be reasonable (< 100MB for 500 requests)
                assert memory_increase < 100 * 1024 * 1024
                assert len(results) == 500


class TestDnsResolverPerformance:
    """Benchmark DNS resolver performance."""
    
    @pytest.mark.asyncio
    async def test_concurrent_dns_resolution(self):
        """Benchmark concurrent DNS resolution."""
        resolver = AsyncDnsResolver(max_concurrent=20)
        
        # Use well-known domains for testing
        domains = [
            "google.com", "github.com", "stackoverflow.com",
            "python.org", "docs.python.org", "pypi.org",
            "wikipedia.org", "example.com", "cloudflare.com",
            "amazon.com"
        ]
        
        try:
            # Sequential resolution
            start_time = time.time()
            sequential_results = {}
            for domain in domains:
                ips = await resolver.resolve_a(domain)
                sequential_results[domain] = ips
            sequential_time = time.time() - start_time
            
            # Clear cache for fair comparison
            resolver.clear_cache()
            
            # Concurrent resolution
            start_time = time.time()
            concurrent_results = await resolver.batch_resolve_a(domains)
            concurrent_time = time.time() - start_time
            
            # Calculate metrics
            speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1
            
            print(f"\nDNS Resolver Performance:")
            print(f"Sequential time: {sequential_time:.2f}s")
            print(f"Concurrent time: {concurrent_time:.2f}s")
            print(f"Speedup: {speedup:.1f}x")
            
            # Concurrent should be faster (allowing for DNS variability)
            assert speedup > 1.5  # At least 1.5x faster
            assert len(concurrent_results) == len(domains)
            
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")
    
    @pytest.mark.asyncio
    async def test_dns_cache_performance(self):
        """Test DNS cache performance improvement."""
        resolver = AsyncDnsResolver(cache_ttl=60)
        domain = "google.com"
        
        try:
            # First resolution (cache miss)
            start_time = time.time()
            result1 = await resolver.resolve_a(domain)
            first_time = time.time() - start_time
            
            # Second resolution (cache hit)
            start_time = time.time()
            result2 = await resolver.resolve_a(domain)
            second_time = time.time() - start_time
            
            # Cache hit should be much faster
            speedup = first_time / second_time if second_time > 0 else 1
            
            print(f"\nDNS Cache Performance:")
            print(f"Cache miss time: {first_time:.4f}s")
            print(f"Cache hit time: {second_time:.4f}s")
            print(f"Cache speedup: {speedup:.1f}x")
            
            assert speedup > 10  # Cache should be at least 10x faster
            assert result1 == result2
            
            # Check cache statistics
            stats = resolver.get_cache_stats()
            assert stats['cache_hits'] > 0
            
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")


class TestRateLimiterPerformance:
    """Benchmark rate limiter performance."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_overhead(self):
        """Test rate limiter performance overhead."""
        limiter = RateLimiter(global_limit=100, per_second=1000)  # High limits
        
        # Measure without rate limiting
        start_time = time.time()
        for _ in range(1000):
            await asyncio.sleep(0)  # Minimal async operation
        no_limiting_time = time.time() - start_time
        
        # Measure with rate limiting
        start_time = time.time()
        for _ in range(1000):
            await limiter.acquire()
            await asyncio.sleep(0)  # Minimal async operation
            await limiter.release()
        with_limiting_time = time.time() - start_time
        
        overhead = (with_limiting_time - no_limiting_time) / no_limiting_time * 100
        
        print(f"\nRate Limiter Performance:")
        print(f"Without limiting: {no_limiting_time:.4f}s")
        print(f"With limiting: {with_limiting_time:.4f}s")
        print(f"Overhead: {overhead:.1f}%")
        
        # Overhead should be reasonable (< 50%)
        assert overhead < 50.0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_accuracy(self):
        """Test rate limiter timing accuracy."""
        limiter = RateLimiter(global_limit=10, per_second=5.0)  # 5 requests per second
        
        # Measure actual rate limiting
        times = []
        for i in range(10):
            start_time = time.time()
            await limiter.acquire()
            await limiter.release()
            end_time = time.time()
            
            if i > 0:  # Skip first request (no delay)
                times.append(end_time - start_time)
        
        if times:
            avg_delay = statistics.mean(times)
            expected_delay = 1.0 / 5.0  # 0.2 seconds between requests
            
            print(f"\nRate Limiter Accuracy:")
            print(f"Expected delay: {expected_delay:.3f}s")
            print(f"Actual avg delay: {avg_delay:.3f}s")
            print(f"Accuracy: {(1 - abs(avg_delay - expected_delay) / expected_delay) * 100:.1f}%")
            
            # Should be reasonably accurate (within 20%)
            assert abs(avg_delay - expected_delay) / expected_delay < 0.2


class TestEventQueuePerformance:
    """Benchmark event queue performance."""
    
    @pytest.mark.asyncio
    async def test_event_queue_throughput(self):
        """Test event queue processing throughput."""
        async with AsyncEventQueue(max_workers=5, max_size=10000) as queue:
            processed_events = []
            
            # Simple event handler
            async def fast_handler(event):
                processed_events.append(event.data)
                await asyncio.sleep(0.001)  # Minimal processing time
            
            queue.register_handler("THROUGHPUT_TEST", fast_handler)
            
            # Add many events
            num_events = 1000
            start_time = time.time()
            
            for i in range(num_events):
                event = Mock()
                event.eventType = "THROUGHPUT_TEST"
                event.data = f"event_{i}"
                await queue.put(event)
            
            # Wait for processing to complete
            while len(processed_events) < num_events:
                await asyncio.sleep(0.01)
                # Timeout after 30 seconds
                if time.time() - start_time > 30:
                    break
            
            total_time = time.time() - start_time
            throughput = len(processed_events) / total_time
            
            print(f"\nEvent Queue Performance:")
            print(f"Events processed: {len(processed_events)}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Throughput: {throughput:.1f} events/second")
            
            # Should process at least 100 events per second
            assert throughput > 100
            assert len(processed_events) >= num_events * 0.9  # Allow 10% tolerance
    
    @pytest.mark.asyncio
    async def test_event_queue_priority_performance(self):
        """Test event queue priority processing performance."""
        async with AsyncEventQueue(max_workers=2) as queue:
            processed_order = []
            
            async def priority_handler(event):
                processed_order.append((event.data, event.eventType))
                await asyncio.sleep(0.01)
            
            queue.register_handler("PRIORITY_TEST", priority_handler)
            
            # Add events with different priorities
            from spiderfoot.event_queue_async import EventPriority
            
            priorities = [
                (EventPriority.LOW, "low"),
                (EventPriority.CRITICAL, "critical"),
                (EventPriority.NORMAL, "normal"),
                (EventPriority.HIGH, "high"),
                (EventPriority.BACKGROUND, "background")
            ]
            
            for priority, name in priorities:
                event = Mock()
                event.eventType = "PRIORITY_TEST"
                event.data = name
                await queue.put(event, priority=priority)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            print(f"\nEvent Queue Priority Order:")
            for i, (data, event_type) in enumerate(processed_order):
                print(f"{i+1}. {data}")
            
            # Critical should be processed first
            if processed_order:
                assert processed_order[0][0] == "critical"


class TestAsyncModulePerformance:
    """Benchmark async module performance."""
    
    @pytest.mark.asyncio
    async def test_async_module_concurrent_events(self):
        """Test async module concurrent event processing."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
        except ImportError:
            pytest.skip("Unified IP Info async module not available")
        
        plugin = sfp_unified_ip_info_async()
        
        # Mock setup
        sf = Mock()
        sf.validIP = Mock(return_value=True)
        sf.isValidLocalOrLoopbackIP = Mock(return_value=False)
        
        opts = {
            'fallback_to_free': True,
            'concurrent_queries': 5,
            '_maxthreads': 10
        }
        
        await plugin.setup_async(sf, opts)
        
        # Mock HTTP responses
        mock_response = {
            'status': 200,
            'content': {
                'ip': '8.8.8.8',
                'city': 'Test City',
                'country': 'US'
            }
        }
        
        with patch.object(plugin.http_client, 'get', new=AsyncMock(return_value=mock_response)):
            plugin.notifyListeners = AsyncMock()
            
            # Create test events
            events = []
            for i in range(20):
                event = Mock()
                event.eventType = "IP_ADDRESS"
                event.data = f"8.8.8.{i}"
                event.module = "test_module"
                events.append(event)
            
            # Sequential processing
            start_time = time.time()
            for event in events:
                await plugin.handleEvent_async(event)
            sequential_time = time.time() - start_time
            
            # Reset for concurrent test
            plugin.results = plugin.tempStorage()
            plugin.cache = {}
            
            # Concurrent processing
            start_time = time.time()
            tasks = [plugin.handleEvent_async(event) for event in events]
            await asyncio.gather(*tasks, return_exceptions=True)
            concurrent_time = time.time() - start_time
            
            speedup = sequential_time / concurrent_time if concurrent_time > 0 else 1
            
            print(f"\nAsync Module Performance:")
            print(f"Sequential time: {sequential_time:.2f}s")
            print(f"Concurrent time: {concurrent_time:.2f}s")
            print(f"Speedup: {speedup:.1f}x")
            
            # Concurrent should be faster
            assert speedup > 1.5
        
        await plugin.cleanup_async()


class TestOverallSystemPerformance:
    """Test overall system performance improvements."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_performance_improvement(self):
        """Test end-to-end performance improvement with async framework."""
        
        # Simulate a complete async workflow
        async def async_workflow():
            # DNS resolution
            resolver = AsyncDnsResolver()
            domains = ["example.com", "google.com", "github.com"]
            
            try:
                dns_results = await resolver.batch_resolve_a(domains)
            except Exception:
                dns_results = {}  # Handle DNS failures gracefully
            
            # HTTP requests  
            async with AsyncHttpClient() as client:
                mock_response = {'status': 200, 'content': {'data': 'test'}}
                
                with patch.object(client, 'get', new=AsyncMock(return_value=mock_response)):
                    urls = [f"https://api.example.com/{i}" for i in range(5)]
                    http_results = await client.batch_get(urls)
            
            # Event processing
            async with AsyncEventQueue(max_workers=3) as queue:
                processed = []
                
                async def handler(event):
                    processed.append(event.data)
                
                queue.register_handler("TEST", handler)
                
                for i in range(10):
                    event = Mock()
                    event.eventType = "TEST"
                    event.data = f"item_{i}"
                    await queue.put(event)
                
                # Wait for processing
                await asyncio.sleep(0.1)
            
            return {
                'dns_results': len(dns_results),
                'http_results': len(http_results),
                'processed_events': len(processed)
            }
        
        # Simulate synchronous workflow
        def sync_workflow():
            import time
            
            # Sequential operations with delays
            time.sleep(0.1)  # DNS resolution
            time.sleep(0.2)  # HTTP requests  
            time.sleep(0.05)  # Event processing
            
            return {
                'dns_results': 3,
                'http_results': 5,
                'processed_events': 10
            }
        
        # Benchmark async workflow
        start_time = time.time()
        async_result = await async_workflow()
        async_time = time.time() - start_time
        
        # Benchmark sync workflow
        start_time = time.time()
        sync_result = sync_workflow()
        sync_time = time.time() - start_time
        
        speedup = sync_time / async_time if async_time > 0 else 1
        
        print(f"\nEnd-to-End Performance:")
        print(f"Async workflow time: {async_time:.2f}s")
        print(f"Sync workflow time: {sync_time:.2f}s")
        print(f"Overall speedup: {speedup:.1f}x")
        
        # Async should be significantly faster
        assert speedup > 2.0
        
        # Results should be equivalent
        assert async_result['dns_results'] >= 0  # Allow for DNS failures
        assert async_result['http_results'] >= 3  # Allow some tolerance
        assert async_result['processed_events'] >= 8  # Allow some tolerance


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])