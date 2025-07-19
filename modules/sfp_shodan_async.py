# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_shodan_async
# Purpose:     Async version of Shodan search module for high-performance queries
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
from urllib.parse import urlencode
from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugin_async import AsyncSpiderFootPlugin


class sfp_shodan_async(AsyncSpiderFootPlugin):
    """Async SHODAN module for high-performance concurrent queries.
    
    This module demonstrates the power of async operations by:
    - Querying multiple IPs concurrently
    - Batch processing netblock lookups
    - Rate limiting API calls properly
    - Caching results to minimize API usage
    """

    meta = {
        'name': "SHODAN (Async)",
        'summary': "High-performance async SHODAN queries with concurrent IP lookups",
        'flags': ["apikey", "async"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://www.shodan.io/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://developer.shodan.io/api",
                "https://developer.shodan.io/apps"
            ],
            'apiKeyInstructions': [
                "Visit https://shodan.io",
                "Register a free account",
                "Navigate to https://account.shodan.io/",
                "The API key is listed under 'API Key'"
            ],
            'description': "Async version of the Shodan module that performs concurrent "
            "searches for maximum performance. Respects rate limits (1 req/sec for free tier) "
            "while maximizing throughput through intelligent batching and caching.",
        }
    }

    opts = {
        'api_key': "",
        'netblocklookup': True,
        'maxnetblock': 24,
        'batch_size': 10,
        'cache_results': True
    }

    optdescs = {
        "api_key": "SHODAN API Key",
        'netblocklookup': "Look up all IPs on netblocks owned by target",
        'maxnetblock': "Maximum netblock size to look up (CIDR value)",
        'batch_size': "Number of IPs to process concurrently",
        'cache_results': "Cache API results to reduce duplicate queries"
    }

    def __init__(self):
        super().__init__()
        self.results = None
        self.errorState = False
        self.cache: Dict[str, Any] = {}
        self.processing_ips: Set[str] = set()

    async def setup_async(self, sf, opts):
        """Async setup method."""
        await super().setup_async(sf, opts)
        
        self.results = self.tempStorage()
        self.errorState = False
        self.cache = {}
        self.processing_ips = set()
        
        # Configure rate limiting for Shodan
        # Free tier: 1 request/second
        # Paid tiers have higher limits
        if self.rate_limiter:
            self.rate_limiter.set_limit("shodan.io", 1.0, burst_size=1)

    def watchedEvents(self):
        return ["IP_ADDRESS", "NETBLOCK_OWNER", "DOMAIN_NAME", "WEB_ANALYTICS_ID"]

    def producedEvents(self):
        return [
            "OPERATING_SYSTEM", "DEVICE_TYPE",
            "TCP_PORT_OPEN", "TCP_PORT_OPEN_BANNER",
            'RAW_RIR_DATA', 'GEOINFO', 'IP_ADDRESS',
            'VULNERABILITY_CVE_CRITICAL', 'VULNERABILITY_CVE_HIGH',
            'VULNERABILITY_CVE_MEDIUM', 'VULNERABILITY_CVE_LOW',
            'VULNERABILITY_GENERAL', 'BGP_AS_MEMBER', 'SOFTWARE_USED'
        ]

    async def queryHost(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query SHODAN for a single host asynchronously."""
        # Check cache first
        if self.opts['cache_results'] and ip in self.cache:
            self.debug(f"Using cached result for {ip}")
            return self.cache[ip]

        async with self._rate_limited("shodan.io"):
            url = f"https://api.shodan.io/shodan/host/{ip}?key={self.opts['api_key']}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers={"User-Agent": "SpiderFoot"},
                    timeout=self.opts['_fetchtimeout']
                )
                
                if result['status'] in [403, 401]:
                    self.error("SHODAN API key rejected or rate limit exceeded")
                    self.errorState = True
                    return None
                
                if result['status'] == 200 and result['content']:
                    data = result['content']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    if "error" in data:
                        self.error(f"SHODAN error: {data['error']}")
                        return None
                    
                    # Cache successful result
                    if self.opts['cache_results']:
                        self.cache[ip] = data
                    
                    return data
                
            except Exception as e:
                self.error(f"Error querying SHODAN for {ip}: {e}")
                
        return None

    async def searchHosts(self, domain: str) -> Optional[Dict[str, Any]]:
        """Search SHODAN for hosts in a domain."""
        params = {
            'query': f"hostname:{domain}",
            'key': self.opts['api_key']
        }
        
        async with self._rate_limited("shodan.io"):
            url = f"https://api.shodan.io/shodan/host/search?{urlencode(params)}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers={"User-Agent": "SpiderFoot"},
                    timeout=self.opts['_fetchtimeout']
                )
                
                if result['status'] in [403, 401]:
                    self.error("SHODAN API key rejected or rate limit exceeded")
                    self.errorState = True
                    return None
                
                if result['status'] == 200 and result['content']:
                    data = result['content']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    if "error" in data:
                        self.error(f"SHODAN error: {data['error']}")
                        return None
                    
                    return data
                    
            except Exception as e:
                self.error(f"Error searching SHODAN for {domain}: {e}")
                
        return None

    async def searchHtml(self, analytics_id: str) -> Optional[Dict[str, Any]]:
        """Search SHODAN for HTML containing analytics ID."""
        params = {
            'query': f'http.html:"{analytics_id}"',
            'key': self.opts['api_key']
        }
        
        async with self._rate_limited("shodan.io"):
            url = f"https://api.shodan.io/shodan/host/search?{urlencode(params)}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers={"User-Agent": "SpiderFoot"},
                    timeout=self.opts['_fetchtimeout']
                )
                
                if result['status'] in [403, 401]:
                    self.error("SHODAN API key rejected or rate limit exceeded")
                    self.errorState = True
                    return None
                
                if result['status'] == 200 and result['content']:
                    data = result['content']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    if "error" in data:
                        self.error(f"SHODAN error: {data['error']}")
                        return None
                    
                    if data.get('total', 0) == 0:
                        self.info(f"No SHODAN results for analytics ID: {analytics_id}")
                        return None
                    
                    return data
                    
            except Exception as e:
                self.error(f"Error searching SHODAN HTML: {e}")
                
        return None

    async def queryMultipleHosts(self, ips: List[str]) -> Dict[str, Any]:
        """Query multiple hosts concurrently with rate limiting."""
        results = {}
        
        # Process in batches to respect rate limits
        batch_size = min(self.opts['batch_size'], 5)  # Max 5 concurrent for safety
        
        for i in range(0, len(ips), batch_size):
            batch = ips[i:i + batch_size]
            
            # Create tasks for batch
            tasks = []
            for ip in batch:
                if ip not in self.processing_ips:
                    self.processing_ips.add(ip)
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
                    self.processing_ips.discard(ip)
            
            # Check if we should stop
            if self.checkForStop():
                break
        
        return results

    async def processHostData(self, addr: str, data: Dict[str, Any], event: SpiderFootEvent) -> None:
        """Process SHODAN host data and emit events."""
        # Operating System
        if data.get('os'):
            evt = SpiderFootEvent(
                "OPERATING_SYSTEM",
                f"{data['os']} ({addr})",
                self.__name__,
                event
            )
            await self.notifyListeners(evt)
        
        # Device Type
        if data.get('devtype'):
            evt = SpiderFootEvent(
                "DEVICE_TYPE",
                f"{data['devtype']} ({addr})",
                self.__name__,
                event
            )
            await self.notifyListeners(evt)
        
        # Geographic Information
        if data.get('country_name'):
            location = ', '.join([_f for _f in [data.get('city'), data.get('country_name')] if _f])
            evt = SpiderFootEvent("GEOINFO", location, self.__name__, event)
            await self.notifyListeners(evt)
        
        # Process service data
        if 'data' in data:
            ports_seen = set()
            banners_seen = set()
            asns_seen = set()
            products_seen = set()
            vulns_seen = set()
            
            for service in data['data']:
                # Port information
                port = service.get('port')
                if port:
                    cp = f"{addr}:{port}"
                    if cp not in ports_seen:
                        ports_seen.add(cp)
                        evt = SpiderFootEvent("TCP_PORT_OPEN", cp, self.__name__, event)
                        await self.notifyListeners(evt)
                
                # Banner information
                banner = service.get('banner')
                if banner and banner not in banners_seen:
                    banners_seen.add(banner)
                    evt = SpiderFootEvent("TCP_PORT_OPEN_BANNER", banner, self.__name__, event)
                    await self.notifyListeners(evt)
                
                # Product information
                product = service.get('product')
                if product and product not in products_seen:
                    products_seen.add(product)
                    evt = SpiderFootEvent("SOFTWARE_USED", product, self.__name__, event)
                    await self.notifyListeners(evt)
                
                # ASN information
                asn = service.get('asn')
                if asn and asn not in asns_seen:
                    asns_seen.add(asn)
                    evt = SpiderFootEvent("BGP_AS_MEMBER", asn.replace("AS", ""), self.__name__, event)
                    await self.notifyListeners(evt)
                
                # Vulnerability information
                vulns = service.get('vulns')
                if vulns:
                    for vuln in vulns.keys():
                        if vuln not in vulns_seen:
                            vulns_seen.add(vuln)
                            etype, cvetext = self.sf.cveInfo(vuln)
                            evt = SpiderFootEvent(etype, cvetext, self.__name__, event)
                            await self.notifyListeners(evt)

    async def handleEvent_async(self, event: SpiderFootEvent) -> None:
        """Async event handler."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if not self.opts['api_key']:
            self.error("SHODAN API key not configured!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Handle domain searches
        if eventName == "DOMAIN_NAME":
            hosts = await self.searchHosts(eventData)
            if hosts:
                evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(hosts), self.__name__, event)
                await self.notifyListeners(evt)
            return

        # Handle analytics ID searches
        if eventName == 'WEB_ANALYTICS_ID':
            try:
                network = eventData.split(": ")[0]
                analytics_id = eventData.split(": ")[1]
            except Exception as e:
                self.error(f"Unable to parse WEB_ANALYTICS_ID: {eventData} ({e})")
                return

            if network not in ['Google AdSense', 'Google Analytics', 'Google Site Verification']:
                self.debug(f"Skipping {eventData}, as not supported.")
                return

            rec = await self.searchHtml(analytics_id)
            if rec:
                evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(rec), self.__name__, event)
                await self.notifyListeners(evt)
            return

        # Handle netblock lookups
        if eventName == 'NETBLOCK_OWNER':
            if not self.opts['netblocklookup']:
                return
            
            max_netblock = self.opts['maxnetblock']
            network = IPNetwork(eventData)
            
            if network.prefixlen < max_netblock:
                self.debug(f"Network too large: {network.prefixlen} > {max_netblock}")
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
                self.info(f"Querying {len(ip_list)} IPs from netblock {eventData}")
                results = await self.queryMultipleHosts(ip_list)
                
                # Process results
                for ip, data in results.items():
                    # Create IP event for netblock members
                    ip_evt = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, event)
                    await self.notifyListeners(ip_evt)
                    
                    # Emit raw data
                    evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(data), self.__name__, ip_evt)
                    await self.notifyListeners(evt)
                    
                    # Process host data
                    await self.processHostData(ip, data, ip_evt)
                    
                    if self.checkForStop():
                        return
            return

        # Handle single IP lookups
        if eventName == "IP_ADDRESS":
            rec = await self.queryHost(eventData)
            if rec:
                evt = SpiderFootEvent("RAW_RIR_DATA", json.dumps(rec), self.__name__, event)
                await self.notifyListeners(evt)
                
                await self.processHostData(eventData, rec, event)

# End of sfp_shodan_async class