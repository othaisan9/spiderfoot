# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_unified_dns_filters
# Purpose:      Unified SpiderFoot plugin for checking if hosts are blocked by
#               various DNS filtering services (CloudFlare, OpenDNS, Quad9, etc.)
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-01
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import dns.resolver
from typing import List, Dict, Optional, Tuple

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_unified_dns_filters(SpiderFootPlugin):

    meta = {
        'name': "Unified DNS Filters",
        'summary': "Check if a host would be blocked by various DNS filtering services (CloudFlare, OpenDNS, Quad9, AdGuard, etc.)",
        'flags': [],
        'useCases': ["Investigate", "Passive"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'website': "https://github.com/smicallef/spiderfoot",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://developers.cloudflare.com/1.1.1.1/1.1.1.1-for-families/",
                "https://www.opendns.com/setupguide/",
                "https://www.quad9.net/",
                "https://adguard-dns.io/en/public-dns.html",
                "https://cleanbrowsing.org/guides/dnsoverhttps",
                "https://dnsforfamily.com/",
                "https://dns.yandex.com/",
                "https://www.comodo.com/secure-dns/"
            ],
            'favIcon': "",
            'logo': "",
            'description': "Unified module to check multiple DNS filtering services including "
            "CloudFlare for Families, OpenDNS, Quad9, AdGuard DNS, CleanBrowsing, "
            "DNS for Family, Yandex DNS, and Comodo Secure DNS.",
        }
    }

    # DNS filter configurations
    DNS_FILTERS = {
        'cloudflare_family': {
            'name': 'CloudFlare for Families',
            'servers': ['1.1.1.3', '1.0.0.3'],
            'type': 'family',
            'description': 'Blocks adult content'
        },
        'cloudflare_malware': {
            'name': 'CloudFlare Security',
            'servers': ['1.1.1.2', '1.0.0.2'],
            'type': 'malware',
            'description': 'Blocks malware'
        },
        'opendns_family': {
            'name': 'OpenDNS FamilyShield',
            'servers': ['208.67.222.123', '208.67.220.123'],
            'type': 'family',
            'description': 'Blocks adult content'
        },
        'quad9': {
            'name': 'Quad9',
            'servers': ['9.9.9.9', '149.112.112.112'],
            'type': 'malware',
            'description': 'Blocks malicious domains'
        },
        'adguard_family': {
            'name': 'AdGuard Family Protection',
            'servers': ['94.140.14.15', '94.140.15.16'],
            'type': 'family',
            'description': 'Blocks adult content and enforces safe search'
        },
        'adguard_default': {
            'name': 'AdGuard Default',
            'servers': ['94.140.14.14', '94.140.15.15'],
            'type': 'ads',
            'description': 'Blocks ads and trackers'
        },
        'cleanbrowsing_family': {
            'name': 'CleanBrowsing Family',
            'servers': ['185.228.168.168', '185.228.169.168'],
            'type': 'family',
            'description': 'Blocks adult content'
        },
        'cleanbrowsing_adult': {
            'name': 'CleanBrowsing Adult',
            'servers': ['185.228.168.10', '185.228.169.11'],
            'type': 'family',
            'description': 'Blocks adult content only'
        },
        'cleanbrowsing_security': {
            'name': 'CleanBrowsing Security',
            'servers': ['185.228.168.9', '185.228.169.9'],
            'type': 'malware',
            'description': 'Blocks malware, phishing, and malicious domains'
        },
        'dns_for_family': {
            'name': 'DNS for Family',
            'servers': ['94.130.180.225', '78.47.64.161'],
            'type': 'family',
            'description': 'Blocks adult content'
        },
        'yandex_family': {
            'name': 'Yandex Family',
            'servers': ['77.88.8.7', '77.88.8.3'],
            'type': 'family',
            'description': 'Blocks adult content'
        },
        'yandex_safe': {
            'name': 'Yandex Safe',
            'servers': ['77.88.8.88', '77.88.8.2'],
            'type': 'malware',
            'description': 'Blocks malicious and fraudulent sites'
        },
        'comodo_secure': {
            'name': 'Comodo Secure DNS',
            'servers': ['8.26.56.26', '8.20.247.20'],
            'type': 'malware',
            'description': 'Blocks malware, phishing and malicious domains'
        }
    }

    opts = {
        'check_family_filters': True,
        'check_malware_filters': True,
        'check_ad_filters': True
    }

    optdescs = {
        'check_family_filters': "Check family-safe/adult content filtering services",
        'check_malware_filters': "Check malware/security filtering services",
        'check_ad_filters': "Check ad-blocking filtering services"
    }

    results = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return [
            "INTERNET_NAME",
            "AFFILIATE_INTERNET_NAME",
            "CO_HOSTED_SITE"
        ]

    def producedEvents(self):
        return [
            "BLACKLISTED_INTERNET_NAME",
            "BLACKLISTED_AFFILIATE_INTERNET_NAME",
            "BLACKLISTED_COHOST",
            "MALICIOUS_INTERNET_NAME",
            "MALICIOUS_AFFILIATE_INTERNET_NAME",
            "MALICIOUS_COHOST",
        ]

    def queryDNS(self, qaddr: str, nameservers: List[str]) -> Optional[dns.resolver.Answer]:
        """Query DNS using specified nameservers."""
        res = dns.resolver.Resolver()
        res.nameservers = nameservers

        try:
            return res.resolve(qaddr)
        except Exception:
            self.debug(f"Unable to resolve {qaddr} using {nameservers}")

        return None

    def checkFilters(self, domain: str) -> Dict[str, bool]:
        """Check domain against all configured DNS filters."""
        blocked_by = {}
        
        for filter_id, config in self.DNS_FILTERS.items():
            # Skip filters based on user preferences
            if config['type'] == 'family' and not self.opts['check_family_filters']:
                continue
            if config['type'] == 'malware' and not self.opts['check_malware_filters']:
                continue
            if config['type'] == 'ads' and not self.opts['check_ad_filters']:
                continue
            
            # Check if domain is blocked
            result = self.queryDNS(domain, config['servers'])
            
            if result is None:
                # Domain is blocked (NXDOMAIN or similar)
                blocked_by[filter_id] = config
                self.debug(f"{domain} is blocked by {config['name']}")
            else:
                # Check for blocking IPs (some services return special IPs for blocked domains)
                for answer in result:
                    ip = str(answer)
                    # Common blocking IPs
                    blocking_ips = ['0.0.0.0', '127.0.0.1', '::1', '0.0.0.1']
                    if ip in blocking_ips:
                        blocked_by[filter_id] = config
                        self.debug(f"{domain} is blocked by {config['name']} (blocking IP: {ip})")
                        break
        
        return blocked_by

    def handleEvent(self, event):
        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Map event types to produced event types
        malicious_type = "MALICIOUS_" + eventName
        blacklisted_type = "BLACKLISTED_" + eventName

        if eventName == "CO_HOSTED_SITE":
            malicious_type = "MALICIOUS_COHOST"
            blacklisted_type = "BLACKLISTED_COHOST"

        # Check the domain against all filters
        blocked_by = self.checkFilters(eventData)
        
        if not blocked_by:
            return

        # Generate events based on filter types
        malware_filters = []
        family_filters = []
        
        for filter_id, config in blocked_by.items():
            if config['type'] == 'malware':
                malware_filters.append(config['name'])
            elif config['type'] in ['family', 'ads']:
                family_filters.append(config['name'])

        # Report malware blocks
        if malware_filters:
            self.info(f"{eventData} blocked by malware filters: {', '.join(malware_filters)}")
            evt = SpiderFootEvent(
                malicious_type,
                f"Blocked by DNS filters [{', '.join(malware_filters)}]",
                self.__name__,
                event
            )
            self.notifyListeners(evt)

        # Report family/content blocks
        if family_filters:
            self.info(f"{eventData} blocked by content filters: {', '.join(family_filters)}")
            evt = SpiderFootEvent(
                blacklisted_type,
                f"Blocked by DNS filters [{', '.join(family_filters)}]",
                self.__name__,
                event
            )
            self.notifyListeners(evt)


# End of sfp_unified_dns_filters.py