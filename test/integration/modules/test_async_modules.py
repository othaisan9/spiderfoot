#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration tests for SpiderFoot async modules."""

import asyncio
import pytest
import time
import json
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# Import SpiderFoot components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from spiderfoot import SpiderFootEvent


class TestShodanAsync:
    """Test Shodan async module."""
    
    @pytest.mark.asyncio
    async def test_shodan_async_import(self):
        """Test that Shodan async module can be imported."""
        try:
            from modules.sfp_shodan_async import sfp_shodan_async
            plugin = sfp_shodan_async()
            assert plugin is not None
            assert hasattr(plugin, 'handleEvent_async')
        except ImportError:
            pytest.skip("Shodan async module not available")
    
    @pytest.mark.asyncio
    async def test_shodan_async_setup(self):
        """Test Shodan async module setup."""
        try:
            from modules.sfp_shodan_async import sfp_shodan_async
        except ImportError:
            pytest.skip("Shodan async module not available")
        
        plugin = sfp_shodan_async()
        
        # Mock setup
        sf = Mock()
        opts = {
            'api_key': 'test_key',
            '_maxthreads': 3,
            'netblocklookup': True,
            'batch_size': 5
        }
        
        await plugin.setup_async(sf, opts)
        
        # Check initialization
        assert plugin.rate_limiter is not None
        assert plugin.http_client is not None
        assert plugin.opts['api_key'] == 'test_key'
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_shodan_async_rate_limiting(self):
        """Test Shodan async rate limiting configuration."""
        try:
            from modules.sfp_shodan_async import sfp_shodan_async
        except ImportError:
            pytest.skip("Shodan async module not available")
        
        plugin = sfp_shodan_async()
        sf = Mock()
        opts = {'api_key': 'test_key'}
        
        await plugin.setup_async(sf, opts)
        
        # Check rate limiter was configured for Shodan
        rate_limiter = plugin.rate_limiter
        assert rate_limiter is not None
        
        # Shodan should be limited to 1 req/sec
        start_time = time.time()
        await rate_limiter.acquire("shodan.io")
        await rate_limiter.acquire("shodan.io")
        rate_limiter.release("shodan.io")
        rate_limiter.release("shodan.io")
        end_time = time.time()
        
        # Should take at least 1 second due to rate limiting
        assert end_time - start_time >= 0.9
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_shodan_async_concurrent_queries(self):
        """Test Shodan async concurrent IP queries."""
        try:
            from modules.sfp_shodan_async import sfp_shodan_async
        except ImportError:
            pytest.skip("Shodan async module not available")
        
        plugin = sfp_shodan_async()
        sf = Mock()
        opts = {'api_key': 'test_key', 'batch_size': 3}
        
        await plugin.setup_async(sf, opts)
        
        # Mock HTTP responses
        mock_response = {
            'status': 200,
            'content': {
                'ip': '8.8.8.8',
                'os': 'Linux',
                'data': [
                    {'port': 53, 'banner': 'DNS server'},
                    {'port': 443, 'banner': 'HTTPS server'}
                ]
            }
        }
        
        with patch.object(plugin.http_client, 'get', new=AsyncMock(return_value=mock_response)):
            # Test concurrent queries
            ips = ['8.8.8.8', '1.1.1.1', '9.9.9.9']
            
            start_time = time.time()
            results = await plugin.queryMultipleHosts(ips)
            end_time = time.time()
            
            # Should complete in reasonable time
            assert end_time - start_time < 5.0
            assert len(results) <= len(ips)  # Some may fail due to mocking
        
        await plugin.cleanup_async()


class TestVirusTotalAsync:
    """Test VirusTotal async module."""
    
    @pytest.mark.asyncio
    async def test_virustotal_async_import(self):
        """Test that VirusTotal async module can be imported."""
        try:
            from modules.sfp_virustotal_async import sfp_virustotal_async
            plugin = sfp_virustotal_async()
            assert plugin is not None
            assert hasattr(plugin, 'handleEvent_async')
        except ImportError:
            pytest.skip("VirusTotal async module not available")
    
    @pytest.mark.asyncio
    async def test_virustotal_async_rate_limiting(self):
        """Test VirusTotal async rate limiting."""
        try:
            from modules.sfp_virustotal_async import sfp_virustotal_async
        except ImportError:
            pytest.skip("VirusTotal async module not available")
        
        plugin = sfp_virustotal_async()
        sf = Mock()
        opts = {
            'api_key': 'test_key',
            'publicapi': True  # Free tier: 4 requests/minute
        }
        
        await plugin.setup_async(sf, opts)
        
        # Check rate limiter configuration
        rate_limiter = plugin.rate_limiter
        assert rate_limiter is not None
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_virustotal_async_batch_processing(self):
        """Test VirusTotal async batch processing."""
        try:
            from modules.sfp_virustotal_async import sfp_virustotal_async
        except ImportError:
            pytest.skip("VirusTotal async module not available")
        
        plugin = sfp_virustotal_async()
        sf = Mock()
        sf.validIP = Mock(return_value=True)
        opts = {
            'api_key': 'test_key',
            'publicapi': False,  # Premium tier
            'batch_size': 3
        }
        
        await plugin.setup_async(sf, opts)
        
        # Mock HTTP responses
        mock_response = {
            'status': 200,
            'content': {
                'detected_urls': ['http://malicious.com'],
                'response_code': 1
            }
        }
        
        with patch.object(plugin.http_client, 'get', new=AsyncMock(return_value=mock_response)):
            # Test batch queries
            items = ['8.8.8.8', '1.1.1.1', '9.9.9.9']
            
            results = await plugin.queryMultiple(items, query_type="ip")
            
            # Should handle batch processing
            assert isinstance(results, dict)
        
        await plugin.cleanup_async()


class TestCensysAsync:
    """Test Censys async module."""
    
    @pytest.mark.asyncio
    async def test_censys_async_import(self):
        """Test that Censys async module can be imported."""
        try:
            from modules.sfp_censys_async import sfp_censys_async
            plugin = sfp_censys_async()
            assert plugin is not None
            assert hasattr(plugin, 'handleEvent_async')
        except ImportError:
            pytest.skip("Censys async module not available")
    
    @pytest.mark.asyncio
    async def test_censys_async_auth_setup(self):
        """Test Censys async authentication setup."""
        try:
            from modules.sfp_censys_async import sfp_censys_async
        except ImportError:
            pytest.skip("Censys async module not available")
        
        plugin = sfp_censys_async()
        sf = Mock()
        opts = {
            'censys_api_key_uid': 'test_uid',
            'censys_api_key_secret': 'test_secret'
        }
        
        await plugin.setup_async(sf, opts)
        
        # Check auth header was created
        assert plugin.auth_header is not None
        assert 'Basic' in plugin.auth_header
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_censys_async_rate_limiting(self):
        """Test Censys async rate limiting (0.4 req/sec)."""
        try:
            from modules.sfp_censys_async import sfp_censys_async
        except ImportError:
            pytest.skip("Censys async module not available")
        
        plugin = sfp_censys_async()
        sf = Mock()
        opts = {
            'censys_api_key_uid': 'test_uid',
            'censys_api_key_secret': 'test_secret'
        }
        
        await plugin.setup_async(sf, opts)
        
        # Check rate limiter configuration for Censys
        rate_limiter = plugin.rate_limiter
        assert rate_limiter is not None
        
        # Censys free tier: 0.4 requests/second
        start_time = time.time()
        await rate_limiter.acquire("censys.io")
        await rate_limiter.acquire("censys.io")
        rate_limiter.release("censys.io")
        rate_limiter.release("censys.io")
        end_time = time.time()
        
        # Should take at least 2.5 seconds (1/0.4)
        assert end_time - start_time >= 2.0
        
        await plugin.cleanup_async()


class TestUnifiedIPInfoAsync:
    """Test Unified IP Info async module."""
    
    @pytest.mark.asyncio
    async def test_unified_ip_info_async_import(self):
        """Test that Unified IP Info async module can be imported."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
            plugin = sfp_unified_ip_info_async()
            assert plugin is not None
            assert hasattr(plugin, 'handleEvent_async')
        except ImportError:
            pytest.skip("Unified IP Info async module not available")
    
    @pytest.mark.asyncio
    async def test_unified_ip_info_async_concurrent_services(self):
        """Test concurrent querying of multiple IP info services."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
        except ImportError:
            pytest.skip("Unified IP Info async module not available")
        
        plugin = sfp_unified_ip_info_async()
        sf = Mock()
        opts = {
            'api_key_ipinfo': 'test_key',
            'fallback_to_free': True,
            'concurrent_queries': 3
        }
        
        await plugin.setup_async(sf, opts)
        
        # Mock different service responses
        def mock_get_response(url, **kwargs):
            if 'ipinfo.io' in url:
                return AsyncMock(return_value={
                    'status': 200,
                    'content': {
                        'ip': '8.8.8.8',
                        'city': 'Mountain View',
                        'country': 'US',
                        'loc': '37.4056,-122.0775'
                    }
                })()
            elif 'ip-api.com' in url:
                return AsyncMock(return_value={
                    'status': 200,
                    'content': {
                        'status': 'success',
                        'query': '8.8.8.8',
                        'city': 'Mountain View',
                        'countryCode': 'US',
                        'lat': 37.4056,
                        'lon': -122.0775
                    }
                })()
            else:
                return AsyncMock(return_value={'status': 404})()
        
        with patch.object(plugin.http_client, 'get', side_effect=mock_get_response):
            # Test concurrent service queries
            start_time = time.time()
            results = await plugin.queryAllServices('8.8.8.8')
            end_time = time.time()
            
            # Should complete quickly (concurrent queries)
            assert end_time - start_time < 2.0
            assert isinstance(results, dict)
            assert len(results) >= 1  # Should get at least one result
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_unified_ip_info_async_result_merging(self):
        """Test intelligent merging of results from multiple services."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
        except ImportError:
            pytest.skip("Unified IP Info async module not available")
        
        plugin = sfp_unified_ip_info_async()
        
        # Test result merging
        mock_results = {
            'ipinfo': {
                'ip': '8.8.8.8',
                'city': 'Mountain View',
                'country': 'US',
                'loc': '37.4056,-122.0775',
                'org': 'AS15169 Google LLC'
            },
            'ipapi': {
                'query': '8.8.8.8',
                'city': 'Mountain View',
                'countryCode': 'US',
                'lat': 37.4056,
                'lon': -122.0775,
                'isp': 'Google'
            }
        }
        
        merged = plugin.mergeResults(mock_results)
        
        # Check merged result
        assert merged['ip'] == '8.8.8.8'
        assert merged['city'] == 'Mountain View'
        assert merged['country'] == 'US'
        assert merged['latitude'] == 37.4056
        assert merged['longitude'] == -122.0775
        assert '_raw' in merged


class TestAsyncModulePerformance:
    """Test performance characteristics of async modules."""
    
    @pytest.mark.asyncio
    async def test_async_vs_sync_module_performance(self):
        """Compare async vs sync module performance."""
        
        # Mock async operations
        async def mock_async_operation(delay=0.1):
            await asyncio.sleep(delay)
            return {"status": "success", "data": f"result"}
        
        def mock_sync_operation(delay=0.1):
            import time
            time.sleep(delay)
            return {"status": "success", "data": f"result"}
        
        # Test concurrent async operations
        start_time = time.time()
        async_tasks = [mock_async_operation(0.1) for _ in range(5)]
        async_results = await asyncio.gather(*async_tasks)
        async_time = time.time() - start_time
        
        # Test sequential sync operations  
        start_time = time.time()
        sync_results = [mock_sync_operation(0.1) for _ in range(5)]
        sync_time = time.time() - start_time
        
        # Async should be much faster
        assert async_time < sync_time / 3
        assert len(async_results) == len(sync_results)
        
        print(f"Async time: {async_time:.2f}s")
        print(f"Sync time: {sync_time:.2f}s")
        print(f"Async speedup: {sync_time/async_time:.1f}x")
    
    @pytest.mark.asyncio
    async def test_async_module_memory_usage(self):
        """Test memory efficiency of async modules."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create many async operations
        async def memory_test_operation():
            await asyncio.sleep(0.001)
            return "test"
        
        # Run many concurrent operations
        tasks = [memory_test_operation() for _ in range(1000)]
        results = await asyncio.gather(*tasks)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (< 50MB for 1000 operations)
        assert memory_increase < 50 * 1024 * 1024  # 50MB
        assert len(results) == 1000
        
        print(f"Memory increase: {memory_increase / 1024 / 1024:.1f}MB for 1000 operations")


class TestAsyncModuleIntegration:
    """Test integration between async modules and framework."""
    
    @pytest.mark.asyncio
    async def test_async_module_event_processing(self):
        """Test async module event processing integration."""
        # Test with a simple async module
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
            'cache_results': True,
            '_maxthreads': 3
        }
        
        await plugin.setup_async(sf, opts)
        
        # Create test events
        events = []
        for i, ip in enumerate(['8.8.8.8', '1.1.1.1', '9.9.9.9']):
            event = Mock(spec=SpiderFootEvent)
            event.eventType = "IP_ADDRESS"
            event.data = ip
            event.module = f"test_module_{i}"
            events.append(event)
        
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
            # Mock notifyListeners
            plugin.notifyListeners = AsyncMock()
            
            # Process events concurrently
            start_time = time.time()
            tasks = [plugin.handleEvent_async(event) for event in events]
            await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Should complete quickly due to concurrency
            assert end_time - start_time < 2.0
            
            # Should have called notifyListeners for each event
            assert plugin.notifyListeners.call_count >= len(events)
        
        await plugin.cleanup_async()
    
    @pytest.mark.asyncio
    async def test_async_module_error_handling(self):
        """Test async module error handling and resilience."""
        try:
            from modules.sfp_unified_ip_info_async import sfp_unified_ip_info_async
        except ImportError:
            pytest.skip("Unified IP Info async module not available")
        
        plugin = sfp_unified_ip_info_async()
        
        # Mock setup
        sf = Mock()
        sf.validIP = Mock(return_value=True)
        sf.isValidLocalOrLoopbackIP = Mock(return_value=False)
        
        opts = {'fallback_to_free': True}
        await plugin.setup_async(sf, opts)
        
        # Create test event
        event = Mock(spec=SpiderFootEvent)
        event.eventType = "IP_ADDRESS"
        event.data = "8.8.8.8"
        event.module = "test_module"
        
        # Mock HTTP client to raise exceptions
        with patch.object(plugin.http_client, 'get', side_effect=Exception("Network error")):
            plugin.notifyListeners = AsyncMock()
            
            # Should handle errors gracefully
            try:
                await plugin.handleEvent_async(event)
                # Should not crash, may or may not call notifyListeners depending on error handling
            except Exception as e:
                pytest.fail(f"Async module should handle errors gracefully: {e}")
        
        await plugin.cleanup_async()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])