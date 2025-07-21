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

from concurrent.futures import ThreadPoolExecutor, as_completed
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
        '_maxthreads': 50,   # Reduced to prevent overload
        'max_results': 20,   # Reduced to limit cascade effects
        'priority_tlds': True,  # Check common TLDs first
        'check_timeout': 30,  # Timeout per domain check (seconds)
    }

    # Option descriptions
    optdescs = {
        'activeonly': "Only report domains that have content (try to fetch the page)?",
        'skipwildcards': "Skip TLDs and sub-TLDs that have wildcard DNS.",
        '_maxthreads': "Maximum threads for concurrent checks",
        'max_results': "Maximum number of similar domains to find before stopping (0 = unlimited)",
        'priority_tlds': "Check common TLDs (.com, .net, .org, etc.) first?",
        'check_timeout': "Timeout per domain check in seconds",
    }

    # Priority TLDs that are checked first
    priority_tld_list = [
        'com', 'net', 'org', 'info', 'biz', 'io', 'co', 'us', 'uk', 'ca',
        'de', 'fr', 'au', 'eu', 'ru', 'cn', 'jp', 'br', 'in', 'it', 'es',
        'nl', 'se', 'ch', 'no', 'dk', 'be', 'at', 'pl', 'ir', 'cz', 'gr',
        'il', 'mx', 'pt', 'kr', 'ar', 'tr', 'tw', 'id', 'ua', 'za', 'sg',
        'my', 'th', 'vn', 'ph', 'ng', 'eg', 'pk', 'pe', 'co.uk', 'com.au',
        'co.za', 'com.br', 'co.in', 'co.jp', 'com.mx', 'com.ar', 'com.tr'
    ]

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.__dataSource__ = "DNS"
        # DNS cache for the session
        self.dns_cache = {}
        # Wildcard cache
        self.wildcard_cache = {}

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self):
        return ["SIMILARDOMAIN"]

    def checkDnsWildcardCached(self, tld):
        """Check if a TLD has wildcard DNS (with caching)."""
        if tld in self.wildcard_cache:
            return self.wildcard_cache[tld]
        
        result = self.sf.checkDnsWildcard(tld)
        self.wildcard_cache[tld] = result
        return result

    def tryTld(self, domain, tld):
        """Try to resolve a domain (improved with caching)."""
        # Check cache first
        if domain in self.dns_cache:
            return self.dns_cache[domain]
        
        # Skip wildcards if enabled
        if self.opts['skipwildcards'] and self.checkDnsWildcardCached(tld):
            self.dns_cache[domain] = False
            return False
        
        resolver = dns.resolver.Resolver()
        resolver.timeout = 1
        resolver.lifetime = 1
        resolver.search = list()
        
        if self.opts.get('_dnsserver', "") != "":
            resolver.nameservers = [self.opts['_dnsserver']]

        try:
            # Check both IPv4 and IPv6
            result = bool(self.sf.resolveHost(domain) or self.sf.resolveHost6(domain))
            self.dns_cache[domain] = result
            return result
        except Exception as e:
            self.debug(f"Failed to resolve {domain}: {e}")
            self.dns_cache[domain] = False
            return False

    def checkActiveContent(self, domain):
        """Check if domain has active web content."""
        if not self.opts['activeonly']:
            return True
            
        try:
            self.debug(f"Checking for active content on {domain}")
            pageContent = self.sf.fetchUrl(
                f'http://{domain}',
                timeout=self.opts['_fetchtimeout'],
                useragent=self.opts['_useragent'],
                noLog=True,
                verify=False
            )
            return pageContent['content'] is not None
        except Exception as e:
            self.debug(f"Error checking active content for {domain}: {e}")
            return False

    def isValidTld(self, tld):
        """Check if a TLD is valid for scanning."""
        if type(tld) != str:
            tld = str(tld.strip(), errors='ignore')
        else:
            tld = tld.strip()
        
        # Skip comments, empty lines, and special entries
        if (tld.startswith("//") or len(tld) == 0 or 
            tld.startswith("!") or tld.startswith("*") or 
            tld.startswith("..") or tld.endswith(".arpa")):
            return False
        
        return True

    def handleEvent(self, event):
        """Handle events to this module."""
        eventData = event.data

        if eventData in self.results:
            return

        self.results[eventData] = True

        # Extract keyword from domain
        keyword = self.sf.domainKeyword(eventData, self.opts['_internettlds'])
        if not keyword:
            self.error(f"Failed to extract keyword from {eventData}")
            return

        self.debug(f"Keyword extracted from {eventData}: {keyword}")

        if keyword in self.results:
            return

        self.results[keyword] = True

        # Prepare TLD lists
        all_tlds = []
        priority_domains = []
        regular_domains = []
        
        # Process all TLDs
        for tld in self.opts['_internettlds']:
            if not self.isValidTld(tld):
                continue
            
            tld = tld.strip()
            domain = f"{keyword}.{tld}"
            
            # Separate priority and regular TLDs
            if self.opts['priority_tlds'] and tld in self.priority_tld_list:
                priority_domains.append((domain, tld))
            else:
                regular_domains.append((domain, tld))
        
        # Combine lists with priority domains first
        all_domains = priority_domains + regular_domains
        
        self.info(f"Checking {len(all_domains)} TLDs for keyword '{keyword}' "
                  f"({len(priority_domains)} priority, {len(regular_domains)} regular)")
        
        # Track results
        found_count = 0
        max_results = self.opts.get('max_results', 50)
        if max_results == 0:
            max_results = float('inf')
        
        # Use ThreadPoolExecutor for concurrent DNS lookups
        max_workers = min(self.opts['_maxthreads'], 100)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_domain = {
                executor.submit(self.tryTld, domain, tld): (domain, tld)
                for domain, tld in all_domains
            }
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_domain):
                # Check if we should stop
                if self.checkForStop():
                    self.info("Scan aborted, shutting down threads")
                    executor.shutdown(wait=False)
                    break
                
                domain, tld = future_to_domain[future]
                
                try:
                    # Use configurable timeout
                    check_timeout = self.opts.get('check_timeout', 30)
                    result = future.result(timeout=check_timeout)
                    
                    if result and domain not in self.results:
                        # Check if target matches (avoid self-reference)
                        if self.getTarget().matches(domain, includeParents=True, includeChildren=True):
                            continue
                        
                        # Check for active content if required
                        if self.opts['activeonly'] and not self.checkActiveContent(domain):
                            self.debug(f"Skipping {domain} - no active content")
                            continue
                        
                        # Found a valid similar domain
                        self.info(f"Found similar domain: {domain}")
                        self.results[domain] = True
                        found_count += 1
                        
                        # Create and notify event
                        evt = SpiderFootEvent("SIMILARDOMAIN", domain, self.__name__, event)
                        self.notifyListeners(evt)
                        
                        # Progress update
                        if found_count % 10 == 0:
                            self.info(f"Progress: {found_count} similar domains found so far")
                        
                        # Check if we've found enough
                        if found_count >= max_results:
                            self.info(f"Reached maximum results limit ({max_results}), stopping search")
                            executor.shutdown(wait=False)
                            break
                            
                except Exception as e:
                    self.debug(f"Error processing {domain}: {e}")
        
        # Final summary
        self.info(f"TLD search completed. Found {found_count} similar domains for '{keyword}'")

# End of sfp_tldsearch class