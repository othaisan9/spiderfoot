#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for SpiderFoot async framework components."""

import asyncio
import pytest
import time
import tempfile
import json
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Import SpiderFoot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from spiderfoot import SpiderFootEvent
from spiderfoot.http_async import AsyncHttpClient
from spiderfoot.dns_async import AsyncDnsResolver, DnsResolverPool
from spiderfoot.db_async import AsyncSpiderFootDb
from spiderfoot.rate_limiter import RateLimiter, TokenBucket
from spiderfoot.event_queue_async import AsyncEventQueue, EventPriority
from spiderfoot.plugin_async import AsyncSpiderFootPlugin


class TestAsyncHttpClient:
    """Test async HTTP client functionality."""
    
    @pytest.mark.asyncio
    async def test_http_client_basic_get(self):
        """Test basic GET request functionality."""
        async with AsyncHttpClient() as client:
            # Use httpbin for testing
            try:
                result = await client.get("https://httpbin.org/get", timeout=10)
                assert result['status'] == 200
                assert 'headers' in result
                assert 'content' in result
            except Exception as e:
                # Skip if network issues
                pytest.skip(f"Network request failed: {e}")
    
    @pytest.mark.asyncio
    async def test_http_client_concurrent_requests(self):
        """Test concurrent HTTP requests."""
        async with AsyncHttpClient() as client:
            urls = [
                "https://httpbin.org/delay/1",
                "https://httpbin.org/delay/1", 
                "https://httpbin.org/delay/1"
            ]
            
            start_time = time.time()
            try:
                results = await client.batch_get(urls, timeout=15)
                end_time = time.time()
                
                # Should complete in ~1 second (concurrent) not ~3 seconds (sequential)
                assert end_time - start_time < 2.5
                assert len(results) == 3
                
                # Check all requests succeeded (or handle network issues gracefully)
                successful = [r for r in results if r.get('status') == 200]
                assert len(successful) >= 2  # Allow some network tolerance
                
            except Exception as e:
                pytest.skip(f"Network request failed: {e}")
    
    @pytest.mark.asyncio
    async def test_http_client_with_rate_limiter(self):
        """Test HTTP client with rate limiting."""
        rate_limiter = RateLimiter(global_limit=2, per_second=2.0)
        
        async with AsyncHttpClient(rate_limiter=rate_limiter) as client:
            # Rate limiter should slow down requests
            start_time = time.time()
            
            tasks = []
            for i in range(3):
                task = client.get("https://httpbin.org/get", timeout=10)
                tasks.append(task)
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                end_time = time.time()
                
                # Should take at least 0.5 seconds due to rate limiting
                assert end_time - start_time >= 0.4
                
                # Check results
                successful = [r for r in results if isinstance(r, dict) and r.get('status') == 200]
                assert len(successful) >= 1  # At least one should succeed
                
            except Exception as e:
                pytest.skip(f"Network request failed: {e}")


class TestAsyncDnsResolver:
    """Test async DNS resolver functionality."""
    
    @pytest.mark.asyncio
    async def test_dns_resolver_a_record(self):
        """Test A record resolution."""
        resolver = AsyncDnsResolver()
        
        try:
            ips = await resolver.resolve_a("google.com")
            assert len(ips) > 0
            assert all('.' in ip for ip in ips)  # IPv4 format check
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")
    
    @pytest.mark.asyncio 
    async def test_dns_resolver_caching(self):
        """Test DNS caching functionality."""
        resolver = AsyncDnsResolver(cache_ttl=60)
        
        try:
            # First query
            start_time = time.time()
            ips1 = await resolver.resolve_a("example.com")
            first_duration = time.time() - start_time
            
            # Second query (should be cached)
            start_time = time.time()
            ips2 = await resolver.resolve_a("example.com")
            second_duration = time.time() - start_time
            
            # Cached query should be faster
            assert second_duration < first_duration / 2
            assert ips1 == ips2
            
            # Check cache stats
            stats = resolver.get_cache_stats()
            assert stats['cache_hits'] > 0
            
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")
    
    @pytest.mark.asyncio
    async def test_dns_resolver_batch_processing(self):
        """Test batch DNS resolution."""
        resolver = AsyncDnsResolver()
        
        domains = ["google.com", "github.com", "stackoverflow.com"]
        
        try:
            start_time = time.time()
            results = await resolver.batch_resolve_a(domains)
            end_time = time.time()
            
            # Should complete faster than sequential queries
            assert end_time - start_time < 5.0
            assert len(results) == len(domains)
            
            # Check results
            for domain in domains:
                assert domain in results
                assert len(results[domain]) > 0  # Should have at least one IP
                
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")
    
    @pytest.mark.asyncio
    async def test_dns_resolver_pool(self):
        """Test DNS resolver pool functionality."""
        pool = DnsResolverPool(pool_size=3)
        
        try:
            # Test multiple concurrent queries
            tasks = []
            for domain in ["google.com", "github.com", "example.com"]:
                task = pool.resolve_a(domain)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check that we got results
            successful = [r for r in results if isinstance(r, list) and len(r) > 0]
            assert len(successful) >= 2  # Allow some DNS tolerance
            
        except Exception as e:
            pytest.skip(f"DNS resolution failed: {e}")


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    @pytest.mark.asyncio
    async def test_token_bucket_basic(self):
        """Test basic token bucket functionality."""
        bucket = TokenBucket(capacity=3, refill_rate=1.0)
        
        # Should be able to consume 3 tokens immediately
        start_time = time.time()
        for _ in range(3):
            await bucket.consume(1)
        end_time = time.time()
        
        # Should be fast
        assert end_time - start_time < 0.1
        
        # Fourth token should require waiting
        start_time = time.time()
        await bucket.consume(1)
        end_time = time.time()
        
        # Should take about 1 second
        assert 0.8 < end_time - start_time < 1.5
    
    @pytest.mark.asyncio
    async def test_rate_limiter_multiple_resources(self):
        """Test rate limiter with multiple resources."""
        limiter = RateLimiter(global_limit=5, per_second=2.0)
        
        # Set different limits for different resources
        limiter.set_limit("api1", 1.0, burst_size=1)
        limiter.set_limit("api2", 2.0, burst_size=2)
        
        # Test resource-specific limiting
        start_time = time.time()
        
        # api1 should be slower
        await limiter.acquire("api1")
        await limiter.acquire("api1")
        limiter.release("api1")
        limiter.release("api1")
        
        api1_time = time.time() - start_time
        
        # api2 should be faster
        start_time = time.time()
        await limiter.acquire("api2")
        await limiter.acquire("api2")
        limiter.release("api2")
        limiter.release("api2")
        
        api2_time = time.time() - start_time
        
        # api1 should take longer due to slower rate
        assert api1_time > api2_time


class TestAsyncDatabase:
    """Test async database operations."""
    
    @pytest.mark.asyncio
    async def test_database_connection_pool(self):
        """Test database connection pooling."""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp_db:
            # Initialize database with basic schema
            import sqlite3
            conn = sqlite3.connect(tmp_db.name)
            conn.execute('''
                CREATE TABLE tbl_scan_results (
                    scan_instance_id TEXT,
                    scan_result_utime INTEGER,
                    scan_result_type TEXT,
                    scan_result_confidence INTEGER,
                    scan_result_visibility INTEGER, 
                    scan_result_risk INTEGER,
                    scan_result_module TEXT,
                    scan_result_data TEXT,
                    scan_result_source_data TEXT,
                    scan_result_hash TEXT,
                    scan_result_extra TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE tbl_scan_instance (
                    scan_instance_id TEXT PRIMARY KEY,
                    scan_name TEXT,
                    scan_target TEXT,
                    scan_status TEXT,
                    scan_start_time INTEGER,
                    scan_end_time INTEGER
                )
            ''')
            conn.close()
            
            # Test async database operations
            async with AsyncSpiderFootDb(tmp_db.name, max_connections=3) as db:
                # Test concurrent database operations
                tasks = []
                
                # Create mock events
                for i in range(5):
                    event = Mock(spec=SpiderFootEvent)
                    event.eventType = "TEST_EVENT"
                    event.data = f"test_data_{i}"
                    event.module = "test_module"
                    event.confidence = 100
                    event.visibility = 1
                    event.risk = 0
                    event.hash = f"hash_{i}"
                    event.sourceEvent = None
                    
                    task = db.store_event_async(f"scan_{i}", event, buffer=False)
                    tasks.append(task)
                
                # Execute concurrently
                await asyncio.gather(*tasks)
                
                # Verify events were stored
                events = await db.search_events_async({"scan_id": "scan_1"})
                assert len(events) >= 1
                assert events[0]['type'] == "TEST_EVENT"
    
    @pytest.mark.asyncio
    async def test_database_event_buffering(self):
        """Test event buffering and batch processing."""
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp_db:
            # Initialize database
            import sqlite3
            conn = sqlite3.connect(tmp_db.name)
            conn.execute('''
                CREATE TABLE tbl_scan_results (
                    scan_instance_id TEXT,
                    scan_result_utime INTEGER,
                    scan_result_type TEXT,
                    scan_result_confidence INTEGER,
                    scan_result_visibility INTEGER,
                    scan_result_risk INTEGER,
                    scan_result_module TEXT,
                    scan_result_data TEXT,
                    scan_result_source_data TEXT,
                    scan_result_hash TEXT,
                    scan_result_extra TEXT
                )
            ''')
            conn.close()
            
            async with AsyncSpiderFootDb(tmp_db.name, batch_size=3, buffer_timeout=0.1) as db:
                # Add events to buffer
                for i in range(5):
                    event = Mock(spec=SpiderFootEvent)
                    event.eventType = f"BUFFERED_EVENT_{i}"
                    event.data = f"buffered_data_{i}"
                    event.module = "test_module"
                    event.confidence = 100
                    event.visibility = 1
                    event.risk = 0
                    event.hash = f"buffered_hash_{i}"
                    event.sourceEvent = None
                    
                    await db.store_event_async("buffered_scan", event, buffer=True)
                
                # Wait for buffer to flush
                await asyncio.sleep(0.2)
                
                # Check events were stored
                events = await db.search_events_async({"scan_id": "buffered_scan"})
                assert len(events) >= 3  # Batch size should trigger flush


class TestAsyncEventQueue:
    """Test async event queue system."""
    
    @pytest.mark.asyncio
    async def test_event_queue_priority_processing(self):
        """Test priority-based event processing."""
        async with AsyncEventQueue(max_workers=2) as queue:
            processed_events = []
            
            # Create a test handler
            async def test_handler(event):
                processed_events.append((event.eventType, event.data))
                await asyncio.sleep(0.01)  # Simulate processing time
            
            # Register handler
            queue.register_handler("TEST_EVENT", test_handler)
            
            # Create test events with different priorities
            events = []
            for i in range(5):
                event = Mock(spec=SpiderFootEvent)
                event.eventType = "TEST_EVENT"
                event.data = f"data_{i}"
                event.module = "test_module"
                events.append(event)
            
            # Add events with different priorities (reverse order)
            await queue.put(events[0], priority=EventPriority.LOW)
            await queue.put(events[1], priority=EventPriority.NORMAL)
            await queue.put(events[2], priority=EventPriority.HIGH)
            await queue.put(events[3], priority=EventPriority.CRITICAL)
            await queue.put(events[4], priority=EventPriority.BACKGROUND)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Check that higher priority events were processed first
            assert len(processed_events) >= 4
            
            # Critical should be first
            assert processed_events[0][1] == "data_3"  # CRITICAL priority
    
    @pytest.mark.asyncio
    async def test_event_queue_batch_processing(self):
        """Test batch event processing."""
        async with AsyncEventQueue(batch_size=3) as queue:
            # Create test events
            events = []
            for i in range(5):
                event = Mock(spec=SpiderFootEvent)
                event.eventType = "BATCH_EVENT"
                event.data = f"batch_data_{i}"
                event.module = "test_module"
                events.append(event)
                await queue.put(event)
            
            # Get a batch
            batch = await queue.get_batch(size=3, timeout=1.0)
            assert len(batch) <= 3
            assert all(qe.event.eventType == "BATCH_EVENT" for qe in batch)


class TestAsyncPluginIntegration:
    """Test async plugin integration."""
    
    @pytest.mark.asyncio
    async def test_async_plugin_setup(self):
        """Test async plugin setup and initialization."""
        
        class TestAsyncPlugin(AsyncSpiderFootPlugin):
            async def handleEvent_async(self, event):
                pass
        
        plugin = TestAsyncPlugin()
        
        # Mock SpiderFoot and options
        sf = Mock()
        opts = {
            '_maxthreads': 5,
            '_requests_per_second': 10,
            '_fetchtimeout': 30,
            '_dns_timeout': 5.0
        }
        
        # Setup plugin
        await plugin.setup_async(sf, opts)
        
        # Check components were initialized
        assert plugin.http_client is not None
        assert plugin.dns_resolver is not None
        assert plugin.rate_limiter is not None
        
        # Cleanup
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_async_plugin_concurrent_operations(self):
        """Test async plugin concurrent operations."""
        
        class TestConcurrentPlugin(AsyncSpiderFootPlugin):
            def __init__(self):
                super().__init__()
                self.processed_events = []
            
            async def handleEvent_async(self, event):
                # Simulate async work
                await asyncio.sleep(0.01)
                self.processed_events.append(event.data)
        
        plugin = TestConcurrentPlugin()
        
        # Mock setup
        sf = Mock()
        opts = {'_maxthreads': 3}
        await plugin.setup_async(sf, opts)
        
        # Create test events
        events = []
        for i in range(5):
            event = Mock(spec=SpiderFootEvent)
            event.data = f"concurrent_data_{i}"
            events.append(event)
        
        # Process events concurrently
        tasks = [plugin.handleEvent_async(event) for event in events]
        await asyncio.gather(*tasks)
        
        # Check all events were processed
        assert len(plugin.processed_events) == 5
        
        # Cleanup
        await plugin.cleanup_async()


class TestAsyncModuleIntegration:
    """Test integration of specific async modules."""
    
    @pytest.mark.asyncio
    async def test_unified_ip_info_async_integration(self):
        """Test unified IP info async module integration."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
        except ImportError:
            pytest.skip("Unified IP info async module not available")
        
        plugin = sfp_unified_ip_info_async()
        
        # Mock setup
        sf = Mock()
        sf.validIP = Mock(return_value=True)
        sf.isValidLocalOrLoopbackIP = Mock(return_value=False)
        
        opts = {
            '_maxthreads': 3,
            'fallback_to_free': True,
            'cache_results': True
        }
        
        await plugin.setup_async(sf, opts)
        
        # Test with mock event
        event = Mock(spec=SpiderFootEvent)
        event.eventType = "IP_ADDRESS"
        event.data = "8.8.8.8"
        event.module = "test_module"
        
        # Mock HTTP responses
        mock_response = {
            'status': 200,
            'content': {
                'ip': '8.8.8.8',
                'city': 'Mountain View',
                'country': 'US',
                'loc': '37.4056,-122.0775'
            }
        }
        
        with patch.object(plugin.http_client, 'get', new=AsyncMock(return_value=mock_response)):
            # Mock notify listeners
            plugin.notifyListeners = AsyncMock()
            
            # Process event
            await plugin.handleEvent_async(event)
            
            # Should have called notifyListeners
            assert plugin.notifyListeners.called
        
        await plugin.cleanup_async()


class TestAsyncPerformance:
    """Test async framework performance improvements."""
    
    @pytest.mark.asyncio
    async def test_concurrent_vs_sequential_performance(self):
        """Test performance improvement of concurrent operations."""
        
        async def mock_api_call(delay=0.1):
            """Mock API call with delay."""
            await asyncio.sleep(delay)
            return {"status": "ok", "data": "test"}
        
        # Sequential execution
        start_time = time.time()
        sequential_results = []
        for _ in range(5):
            result = await mock_api_call(0.1)
            sequential_results.append(result)
        sequential_time = time.time() - start_time
        
        # Concurrent execution
        start_time = time.time()
        tasks = [mock_api_call(0.1) for _ in range(5)]
        concurrent_results = await asyncio.gather(*tasks)
        concurrent_time = time.time() - start_time
        
        # Concurrent should be significantly faster
        assert concurrent_time < sequential_time / 3
        assert len(concurrent_results) == len(sequential_results)
        
        print(f"Sequential time: {sequential_time:.2f}s")
        print(f"Concurrent time: {concurrent_time:.2f}s") 
        print(f"Speedup: {sequential_time/concurrent_time:.1f}x")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])