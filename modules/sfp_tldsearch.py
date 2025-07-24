# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tldsearch
# Purpose:      SpiderFoot plug-in for identifying the existence of this target
#               on other TLDs.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     31/08/2013
# Copyright:   (c) Steve Micallef 2013
# Licence:     MIT
# -------------------------------------------------------------------------------

import random
import threading
import time

import dns.resolver

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_tldsearch(SpiderFootPlugin):

    meta = {
        'name': "TLD Searcher",
        'summary': "Search all Internet TLDs for domains with the same name as the target (this can be very slow.)",
        'flags': ["slow"],
        'useCases': ["Footprint"],
        'categories': ["DNS"]
    }

    # Default options
    opts = {
        'activeonly': False,  # Only report domains that have content (try to fetch the page)
        'skipwildcards': True,
        'use_priority_tlds': True,  # Use curated list for phishing detection
        'check_all_tlds': False,     # Option to check all TLDs
        'max_tlds': 100,             # Maximum TLDs to check when not using priority list
        '_maxthreads': 20
    }

    # Option descriptions
    optdescs = {
        'activeonly': "Only report domains that have content (try to fetch the page)?",
        "skipwildcards": "Skip TLDs and sub-TLDs that have wildcard DNS.",
        'use_priority_tlds': "Use curated list of high-risk TLDs for phishing detection?",
        'check_all_tlds': "Check all available TLDs (very slow)?",
        'max_tlds': "Maximum number of TLDs to check when not using priority list.",
        "_maxthreads": "Maximum threads"
    }

    # High-risk TLDs commonly used for phishing
    PHISHING_PRIORITY_TLDS = [
        # Major gTLDs
        'com', 'net', 'org', 'info', 'biz', 'co',
        
        # New gTLDs often used in phishing
        'online', 'site', 'website', 'tech', 'store', 
        'shop', 'app', 'cloud', 'io', 'ai', 'dev',
        'xyz', 'top', 'icu', 'buzz', 'live', 'club',
        
        # Free/cheap TLDs commonly abused
        'tk', 'ml', 'ga', 'cf', 'click', 'download',
        
        # Country TLDs with lax policies
        'cn', 'ru', 'in', 'br', 'cc', 'ws', 'to',
        
        # Korean TLDs
        'kr', 'co.kr', 'or.kr', 'com.kr', 'ne.kr',
        
        # Financial sector targeted TLDs
        'finance', 'money', 'loan', 'credit', 'bank',
        
        # Tech-related (for tech company impersonation)
        'systems', 'network', 'support', 'security'
    ]

    # Internal results tracking
    results = None

    # Track TLD search results between threads
    tldResults = dict()
    lock = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.__dataSource__ = "DNS"
        self.lock = threading.Lock()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["INTERNET_NAME"]

    # What events this module produces
    # This is to support the end user in selecting modules based on events
    # produced.
    def producedEvents(self):
        return ["SIMILARDOMAIN"]

    def getTldList(self):
        """Get the list of TLDs to check based on options."""
        if self.opts['use_priority_tlds']:
            self.info(f"Using priority TLD list with {len(self.PHISHING_PRIORITY_TLDS)} entries for phishing detection")
            return self.PHISHING_PRIORITY_TLDS
        
        if self.opts['check_all_tlds']:
            # Use all TLDs from SpiderFoot config
            all_tlds = self.opts.get('_internettlds', [])
            self.info(f"Using all {len(all_tlds)} TLDs (this will be slow)")
            return all_tlds
        
        # Use limited set from all TLDs
        all_tlds = self.opts.get('_internettlds', [])
        limit = min(self.opts['max_tlds'], len(all_tlds))
        # Prioritize common TLDs
        selected_tlds = []
        
        # First add common TLDs if they exist
        common = ['com', 'net', 'org', 'info', 'biz', 'co', 'io', 'app']
        for tld in common:
            if tld in all_tlds and tld not in selected_tlds:
                selected_tlds.append(tld)
        
        # Fill the rest randomly
        remaining = [t for t in all_tlds if t not in selected_tlds]
        while len(selected_tlds) < limit and remaining:
            idx = random.randint(0, len(remaining) - 1)
            selected_tlds.append(remaining.pop(idx))
        
        self.info(f"Using {len(selected_tlds)} selected TLDs")
        return selected_tlds

    def tryTld(self, target, tld):
        resolver = dns.resolver.Resolver()
        resolver.timeout = 1
        resolver.lifetime = 1
        resolver.search = list()
        if self.opts.get('_dnsserver', "") != "":
            resolver.nameservers = [self.opts['_dnsserver']]

        if self.opts['skipwildcards'] and self.sf.checkDnsWildcard(tld):
            return

        try:
            if not self.sf.resolveHost(target) and not self.sf.resolveHost6(target):
                with self.lock:
                    self.tldResults[target] = False
            else:
                with self.lock:
                    self.tldResults[target] = True
        except Exception:
            with self.lock:
                self.tldResults[target] = False

    def tryTldWrapper(self, tldList, sourceEvent):
        self.tldResults = dict()
        running = True
        t = []

        # Spawn threads for scanning
        self.info(f"Spawning threads to check TLDs: {len(tldList)} domains")
        for i, pair in enumerate(tldList):
            (domain, tld) = pair
            tn = 'thread_sfp_tldsearch_' + str(random.SystemRandom().randint(0, 999999999))
            t.append(threading.Thread(name=tn, target=self.tryTld, args=(domain, tld,)))
            t[i].start()

        # Block until all threads are finished
        while running:
            found = False
            for rt in threading.enumerate():
                if rt.name.startswith("thread_sfp_tldsearch_"):
                    found = True

            if not found:
                running = False

            time.sleep(0.1)

        for res in self.tldResults:
            if self.getTarget().matches(res, includeParents=True, includeChildren=True):
                continue
            if self.tldResults[res] and res not in self.results:
                self.sendEvent(sourceEvent, res)

    # Store the result internally and notify listening modules
    def sendEvent(self, source, result):
        self.info("Found a TLD with the target's name: " + result)
        self.results[result] = True

        # Inform listening modules
        if self.opts['activeonly']:
            if self.checkForStop():
                return

            pageContent = self.sf.fetchUrl('http://' + result,
                                           timeout=self.opts['_fetchtimeout'],
                                           useragent=self.opts['_useragent'],
                                           noLog=True,
                                           verify=False)
            if pageContent['content'] is not None:
                evt = SpiderFootEvent("SIMILARDOMAIN", result, self.__name__, source)
                self.notifyListeners(evt)
        else:
            evt = SpiderFootEvent("SIMILARDOMAIN", result, self.__name__, source)
            self.notifyListeners(evt)

    # Search for similar sounding domains
    def handleEvent(self, event):
        eventData = event.data

        if eventData in self.results:
            return

        self.results[eventData] = True

        keyword = self.sf.domainKeyword(eventData, self.opts['_internettlds'])

        if not keyword:
            self.error(f"Failed to extract keyword from {eventData}")
            return

        self.debug(f"Keyword extracted from {eventData}: {keyword}")

        if keyword in self.results:
            return

        self.results[keyword] = True

        # Get TLD list based on configuration
        tld_list = self.getTldList()
        
        # Look through selected TLDs for the existence of this target keyword
        targetList = list()
        for tld in tld_list:
            if type(tld) != str:
                tld = str(tld.strip(), errors='ignore')
            else:
                tld = tld.strip()

            if tld.startswith("//") or len(tld) == 0:
                continue

            if tld.startswith("!") or tld.startswith("*") or tld.startswith(".."):
                continue

            if tld.endswith(".arpa"):
                continue

            tryDomain = keyword + "." + tld

            if self.checkForStop():
                return

            if len(targetList) <= self.opts['_maxthreads']:
                targetList.append([tryDomain, tld])
            else:
                self.tryTldWrapper(targetList, event)
                targetList = list()

        # Scan whatever may be left over.
        if len(targetList) > 0:
            self.tryTldWrapper(targetList, event)

# End of sfp_tldsearch class