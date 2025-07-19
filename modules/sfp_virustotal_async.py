# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_virustotal_async
# Purpose:      Async VirusTotal module for high-performance concurrent queries
#
# Author:       SpiderFoot Team
#
# Created:      2025-01-01
# Copyright:    (c) SpiderFoot 2025
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import asyncio
from typing import Dict, Optional, Any, List, Set
from urllib.parse import urlencode
from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent
from spiderfoot.plugin_async import AsyncSpiderFootPlugin


class sfp_virustotal_async(AsyncSpiderFootPlugin):
    """Async VirusTotal module for high-performance threat intelligence.
    
    This module demonstrates async capabilities through:
    - Concurrent IP and domain lookups
    - Intelligent rate limiting (4/min for free, higher for paid)
    - Batch processing of netblocks
    - Result caching to minimize API usage
    - Parallel processing of related domains
    """

    meta = {
        'name': "VirusTotal (Async)",
        'summary': "High-performance async VirusTotal queries with intelligent batching",
        'flags': ["apikey", "async"],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://www.virustotal.com/",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://developers.virustotal.com/reference"
            ],
            'apiKeyInstructions': [
                "Visit https://www.virustotal.com/",
                "Register a free account",
                "Click on your profile",
                "Click on API Key",
                "The API key is listed under 'API Key'"
            ],
            'description': "Async version of the VirusTotal module that maximizes "
            "throughput while respecting rate limits. Free tier: 4 req/min, "
            "Premium tiers have higher limits. Intelligently batches requests "
            "and caches results for optimal performance.",
        }
    }

    opts = {
        'api_key': '',
        'verify': True,
        'publicapi': True,
        'checkcohosts': True,
        'checkaffiliates': True,
        'netblocklookup': True,
        'maxnetblock': 24,
        'subnetlookup': True,
        'maxsubnet': 24,
        'batch_size': 4,
        'cache_results': True
    }

    optdescs = {
        'api_key': 'VirusTotal API Key',
        'publicapi': 'Using public API? (4 queries/minute limit)',
        'checkcohosts': 'Check co-hosted sites?',
        'checkaffiliates': 'Check affiliates?',
        'netblocklookup': 'Look up all IPs on owned netblocks?',
        'maxnetblock': 'Maximum netblock size to lookup (CIDR)',
        'subnetlookup': 'Look up all IPs on subnets?',
        'maxsubnet': 'Maximum subnet size to lookup (CIDR)',
        'verify': 'Verify that hostnames still resolve?',
        'batch_size': 'Number of queries to process concurrently',
        'cache_results': 'Cache API results to reduce duplicate queries'
    }

    def __init__(self):
        super().__init__()
        self.results = None
        self.errorState = False
        self.cache: Dict[str, Any] = {}
        self.processing: Set[str] = set()

    async def setup_async(self, sf, opts):
        """Async setup method."""
        await super().setup_async(sf, opts)
        
        self.results = self.tempStorage()
        self.errorState = False
        self.cache = {}
        self.processing = set()
        
        # Configure rate limiting
        if self.rate_limiter:
            if self.opts['publicapi']:
                # Free tier: 4 requests per minute
                self.rate_limiter.set_limit("virustotal.com", 4.0/60, burst_size=4)
            else:
                # Premium tier: 500-30k requests per minute depending on plan
                # Default to conservative 500/min
                self.rate_limiter.set_limit("virustotal.com", 500.0/60, burst_size=20)

    def watchedEvents(self):
        return [
            "IP_ADDRESS",
            "AFFILIATE_IPADDR",
            "INTERNET_NAME",
            "CO_HOSTED_SITE",
            "NETBLOCK_OWNER",
            "NETBLOCK_MEMBER"
        ]

    def producedEvents(self):
        return [
            "MALICIOUS_IPADDR",
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_COHOST",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_IPADDR",
            "MALICIOUS_NETBLOCK",
            "MALICIOUS_SUBNET",
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "INTERNET_NAME_UNRESOLVED",
            "DOMAIN_NAME",
            "AFFILIATE_DOMAIN_NAME"
        ]

    async def queryIp(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query VirusTotal for IP address information."""
        # Check cache
        cache_key = f"ip:{ip}"
        if self.opts['cache_results'] and cache_key in self.cache:
            self.debug(f"Using cached result for IP {ip}")
            return self.cache[cache_key]

        async with self._rate_limited("virustotal.com"):
            params = {
                'ip': ip,
                'apikey': self.opts['api_key']
            }
            
            url = f"https://www.virustotal.com/vtapi/v2/ip-address/report?{urlencode(params)}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers={"User-Agent": "SpiderFoot"},
                    timeout=self.opts['_fetchtimeout']
                )
                
                if result['status'] == 204:
                    self.error("VirusTotal request was throttled")
                    self.errorState = True
                    return None
                
                if result['status'] == 200 and result['content']:
                    data = result['content']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    # Cache successful result
                    if self.opts['cache_results']:
                        self.cache[cache_key] = data
                    
                    return data
                    
            except Exception as e:
                self.error(f"Error querying VirusTotal for IP {ip}: {e}")
                
        return None

    async def queryDomain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Query VirusTotal for domain information."""
        # Check cache
        cache_key = f"domain:{domain}"
        if self.opts['cache_results'] and cache_key in self.cache:
            self.debug(f"Using cached result for domain {domain}")
            return self.cache[cache_key]

        async with self._rate_limited("virustotal.com"):
            params = {
                'domain': domain,
                'apikey': self.opts['api_key']
            }
            
            url = f"https://www.virustotal.com/vtapi/v2/domain/report?{urlencode(params)}"
            
            try:
                result = await self.http_client.get(
                    url,
                    headers={"User-Agent": "SpiderFoot"},
                    timeout=self.opts['_fetchtimeout']
                )
                
                if result['status'] == 204:
                    self.error("VirusTotal request was throttled")
                    self.errorState = True
                    return None
                
                if result['status'] == 200 and result['content']:
                    data = result['content']
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    # Cache successful result
                    if self.opts['cache_results']:
                        self.cache[cache_key] = data
                    
                    return data
                    
            except Exception as e:
                self.error(f"Error querying VirusTotal for domain {domain}: {e}")
                
        return None

    async def queryMultiple(self, items: List[str], query_type: str = "auto") -> Dict[str, Any]:
        """Query multiple IPs/domains concurrently."""
        results = {}
        
        # Determine batch size based on API limits
        batch_size = min(self.opts['batch_size'], 4 if self.opts['publicapi'] else 20)
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Create tasks for batch
            tasks = []
            for item in batch:
                if item not in self.processing:
                    self.processing.add(item)
                    
                    # Auto-detect query type
                    if query_type == "auto":
                        if self.sf.validIP(item):
                            task = self.queryIp(item)
                        else:
                            task = self.queryDomain(item)
                    elif query_type == "ip":
                        task = self.queryIp(item)
                    else:
                        task = self.queryDomain(item)
                    
                    tasks.append(task)
                else:
                    tasks.append(None)
            
            # Execute batch
            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for item, result in zip(batch, batch_results):
                    if result and not isinstance(result, Exception):
                        results[item] = result
                    self.processing.discard(item)
            
            # Check if we should stop
            if self.checkForStop():
                break
        
        return results

    async def verifyDomains(self, domains: List[str]) -> List[tuple]:
        """Verify multiple domains concurrently."""
        if not self.opts['verify']:
            return [(domain, True) for domain in domains]
        
        async def verify_domain(domain: str) -> tuple:
            """Verify a single domain."""
            resolved = False
            
            # Try IPv4
            if self.sf.resolveHost(domain):
                resolved = True
            # Try IPv6
            elif self.sf.resolveHost6(domain):
                resolved = True
            
            return (domain, resolved)
        
        # Verify domains concurrently
        tasks = [verify_domain(domain) for domain in domains]
        return await asyncio.gather(*tasks)

    async def processThreatData(self, addr: str, info: Dict[str, Any], 
                               event: SpiderFootEvent, event_name: str) -> None:
        """Process threat intelligence data and emit events."""
        # Check for malicious URLs
        if len(info.get('detected_urls', [])) > 0:
            self.info(f"Found VirusTotal threat data for {addr}")
            
            # Determine event type based on source
            evt_type = None
            info_type = None
            
            if event_name in ["IP_ADDRESS"] or event_name.startswith("NETBLOCK_"):
                evt_type = "MALICIOUS_IPADDR"
                info_type = "ip-address"
            elif event_name == "AFFILIATE_IPADDR":
                evt_type = "MALICIOUS_AFFILIATE_IPADDR"
                info_type = "ip-address"
            elif event_name == "INTERNET_NAME":
                evt_type = "MALICIOUS_INTERNET_NAME"
                info_type = "domain"
            elif event_name == "AFFILIATE_INTERNET_NAME":
                evt_type = "MALICIOUS_AFFILIATE_INTERNET_NAME"
                info_type = "domain"
            elif event_name == "CO_HOSTED_SITE":
                evt_type = "MALICIOUS_COHOST"
                info_type = "domain"
            
            if evt_type:
                info_url = f"<SFURL>https://www.virustotal.com/en/{info_type}/{addr}/information/</SFURL>"
                evt = SpiderFootEvent(
                    evt_type,
                    f"VirusTotal [{addr}]\n{info_url}",
                    self.__name__,
                    event
                )
                await self.notifyListeners(evt)

    async def processRelatedDomains(self, info: Dict[str, Any], 
                                   event: SpiderFootEvent, event_name: str) -> None:
        """Process related domains from VirusTotal results."""
        domains = []
        
        # Collect domain siblings
        if 'domain_siblings' in info:
            if event_name in ["IP_ADDRESS", "INTERNET_NAME"]:
                domains.extend(info['domain_siblings'])
        
        # Collect subdomains
        if 'subdomains' in info:
            if event_name == "INTERNET_NAME":
                domains.extend(info['subdomains'])
        
        # Process unique domains
        unique_domains = list(set(domains))
        if not unique_domains:
            return
        
        # Verify domains concurrently
        verification_results = await self.verifyDomains(unique_domains)
        
        # Process verification results
        for domain, resolved in verification_results:
            if domain in self.results:
                continue
            
            # Determine if affiliate or target
            if self.getTarget().matches(domain):
                evt_type = 'INTERNET_NAME'
            else:
                evt_type = 'AFFILIATE_INTERNET_NAME'
            
            # Add unresolved suffix if needed
            if not resolved:
                self.debug(f"Host {domain} could not be resolved")
                evt_type += '_UNRESOLVED'
            
            # Emit internet name event
            evt = SpiderFootEvent(evt_type, domain, self.__name__, event)
            await self.notifyListeners(evt)
            
            # Emit domain name event if applicable
            if self.sf.isDomain(domain, self.opts['_internettlds']):
                if evt_type.startswith('AFFILIATE'):
                    evt = SpiderFootEvent('AFFILIATE_DOMAIN_NAME', domain, self.__name__, event)
                else:
                    evt = SpiderFootEvent('DOMAIN_NAME', domain, self.__name__, event)
                await self.notifyListeners(evt)

    async def handleEvent_async(self, event: SpiderFootEvent) -> None:
        """Async event handler."""
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if not self.opts["api_key"]:
            self.error("VirusTotal API key not configured!")
            self.errorState = True
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Check configuration options
        if eventName.startswith("AFFILIATE") and not self.opts['checkaffiliates']:
            return

        if eventName == 'CO_HOSTED_SITE' and not self.opts['checkcohosts']:
            return

        # Handle netblock size limits
        if eventName == 'NETBLOCK_OWNER':
            if not self.opts['netblocklookup']:
                return
            
            network = IPNetwork(eventData)
            if network.prefixlen < self.opts['maxnetblock']:
                self.debug(f"Network too large: {network.prefixlen} < {self.opts['maxnetblock']}")
                return

        if eventName == 'NETBLOCK_MEMBER':
            if not self.opts['subnetlookup']:
                return
            
            network = IPNetwork(eventData)
            if network.prefixlen < self.opts['maxsubnet']:
                self.debug(f"Subnet too large: {network.prefixlen} < {self.opts['maxsubnet']}")
                return

        # Prepare query list
        qrylist = []
        if eventName.startswith("NETBLOCK_"):
            # Collect IPs from netblock
            for ipaddr in IPNetwork(eventData):
                ip_str = str(ipaddr)
                if ip_str not in self.results:
                    qrylist.append(ip_str)
                    self.results[ip_str] = True
        else:
            qrylist.append(eventData)

        # Query items concurrently
        if qrylist:
            self.info(f"Querying VirusTotal for {len(qrylist)} items")
            results = await self.queryMultiple(qrylist)
            
            # Process results
            for addr, info in results.items():
                if not info:
                    continue
                
                # Process threat data
                await self.processThreatData(addr, info, event, eventName)
                
                # Process related domains
                await self.processRelatedDomains(info, event, eventName)
                
                if self.checkForStop():
                    return

# End of sfp_virustotal_async class