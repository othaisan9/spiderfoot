# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_unified_ip_info_async
# Purpose:      Async unified IP geolocation and information module for SpiderFoot
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-01
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import asyncio
from typing import Dict, Optional, Any, List, Set
from ipaddress import ip_address, IPv4Address, IPv6Address

from spiderfoot import SpiderFootEvent
from spiderfoot.plugin_async import AsyncSpiderFootPlugin


class sfp_unified_ip_info_async(AsyncSpiderFootPlugin):
    """Async version of unified IP information module.
    
    This module demonstrates the power of async operations by querying
    multiple IP information services concurrently, dramatically reducing
    the time needed to gather comprehensive IP data.
    """

    meta = {
        'name': "Unified IP Information (Async)",
        'summary': "High-performance async IP information gathering using multiple services concurrently",
        'flags': ["async"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Real World"],
        'dataSource': {
            'website': "https://github.com/smicallef/spiderfoot",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://ipinfo.io/developers",
                "https://ipapi.co/api",
                "https://ipstack.com/documentation",
                "https://ip-api.com/docs"
            ],
            'description': "Async unified module that queries multiple IP information services "
            "concurrently for maximum performance. Provides geolocation, ASN, ISP, "
            "and other IP metadata with intelligent caching and fallback.",
        }
    }

    opts = {
        'api_key_ipinfo': '',
        'api_key_ipstack': '',
        'fallback_to_free': True,
        'cache_results': True,
        'concurrent_queries': 3,
        'timeout': 10
    }

    optdescs = {
        'api_key_ipinfo': "IPInfo.io API key for enhanced queries",
        'api_key_ipstack': "IPStack API key for additional data",
        'fallback_to_free': "Use free services if API keys fail",
        'cache_results': "Cache IP lookups to reduce API calls",
        'concurrent_queries': "Number of concurrent API queries per IP",
        'timeout': "Timeout for each API request (seconds)"
    }

    def __init__(self):
        super().__init__()
        self.results = None
        self.errorState = False
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.processing_ips: Set[str] = set()

    async def setup_async(self, sf, opts):
        """Async setup method."""
        await super().setup_async(sf, opts)
        
        self.results = self.tempStorage()
        self.errorState = False
        self.cache = {}
        self.processing_ips = set()
        
        # Configure rate limits for different services
        if self.rate_limiter:
            # IPInfo: 50k requests/month on free tier = ~1.15/minute
            self.rate_limiter.set_limit("ipinfo.io", 1.0, burst_size=2)
            # IP-API: 45 requests/minute on free tier
            self.rate_limiter.set_limit("ip-api.com", 0.75, burst_size=5)
            # IPStack: 10k requests/month on free tier = ~0.23/minute
            self.rate_limiter.set_limit("ipstack.com", 0.2, burst_size=1)

    def watchedEvents(self):
        return [
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "NETBLOCK_MEMBER",
            "AFFILIATE_IPADDR"
        ]

    def producedEvents(self):
        return [
            "PHYSICAL_COORDINATES",
            "PHYSICAL_ADDRESS",
            "GEOINFO",
            "ISP_NAME",
            "COMPANY_NAME",
            "NETBLOCK_OWNER",
            "RAW_RIR_DATA"
        ]

    async def queryIPInfo(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query IPInfo.io API asynchronously."""
        async with self._rate_limited("ipinfo.io"):
            headers = {"Accept": "application/json"}
            
            if self.opts['api_key_ipinfo']:
                url = f"https://ipinfo.io/{ip}?token={self.opts['api_key_ipinfo']}"
            else:
                url = f"https://ipinfo.io/{ip}/json"

            try:
                result = await self.http_client.get(
                    url,
                    headers=headers,
                    timeout=self.opts['timeout']
                )
                
                if result['status'] == 200 and result['content']:
                    return result['content']
                    
            except Exception as e:
                self.debug(f"IPInfo query failed for {ip}: {e}")
                
        return None

    async def queryIPAPI(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query IP-API.com asynchronously (free service)."""
        if not self.opts['fallback_to_free']:
            return None
            
        async with self._rate_limited("ip-api.com"):
            url = f"http://ip-api.com/json/{ip}"
            
            try:
                result = await self.http_client.get(
                    url,
                    timeout=self.opts['timeout']
                )
                
                if result['status'] == 200 and result['content']:
                    content = result['content']
                    if content.get('status') == 'success':
                        return content
                        
            except Exception as e:
                self.debug(f"IP-API query failed for {ip}: {e}")
                
        return None

    async def queryIPStack(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query IPStack API asynchronously."""
        if not self.opts['api_key_ipstack']:
            return None
            
        async with self._rate_limited("ipstack.com"):
            url = f"http://api.ipstack.com/{ip}?access_key={self.opts['api_key_ipstack']}"
            
            try:
                result = await self.http_client.get(
                    url,
                    timeout=self.opts['timeout']
                )
                
                if result['status'] == 200 and result['content']:
                    content = result['content']
                    if not content.get('error'):
                        return content
                        
            except Exception as e:
                self.debug(f"IPStack query failed for {ip}: {e}")
                
        return None

    async def queryAllServices(self, ip: str) -> Dict[str, Any]:
        """Query all available services concurrently."""
        # Create tasks for all services
        tasks = []
        
        # Always try IPInfo
        tasks.append(('ipinfo', self.queryIPInfo(ip)))
        
        # Add other services based on configuration
        if self.opts['api_key_ipstack']:
            tasks.append(('ipstack', self.queryIPStack(ip)))
            
        if self.opts['fallback_to_free']:
            tasks.append(('ipapi', self.queryIPAPI(ip)))
        
        # Execute all queries concurrently
        results = {}
        task_list = [task[1] for task in tasks]
        responses = await asyncio.gather(*task_list, return_exceptions=True)
        
        # Map responses back to service names
        for i, (service_name, _) in enumerate(tasks):
            if not isinstance(responses[i], Exception) and responses[i]:
                results[service_name] = responses[i]
        
        return results

    def mergeResults(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Merge results from multiple services intelligently."""
        merged = {
            'ip': None,
            'city': None,
            'region': None,
            'country': None,
            'postal': None,
            'latitude': None,
            'longitude': None,
            'isp': None,
            'org': None,
            'asn': None,
            'timezone': None,
            'hostname': None
        }
        
        # Priority order for data sources
        priority = ['ipinfo', 'ipstack', 'ipapi']
        
        # Merge data with priority
        for service in priority:
            if service not in results:
                continue
                
            data = results[service]
            
            # Map fields from different services
            if service == 'ipinfo':
                merged['ip'] = merged['ip'] or data.get('ip')
                merged['city'] = merged['city'] or data.get('city')
                merged['region'] = merged['region'] or data.get('region')
                merged['country'] = merged['country'] or data.get('country')
                merged['postal'] = merged['postal'] or data.get('postal')
                if data.get('loc'):
                    parts = data['loc'].split(',')
                    if len(parts) == 2:
                        merged['latitude'] = merged['latitude'] or float(parts[0])
                        merged['longitude'] = merged['longitude'] or float(parts[1])
                merged['org'] = merged['org'] or data.get('org')
                merged['timezone'] = merged['timezone'] or data.get('timezone')
                merged['hostname'] = merged['hostname'] or data.get('hostname')
                
            elif service == 'ipstack':
                merged['ip'] = merged['ip'] or data.get('ip')
                merged['city'] = merged['city'] or data.get('city')
                merged['region'] = merged['region'] or data.get('region_name')
                merged['country'] = merged['country'] or data.get('country_code')
                merged['postal'] = merged['postal'] or data.get('zip')
                merged['latitude'] = merged['latitude'] or data.get('latitude')
                merged['longitude'] = merged['longitude'] or data.get('longitude')
                
            elif service == 'ipapi':
                merged['ip'] = merged['ip'] or data.get('query')
                merged['city'] = merged['city'] or data.get('city')
                merged['region'] = merged['region'] or data.get('regionName')
                merged['country'] = merged['country'] or data.get('countryCode')
                merged['postal'] = merged['postal'] or data.get('zip')
                merged['latitude'] = merged['latitude'] or data.get('lat')
                merged['longitude'] = merged['longitude'] or data.get('lon')
                merged['isp'] = merged['isp'] or data.get('isp')
                merged['org'] = merged['org'] or data.get('org')
                merged['asn'] = merged['asn'] or data.get('as')
                merged['timezone'] = merged['timezone'] or data.get('timezone')
        
        # Add raw data for reference
        merged['_raw'] = results
        
        return merged

    async def handleEvent_async(self, event: SpiderFootEvent) -> None:
        """Async event handler."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        # Skip if we've already processed this IP
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        # Validate IP address
        try:
            ip_obj = ip_address(eventData)
            if ip_obj.is_private or ip_obj.is_loopback:
                self.debug(f"Skipping private/loopback IP: {eventData}")
                return
        except ValueError:
            self.debug(f"Invalid IP address: {eventData}")
            return

        self.results[eventData] = True

        # Check cache first
        if self.opts['cache_results'] and eventData in self.cache:
            self.debug(f"Using cached result for {eventData}")
            ip_info = self.cache[eventData]
        else:
            # Prevent duplicate processing
            if eventData in self.processing_ips:
                self.debug(f"Already processing {eventData}, skipping")
                return
                
            self.processing_ips.add(eventData)
            
            try:
                # Query all services concurrently
                self.info(f"Querying IP information services for {eventData}")
                all_results = await self.queryAllServices(eventData)
                
                if not all_results:
                    self.info(f"No results from any service for {eventData}")
                    return
                
                # Merge results from all services
                ip_info = self.mergeResults(all_results)
                
                # Cache the result
                if self.opts['cache_results']:
                    self.cache[eventData] = ip_info
                    
            finally:
                self.processing_ips.discard(eventData)

        # Process and emit events
        await self.processIPInfo(event, ip_info)

    async def processIPInfo(self, event: SpiderFootEvent, ip_info: Dict[str, Any]) -> None:
        """Process IP information and emit appropriate events."""
        # Emit raw data event
        if ip_info.get('_raw'):
            raw_data = json.dumps(ip_info['_raw'], indent=2)
            evt = SpiderFootEvent("RAW_RIR_DATA", raw_data, self.__name__, event)
            await self.notifyListeners(evt)

        # Emit geolocation events
        if ip_info.get('latitude') and ip_info.get('longitude'):
            coords = f"{ip_info['latitude']},{ip_info['longitude']}"
            evt = SpiderFootEvent("PHYSICAL_COORDINATES", coords, self.__name__, event)
            await self.notifyListeners(evt)

        # Build physical address
        location_parts = []
        if ip_info.get('city'):
            location_parts.append(ip_info['city'])
        if ip_info.get('region'):
            location_parts.append(ip_info['region'])
        if ip_info.get('country'):
            location_parts.append(ip_info['country'])

        if location_parts:
            location = ", ".join(location_parts)
            evt = SpiderFootEvent("PHYSICAL_ADDRESS", location, self.__name__, event)
            await self.notifyListeners(evt)
            
            # Also emit as GEOINFO
            evt = SpiderFootEvent("GEOINFO", location, self.__name__, event)
            await self.notifyListeners(evt)

        # Emit ISP/Organization events
        if ip_info.get('isp'):
            evt = SpiderFootEvent("ISP_NAME", ip_info['isp'], self.__name__, event)
            await self.notifyListeners(evt)

        if ip_info.get('org'):
            # Extract company name from org field
            org = ip_info['org']
            if ' ' in org and org.split()[0].startswith('AS'):
                # Format: "AS12345 Company Name"
                company = ' '.join(org.split()[1:])
            else:
                company = org
                
            evt = SpiderFootEvent("COMPANY_NAME", company, self.__name__, event)
            await self.notifyListeners(evt)

        # Emit netblock owner if we have ASN info
        if ip_info.get('asn') or ip_info.get('org'):
            netblock_info = ip_info.get('org', ip_info.get('asn', 'Unknown'))
            evt = SpiderFootEvent("NETBLOCK_OWNER", netblock_info, self.__name__, event)
            await self.notifyListeners(evt)

# End of sfp_unified_ip_info_async class