# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_unified_ip_info
# Purpose:      Unified IP geolocation and information module for SpiderFoot
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-01
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import time
from typing import Dict, Optional, Any, List

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_unified_ip_info(SpiderFootPlugin):

    meta = {
        'name': "Unified IP Information",
        'summary': "Identifies the physical location and other information about IP addresses using multiple services",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Real World"],
        'dataSource': {
            'website': "https://github.com/smicallef/spiderfoot",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://ipinfo.io/developers",
                "https://ipapi.co/api",
                "https://ipstack.com/documentation"
            ],
            'description': "Unified module that combines multiple IP information services "
            "including IPInfo.io (primary), with fallback to free services. "
            "Provides geolocation, ASN, ISP, and other IP metadata.",
        }
    }

    opts = {
        'api_key_ipinfo': '',
        'fallback_to_free': True,
        'cache_results': True
    }

    optdescs = {
        'api_key_ipinfo': "IPInfo.io API key for enhanced queries",
        'fallback_to_free': "Use free services if API key fails",
        'cache_results': "Cache IP lookups to reduce API calls"
    }

    results = None
    errorState = False
    cache = {}

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False
        self.cache = {}

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

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

    def queryIPInfo(self, ip: str) -> Optional[Dict[str, Any]]:
        """Query IPInfo.io API"""
        if self.opts['api_key_ipinfo']:
            url = f"https://ipinfo.io/{ip}?token={self.opts['api_key_ipinfo']}"
        else:
            url = f"https://ipinfo.io/{ip}/json"

        res = self.sf.fetchUrl(
            url,
            timeout=10,
            useragent=self.opts['_useragent']
        )

        if res['content'] is None:
            self.debug(f"No response from IPInfo for {ip}")
            return None

        try:
            data = json.loads(res['content'])
            if 'error' in data:
                self.debug(f"IPInfo error: {data['error']}")
                return None
            return data
        except Exception as e:
            self.debug(f"Error parsing IPInfo response: {e}")
            return None

    def queryFreeGeoIP(self, ip: str) -> Optional[Dict[str, Any]]:
        """Fallback to free IP geolocation service"""
        url = f"http://ip-api.com/json/{ip}"
        
        res = self.sf.fetchUrl(
            url,
            timeout=10,
            useragent=self.opts['_useragent']
        )

        if res['content'] is None:
            return None

        try:
            data = json.loads(res['content'])
            if data.get('status') == 'fail':
                return None
            
            # Convert to IPInfo-like format
            return {
                'ip': ip,
                'city': data.get('city'),
                'region': data.get('regionName'),
                'country': data.get('countryCode'),
                'loc': f"{data.get('lat')},{data.get('lon')}" if data.get('lat') else None,
                'org': f"{data.get('as')} {data.get('isp')}" if data.get('as') else data.get('isp'),
                'timezone': data.get('timezone')
            }
        except Exception as e:
            self.debug(f"Error parsing free geo IP response: {e}")
            return None

    def lookupIP(self, ip: str) -> Optional[Dict[str, Any]]:
        """Main IP lookup function with caching and fallback"""
        # Check cache first
        if self.opts['cache_results'] and ip in self.cache:
            self.debug(f"Using cached result for {ip}")
            return self.cache[ip]

        # Try primary service
        data = self.queryIPInfo(ip)
        
        # Fallback if needed
        if data is None and self.opts['fallback_to_free']:
            self.debug(f"Falling back to free service for {ip}")
            data = self.queryFreeGeoIP(ip)

        # Cache result
        if data and self.opts['cache_results']:
            self.cache[ip] = data

        return data

    def handleEvent(self, event):
        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        # Skip if we've already processed this
        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Skip private IPs
        if self.sf.isValidLocalOrLoopbackIP(eventData):
            self.debug(f"Skipping local/loopback IP: {eventData}")
            return

        # Query IP information
        data = self.lookupIP(eventData)
        if not data:
            self.debug(f"No data found for {eventData}")
            return

        # Extract and emit events
        
        # Location coordinates
        if data.get('loc'):
            try:
                lat, lon = data['loc'].split(',')
                evt = SpiderFootEvent(
                    "PHYSICAL_COORDINATES",
                    f"{lat}, {lon}",
                    self.__name__,
                    event
                )
                self.notifyListeners(evt)
            except Exception:
                pass

        # Physical address
        location_parts = []
        if data.get('city'):
            location_parts.append(data['city'])
        if data.get('region'):
            location_parts.append(data['region'])
        if data.get('country'):
            location_parts.append(data['country'])
        
        if location_parts:
            location = ', '.join(location_parts)
            evt = SpiderFootEvent(
                "PHYSICAL_ADDRESS",
                location,
                self.__name__,
                event
            )
            self.notifyListeners(evt)

        # Geographic info
        geoinfo = []
        if data.get('city'):
            geoinfo.append(f"City: {data['city']}")
        if data.get('region'):
            geoinfo.append(f"Region: {data['region']}")
        if data.get('country'):
            geoinfo.append(f"Country: {data['country']}")
        if data.get('timezone'):
            geoinfo.append(f"Timezone: {data['timezone']}")
        if data.get('postal'):
            geoinfo.append(f"Postal: {data['postal']}")
        
        if geoinfo:
            evt = SpiderFootEvent(
                "GEOINFO",
                ', '.join(geoinfo),
                self.__name__,
                event
            )
            self.notifyListeners(evt)

        # Organization/ISP info
        if data.get('org'):
            # Try to parse AS number and org name
            org = data['org']
            if org.startswith('AS'):
                parts = org.split(' ', 1)
                if len(parts) == 2:
                    asn = parts[0]
                    org_name = parts[1]
                    
                    # Emit ISP name
                    evt = SpiderFootEvent(
                        "ISP_NAME",
                        org_name,
                        self.__name__,
                        event
                    )
                    self.notifyListeners(evt)
                    
                    # Also emit as company if it looks like one
                    if not any(word in org_name.lower() for word in ['hosting', 'cloud', 'server', 'vps']):
                        evt = SpiderFootEvent(
                            "COMPANY_NAME", 
                            org_name,
                            self.__name__,
                            event
                        )
                        self.notifyListeners(evt)
            else:
                # Just organization name without AS
                evt = SpiderFootEvent(
                    "COMPANY_NAME",
                    org,
                    self.__name__,
                    event
                )
                self.notifyListeners(evt)

        # Raw data for further processing
        evt = SpiderFootEvent(
            "RAW_RIR_DATA",
            json.dumps(data),
            self.__name__,
            event
        )
        self.notifyListeners(evt)


# End of sfp_unified_ip_info.py