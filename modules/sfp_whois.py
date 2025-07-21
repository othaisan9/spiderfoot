# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_whois
# Purpose:      SpiderFoot plug-in for searching Whois servers for domain names
#               and netblocks identified.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2015
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

import ipwhois
import netaddr
import whois
import time

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_whois(SpiderFootPlugin):

    meta = {
        'name': "Whois",
        'summary': "Perform a WHOIS look-up on domain names and owned netblocks.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Public Registries"]
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    results = None
    failed_queries = None  # Track failed WHOIS queries to avoid retries
    last_query_time = 0  # Track last WHOIS query time for rate limiting
    
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.failed_queries = self.tempStorage()
        self.last_query_time = 0

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "DOMAIN_NAME_PARENT", "NETBLOCK_OWNER", "NETBLOCKV6_OWNER",
                "CO_HOSTED_SITE_DOMAIN", "AFFILIATE_DOMAIN_NAME", "SIMILARDOMAIN"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["DOMAIN_WHOIS", "NETBLOCK_WHOIS", "DOMAIN_REGISTRAR",
                "CO_HOSTED_SITE_DOMAIN_WHOIS", "AFFILIATE_DOMAIN_WHOIS",
                "SIMILARDOMAIN_WHOIS"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if eventData in self.results:
            return

        # Check if we've already failed to query this domain
        if eventData in self.failed_queries:
            self.debug(f"Skipping {eventData} - previous WHOIS query failed")
            return

        self.results[eventData] = True

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName.startswith("DOMAIN_NAME"):
            typ = "DOMAIN_WHOIS"
        elif eventName.startswith("NETBLOCK"):
            typ = "NETBLOCK_WHOIS"
        elif eventName.startswith("AFFILIATE_DOMAIN_NAME"):
            typ = "AFFILIATE_DOMAIN_WHOIS"
        elif eventName.startswith("CO_HOSTED_SITE_DOMAIN"):
            typ = "CO_HOSTED_SITE_DOMAIN_WHOIS"
        elif eventName == "SIMILARDOMAIN":
            typ = "SIMILARDOMAIN_WHOIS"
        else:
            self.error(f"Invalid event type: {eventName}")
            return

        data = None
        
        # Rate limiting: wait at least 2 seconds between WHOIS queries
        current_time = time.time()
        time_since_last = current_time - self.last_query_time
        if time_since_last < 2:
            wait_time = 2 - time_since_last
            self.debug(f"Rate limiting: waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
        
        self.last_query_time = time.time()

        if eventName in ["NETBLOCK_OWNER", "NETBLOCKV6_OWNER"]:
            try:
                netblock = netaddr.IPNetwork(eventData)
            except Exception as e:
                self.error(f"Invalid netblock {eventData}: {e}")
                return

            ip = netblock[0]
            self.debug(f"Sending RDAP query for IP address: {ip}")

            try:
                # TODO: this should use the configured proxy
                r = ipwhois.IPWhois(ip)
                data = str(r.lookup_rdap(depth=1))
            except Exception as e:
                self.error(f"Unable to perform WHOIS query on {ip}: {e}")
        else:
            self.debug(f"Sending WHOIS query for domain: {eventData}")
            try:
                whoisdata = whois.whois(eventData)
                data = str(whoisdata.text)
            except Exception as e:
                self.error(f"Unable to perform WHOIS query on {eventData}: {e}")
                self.failed_queries[eventData] = True

        if not data:
            self.error(f"No WHOIS record for {eventData}")
            self.failed_queries[eventData] = True
            return

        # This is likely to be an error about being throttled rather than real data
        if len(str(data)) < 250:
            self.error(f"WHOIS data ({len(data)} bytes) is smaller than 250 bytes. Throttling from WHOIS server is probably happening. Ignoring response.")
            self.failed_queries[eventData] = True
            return

        rawevt = SpiderFootEvent(typ, data, self.__name__, event)
        self.notifyListeners(rawevt)

        if eventName.startswith("DOMAIN_NAME"):
            if whoisdata:
                registrar = whoisdata.get('registrar')
                if registrar:
                    evt = SpiderFootEvent("DOMAIN_REGISTRAR", registrar, self.__name__, event)
                    self.notifyListeners(evt)

# End of sfp_whois class
