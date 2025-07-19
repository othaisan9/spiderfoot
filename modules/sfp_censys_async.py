# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_censys_async
# Purpose:     Async Censys.io API module for high-performance reconnaissance
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-01
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import base64
import json
import asyncio
from typing import Dict, Optional, Any, List, Set
from datetime import datetime
import time
from urllib.parse import urlencode
from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugin_async import AsyncSpiderFootPlugin


class sfp_censys_async(AsyncSpiderFootPlugin):
    """Async Censys module for high-performance internet-wide scanning data.
    
    This module demonstrates async capabilities through:
    - Concurrent host lookups with intelligent batching
    - Parallel processing of search results
    - Efficient rate limiting (0.4 req/sec for free tier)
    - Result caching to minimize API usage
    - Concurrent service and software extraction
    """

    meta = {
        'name': "Censys (Async)",
        'summary': "High-performance async Censys queries with intelligent batching",
        'flags': ["apikey", "async"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://censys.io/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://search.censys.io/api",
                "https://search.censys.io/search/language",
                "https://github.com/censys/censys-postman/blob/main/Censys_Search.postman_collection.json",
            ],
            'apiKeyInstructions': [
                "Visit https://censys.io/",
                "Register a free account",
                "Navigate to https://censys.io/account",
                "Click on 'API'",
                "The API key combination is listed under 'API ID' and 'Secret'"
            ],
            'description': "Async version of the Censys module that maximizes "
            "throughput while respecting rate limits. Free tier: 0.4 req/sec "
            "(120 requests per 5 minutes). Performs concurrent lookups and "
            "intelligently batches netblock queries for optimal performance.",
        }
    }

    opts = {
        "censys_api_key_uid": "",
        "censys_api_key_secret": "",
        'netblocklookup': True,
        'maxnetblock': 24,
        'maxv6netblock': 120,
        "age_limit_days": 90,
        'batch_size': 5,
        'cache_results': True
    }

    optdescs = {
        "censys_api_key_uid": "Censys.io API UID",
        "censys_api_key_secret": "Censys.io API Secret",
        'netblocklookup': "Look up all IPs on owned netblocks?",
        'maxnetblock': "Maximum IPv4 netblock size to lookup (CIDR)",
        'maxv6netblock': "Maximum IPv6 netblock size to lookup (CIDR)",
        "age_limit_days": "Ignore records older than this many days (0 = unlimited)",
        'batch_size': "Number of IPs to process concurrently",
        'cache_results': "Cache API results to reduce duplicate queries"
    }

    def __init__(self):
        super().__init__()
        self.results = None
        self.errorState = False
        self.cache: Dict[str, Any] = {}
        self.processing: Set[str] = set()
        self.auth_header = None

    async def setup_async(self, sf, opts):
        """Async setup method."""
        await super().setup_async(sf, opts)
        
        self.results = self.tempStorage()
        self.errorState = False
        self.cache = {}
        self.processing = set()
        
        # Prepare authentication
        if self.opts['censys_api_key_uid'] and self.opts['censys_api_key_secret']:
            secret = f"{self.opts['censys_api_key_uid']}:{self.opts['censys_api_key_secret']}"
            self.auth_header = f"Basic {base64.b64encode(secret.encode('utf-8')).decode('utf-8')}"
        
        # Configure rate limiting
        # Free tier: 0.4 requests/second (120 per 5 minutes)
        if self.rate_limiter:
            self.rate_limiter.set_limit("censys.io", 0.4, burst_size=2)

    def watchedEvents(self):
        return [
            "IP_ADDRESS",
            "IPV6_ADDRESS",
            "NETBLOCK_OWNER",
            "NETBLOCKV6_OWNER",
        ]

    def producedEvents(self):
        return [
            "BGP_AS_MEMBER",
            "UDP_PORT_OPEN",
            "TCP_PORT_OPEN",
            "TCP_PORT_OPEN_BANNER",
            "OPERATING_SYSTEM",
            "SOFTWARE_USED",
            "WEBSERVER_HTTPHEADERS",
            "NETBLOCK_MEMBER",
            "NETBLOCKV6_MEMBER",
            "GEOINFO",
            "RAW_RIR_DATA"
        ]

    async def queryHost(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query Censys for a single host asynchronously."""
        # Check cache
        cache_key = f"host:{ip}"
        if self.opts['cache_results'] and cache_key in self.cache:
            self.debug(f"Using cached result for {ip}")
            return self.cache[cache_key]

        async with self._rate_limited("censys.io"):
            headers = {
                'Authorization': self.auth_header,
                'User-Agent': 'SpiderFoot'
            }
            
            url = f"https://search.censys.io/api/v2/hosts/{ip}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers=headers,
                    timeout=self.opts['_fetchtimeout']
                )
                
                # Parse response
                parsed = self.parseApiResponse(result)
                if parsed:
                    # Cache successful result
                    if self.opts['cache_results']:
                        self.cache[cache_key] = parsed
                    return parsed
                    
            except Exception as e:
                self.error(f"Error querying Censys for {ip}: {e}")
                
        return None

    async def searchHosts(self, query: str) -> Optional[Dict[str, Any]]:
        """Search Censys hosts asynchronously."""
        async with self._rate_limited("censys.io"):
            headers = {
                'Authorization': self.auth_header,
                'User-Agent': 'SpiderFoot'
            }
            
            params = {'q': query}
            url = f"https://search.censys.io/api/v2/hosts/search/?{urlencode(params)}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers=headers,
                    timeout=self.opts['_fetchtimeout']
                )
                
                return self.parseApiResponse(result)
                    
            except Exception as e:
                self.error(f"Error searching Censys: {e}")
                
        return None

    def parseApiResponse(self, res: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Censys API response."""
        if not res:
            self.error("No response from Censys")
            return None

        status = res.get('status', 0)
        
        if status == 400:
            self.error("Invalid request to Censys")
            return None
        
        if status == 403:
            self.error("Invalid Censys API credentials")
            self.errorState = True
            return None
        
        if status == 404:
            self.info("Censys returned no results")
            return None
        
        if status == 429:
            self.error("Censys rate limit exceeded")
            self.errorState = True
            return None
        
        if status != 200:
            self.error(f"Unexpected HTTP {status} from Censys")
            self.errorState = True
            return None

        content = res.get('content')
        if not content:
            self.info("Censys returned empty response")
            return None

        # Parse JSON
        try:
            if isinstance(content, str):
                data = json.loads(content)
            else:
                data = content
                
            if data.get('error_type'):
                self.error(f"Censys error: {data.get('error_type')}")
                return None
                
            return data
            
        except Exception as e:
            self.error(f"Error parsing Censys response: {e}")
            return None

    async def queryMultipleHosts(self, ips: List[str]) -> Dict[str, Any]:
        """Query multiple hosts concurrently."""
        results = {}
        
        # Process in batches
        batch_size = min(self.opts['batch_size'], 5)
        
        for i in range(0, len(ips), batch_size):
            batch = ips[i:i + batch_size]
            
            # Create tasks
            tasks = []
            for ip in batch:
                if ip not in self.processing:
                    self.processing.add(ip)
                    tasks.append(self.queryHost(ip))
                else:
                    tasks.append(None)
            
            # Execute batch
            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for ip, result in zip(batch, batch_results):
                    if result and not isinstance(result, Exception):
                        results[ip] = result
                    self.processing.discard(ip)
            
            # Check if we should stop
            if self.checkForStop():
                break
        
        return results

    def checkRecordAge(self, record: Dict[str, Any]) -> bool:
        """Check if record is within age limit."""
        if self.opts['age_limit_days'] <= 0:
            return True
        
        try:
            # Date format: 2021-09-22T16:46:47.623Z
            last_updated = record.get('last_updated_at', "1970-01-01T00:00:00.000Z")
            created_dt = datetime.strptime(last_updated, '%Y-%m-%dT%H:%M:%S.%fZ')
            created_ts = int(time.mktime(created_dt.timetuple()))
            age_limit_ts = int(time.time()) - (86400 * self.opts['age_limit_days'])
            
            if created_ts < age_limit_ts:
                self.debug(f"Record too old ({created_dt}), skipping")
                return False
                
        except Exception as e:
            self.error(f"Error checking record age: {e}")
            
        return True

    async def processHostData(self, addr: str, data: Dict[str, Any], event: SpiderFootEvent) -> None:
        """Process host data and emit events."""
        record = data.get('result', {})
        if not record:
            return
        
        # Check record age
        if not self.checkRecordAge(record):
            return
        
        # Emit raw data
        evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(record), self.__name__, event)
        await self.notifyListeners(evt)
        
        # Process location data
        location = record.get('location', {})
        if location:
            geoinfo_parts = [
                location.get('city'),
                location.get('province'),
                location.get('postal_code'),
                location.get('country'),
                location.get('continent')
            ]
            geoinfo = ', '.join([_f for _f in geoinfo_parts if _f])
            if geoinfo:
                evt = SpiderFootEvent("GEOINFO", geoinfo, self.__name__, event)
                await self.notifyListeners(evt)
        
        # Process services concurrently
        await self.processServices(addr, record.get('services', []), event)
        
        # Process autonomous system
        as_info = record.get('autonomous_system', {})
        if as_info:
            asn = as_info.get('asn')
            if asn:
                evt = SpiderFootEvent("BGP_AS_MEMBER", str(asn), self.__name__, event)
                await self.notifyListeners(evt)
            
            bgp_prefix = as_info.get('bgp_prefix')
            if bgp_prefix and self.sf.validIpNetwork(bgp_prefix):
                if ':' in bgp_prefix:
                    evt = SpiderFootEvent("NETBLOCKV6_MEMBER", str(bgp_prefix), self.__name__, event)
                else:
                    evt = SpiderFootEvent("NETBLOCK_MEMBER", str(bgp_prefix), self.__name__, event)
                await self.notifyListeners(evt)
        
        # Process operating system
        os_info = record.get('operating_system', {})
        if os_info:
            os_parts = [
                os_info.get('vendor'),
                os_info.get('product'),
                os_info.get('version'),
                os_info.get('edition')
            ]
            os_string = ' '.join([_f for _f in os_parts if _f])
            if os_string:
                evt = SpiderFootEvent("OPERATING_SYSTEM", os_string, self.__name__, event)
                await self.notifyListeners(evt)

    async def processServices(self, addr: str, services: List[Dict[str, Any]], event: SpiderFootEvent) -> None:
        """Process services data and emit events."""
        if not services:
            return
        
        # Collect unique values
        software_set = set()
        tcp_banners = set()
        
        # Process each service
        for service in services:
            port = service.get('port')
            if not port:
                continue
            
            transport = service.get('transport_protocol')
            
            # Emit port events
            if transport == "UDP":
                evt = SpiderFootEvent("UDP_PORT_OPEN", f"{addr}:{port}", self.__name__, event)
                await self.notifyListeners(evt)
            elif transport == "TCP":
                evt = SpiderFootEvent("TCP_PORT_OPEN", f"{addr}:{port}", self.__name__, event)
                await self.notifyListeners(evt)
                
                # Collect banner
                banner = service.get('banner')
                if banner:
                    tcp_banners.add(banner)
            
            # Collect software
            for sw in service.get('software', []):
                sw_parts = [
                    sw.get('vendor'),
                    sw.get('product'),
                    sw.get('version')
                ]
                sw_string = ' '.join([_f for _f in sw_parts if _f])
                if sw_string:
                    software_set.add(sw_string)
            
            # Process HTTP headers
            http = service.get('http', {})
            if http:
                response = http.get('response', {})
                headers = response.get('headers')
                if headers:
                    evt = SpiderFootEvent(
                        "WEBSERVER_HTTPHEADERS",
                        json.dumps(headers, ensure_ascii=False),
                        self.__name__,
                        event
                    )
                    evt.actualSource = addr
                    await self.notifyListeners(evt)
        
        # Emit unique software
        for software in software_set:
            evt = SpiderFootEvent("SOFTWARE_USED", software, self.__name__, event)
            await self.notifyListeners(evt)
        
        # Emit unique banners
        for banner in tcp_banners:
            evt = SpiderFootEvent("TCP_PORT_OPEN_BANNER", str(banner), self.__name__, event)
            await self.notifyListeners(evt)

    async def handleEvent_async(self, event: SpiderFootEvent) -> None:
        """Async event handler."""
        if self.errorState:
            return

        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        # Check credentials
        if not self.opts['censys_api_key_uid'] or not self.opts['censys_api_key_secret']:
            self.error("Censys API credentials not configured!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Handle netblock lookups
        if eventName in ['NETBLOCK_OWNER', 'NETBLOCKV6_OWNER']:
            if not self.opts['netblocklookup']:
                return
            
            network = IPNetwork(eventData)
            
            # Check netblock size
            if eventName == 'NETBLOCKV6_OWNER':
                max_size = self.opts['maxv6netblock']
            else:
                max_size = self.opts['maxnetblock']
            
            if network.prefixlen < max_size:
                self.debug(f"Network too large: {network.prefixlen} < {max_size}")
                return
            
            # Collect IPs for batch processing
            ip_list = []
            for ip in network:
                ip_str = str(ip)
                if ip_str not in self.results:
                    ip_list.append(ip_str)
                    self.results[ip_str] = True
            
            if ip_list:
                # Query multiple IPs concurrently
                self.info(f"Querying Censys for {len(ip_list)} IPs from netblock {eventData}")
                results = await self.queryMultipleHosts(ip_list)
                
                # Process results
                for ip, data in results.items():
                    if not data:
                        continue
                    
                    # Create IP event for netblock members
                    if eventName == 'NETBLOCK_OWNER':
                        ip_evt = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                    else:
                        ip_evt = SpiderFootEvent("IPV6_ADDRESS", ip, self.__name__, event)
                    await self.notifyListeners(ip_evt)
                    
                    # Process host data
                    await self.processHostData(ip, data, ip_evt)
                    
                    if self.checkForStop():
                        return
            return

        # Handle single IP lookups
        if eventName in ["IP_ADDRESS", "IPV6_ADDRESS"]:
            data = await self.queryHost(eventData)
            if data:
                await self.processHostData(eventData, data, event)

# End of sfp_censys_async class