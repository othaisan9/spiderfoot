# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_unified_search_engines
# Purpose:      Unified search engine module combining Google, Bing, DuckDuckGo
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-01
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import re
import time
import urllib.parse
from typing import List, Dict, Set, Optional

from spiderfoot import SpiderFootEvent, SpiderFootPlugin, SpiderFootHelpers


class sfp_unified_search_engines(SpiderFootPlugin):

    meta = {
        'name': "Unified Search Engines",
        'summary': "Query Google, Bing, and DuckDuckGo APIs for information about the target",
        'flags': ["apikey"],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Search Engines"],
        'dataSource': {
            'website': "https://github.com/smicallef/spiderfoot",
            'model': "FREE_AUTH_LIMITED",
            'references': [
                "https://developers.google.com/custom-search/v1/overview",
                "https://www.microsoft.com/en-us/bing/apis/bing-web-search-api",
                "https://duckduckgo.com/api"
            ],
            'description': "Unified search module that queries multiple search engines "
            "including Google Custom Search, Bing Search API, and DuckDuckGo. "
            "Falls back to free alternatives when API keys are not available.",
        }
    }

    opts = {
        'google_api_key': '',
        'google_cse_id': '',
        'bing_api_key': '',
        'max_pages': 10,
        'max_results_per_engine': 100,
        'use_duckduckgo_free': True,
        'delay_between_queries': 1
    }

    optdescs = {
        'google_api_key': "Google API key for Custom Search API",
        'google_cse_id': "Google Custom Search Engine ID", 
        'bing_api_key': "Bing Search API key",
        'max_pages': "Maximum number of pages to fetch per engine",
        'max_results_per_engine': "Maximum results per search engine",
        'use_duckduckgo_free': "Use DuckDuckGo's free instant answer API",
        'delay_between_queries': "Seconds between API queries"
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return [
            "DOMAIN_NAME",
            "DOMAIN_NAME_PARENT",
            "INTERNET_NAME",
            "EMAILADDR",
            "HUMAN_NAME"
        ]

    def producedEvents(self):
        return [
            "LINKED_URL_INTERNAL",
            "LINKED_URL_EXTERNAL", 
            "RAW_RIR_DATA",
            "SEARCH_ENGINE_WEB_CONTENT",
            "EMAILADDR",
            "EMAILADDR_GENERIC",
            "INTERNET_NAME",
            "DOMAIN_NAME",
            "AFFILIATE_INTERNET_NAME"
        ]

    def searchGoogle(self, query: str) -> List[Dict]:
        """Search using Google Custom Search API"""
        if not self.opts['google_api_key'] or not self.opts['google_cse_id']:
            return []

        results = []
        start = 1
        
        for page in range(self.opts['max_pages']):
            if len(results) >= self.opts['max_results_per_engine']:
                break

            url = (
                f"https://www.googleapis.com/customsearch/v1"
                f"?key={self.opts['google_api_key']}"
                f"&cx={self.opts['google_cse_id']}"
                f"&q={urllib.parse.quote(query)}"
                f"&start={start}"
            )

            res = self.sf.fetchUrl(
                url,
                timeout=30,
                useragent=self.opts['_useragent']
            )

            if res['content'] is None:
                self.debug("No response from Google")
                break

            try:
                data = json.loads(res['content'])
                
                if 'error' in data:
                    self.error(f"Google API error: {data['error'].get('message', 'Unknown error')}")
                    break

                if 'items' not in data:
                    break

                for item in data['items']:
                    results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'source': 'Google'
                    })

                # Check if more results available
                if 'queries' in data and 'nextPage' in data['queries']:
                    start = data['queries']['nextPage'][0]['startIndex']
                else:
                    break

                time.sleep(self.opts['delay_between_queries'])

            except Exception as e:
                self.error(f"Error parsing Google response: {e}")
                break

        return results

    def searchBing(self, query: str) -> List[Dict]:
        """Search using Bing Search API"""
        if not self.opts['bing_api_key']:
            return []

        results = []
        offset = 0
        
        for page in range(self.opts['max_pages']):
            if len(results) >= self.opts['max_results_per_engine']:
                break

            url = (
                f"https://api.bing.microsoft.com/v7.0/search"
                f"?q={urllib.parse.quote(query)}"
                f"&offset={offset}"
                f"&count=50"
            )

            headers = {
                'Ocp-Apim-Subscription-Key': self.opts['bing_api_key']
            }

            res = self.sf.fetchUrl(
                url,
                headers=headers,
                timeout=30,
                useragent=self.opts['_useragent']
            )

            if res['content'] is None:
                self.debug("No response from Bing")
                break

            try:
                data = json.loads(res['content'])
                
                if 'error' in data:
                    self.error(f"Bing API error: {data['error'].get('message', 'Unknown error')}")
                    break

                if 'webPages' not in data or 'value' not in data['webPages']:
                    break

                for item in data['webPages']['value']:
                    results.append({
                        'title': item.get('name', ''),
                        'link': item.get('url', ''),
                        'snippet': item.get('snippet', ''),
                        'source': 'Bing'
                    })

                offset += 50
                
                # Check if more results available
                if offset >= data.get('webPages', {}).get('totalEstimatedMatches', 0):
                    break

                time.sleep(self.opts['delay_between_queries'])

            except Exception as e:
                self.error(f"Error parsing Bing response: {e}")
                break

        return results

    def searchDuckDuckGo(self, query: str) -> List[Dict]:
        """Search using DuckDuckGo instant answer API (limited)"""
        if not self.opts['use_duckduckgo_free']:
            return []

        results = []
        
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"

        res = self.sf.fetchUrl(
            url,
            timeout=30,
            useragent=self.opts['_useragent']
        )

        if res['content'] is None:
            self.debug("No response from DuckDuckGo")
            return []

        try:
            data = json.loads(res['content'])
            
            # DuckDuckGo instant answer API is limited
            # Extract what we can
            if data.get('AbstractURL'):
                results.append({
                    'title': data.get('Heading', query),
                    'link': data['AbstractURL'],
                    'snippet': data.get('AbstractText', ''),
                    'source': 'DuckDuckGo'
                })

            # Related topics often contain useful links
            for topic in data.get('RelatedTopics', []):
                if isinstance(topic, dict) and 'FirstURL' in topic:
                    results.append({
                        'title': topic.get('Text', '').split(' - ')[0],
                        'link': topic['FirstURL'],
                        'snippet': topic.get('Text', ''),
                        'source': 'DuckDuckGo'
                    })

        except Exception as e:
            self.error(f"Error parsing DuckDuckGo response: {e}")

        return results

    def processResults(self, results: List[Dict], source_event):
        """Process search results and generate events"""
        emails = set()
        domains = set()
        
        for result in results:
            link = result.get('link', '')
            snippet = result.get('snippet', '')
            
            # Extract domain from URL
            domain = self.sf.urlFQDN(link)
            if domain and domain not in domains:
                domains.add(domain)
                
                # Check if internal or external link
                if self.getTarget().matches(domain):
                    evt = SpiderFootEvent("LINKED_URL_INTERNAL", link, self.__name__, source_event)
                else:
                    evt = SpiderFootEvent("LINKED_URL_EXTERNAL", link, self.__name__, source_event)
                self.notifyListeners(evt)

            # Extract emails from snippet
            for email in SpiderFootHelpers.extractEmailsFromText(snippet):
                if email not in emails:
                    emails.add(email)
                    evt = SpiderFootEvent("EMAILADDR", email, self.__name__, source_event)
                    self.notifyListeners(evt)

            # Store raw content
            if snippet:
                evt = SpiderFootEvent(
                    "SEARCH_ENGINE_WEB_CONTENT",
                    f"{result['source']}: {snippet}",
                    self.__name__,
                    source_event
                )
                self.notifyListeners(evt)

    def handleEvent(self, event):
        eventName = event.eventType
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {event.module}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        # Build search queries based on event type
        queries = []
        
        if eventName in ["DOMAIN_NAME", "DOMAIN_NAME_PARENT", "INTERNET_NAME"]:
            queries = [
                f'site:{eventData}',
                f'"{eventData}"',
                f'related:{eventData}'
            ]
        elif eventName == "EMAILADDR":
            queries = [f'"{eventData}"']
        elif eventName == "HUMAN_NAME":
            queries = [f'"{eventData}"']

        # Perform searches
        all_results = []
        
        for query in queries:
            self.info(f"Searching for: {query}")
            
            # Google search
            if self.opts['google_api_key']:
                results = self.searchGoogle(query)
                all_results.extend(results)
                self.info(f"Google returned {len(results)} results")

            # Bing search
            if self.opts['bing_api_key']:
                results = self.searchBing(query)
                all_results.extend(results)
                self.info(f"Bing returned {len(results)} results")

            # DuckDuckGo search (always available)
            if self.opts['use_duckduckgo_free']:
                results = self.searchDuckDuckGo(query)
                all_results.extend(results)
                self.info(f"DuckDuckGo returned {len(results)} results")

            time.sleep(self.opts['delay_between_queries'])

        # Process all results
        if all_results:
            self.info(f"Total search results: {len(all_results)}")
            self.processResults(all_results, event)


# End of sfp_unified_search_engines.py