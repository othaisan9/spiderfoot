# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_accounts_optimized
# Purpose:      Optimized version of account finder with performance improvements
#
# Author:      SpiderFoot Team
#
# Created:     2025-01-20
# Copyright:   (c) SpiderFoot 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from spiderfoot import SpiderFootEvent, SpiderFootHelpers, SpiderFootPlugin


class sfp_accounts(SpiderFootPlugin):

    meta = {
        'name': "Account Finder (Optimized)",
        'summary': "High-performance account finder with ThreadPoolExecutor and smart filtering",
        'useCases': ["Footprint", "Passive"],
        'categories': ["Social Media"]
    }

    opts = {
        "ignorenamedict": True,
        "ignoreworddict": True,
        "musthavename": True,
        "userfromemail": True,
        "permutate": False,
        "usernamesize": 4,
        "max_results": 50,  # 조기 종료
        "max_workers": 50,  # 동시 작업자 수
        "timeout": 5,       # 사이트당 타임아웃
        "priority_only": False  # 우선순위 사이트만 확인
    }

    optdescs = {
        "ignorenamedict": "Don't bother looking up names that are just stand-alone first names",
        "ignoreworddict": "Don't bother looking up names that appear in the dictionary",
        "musthavename": "The username must be mentioned on the social media page",
        "userfromemail": "Extract usernames from e-mail addresses",
        "permutate": "Look for the existence of account name permutations",
        "usernamesize": "The minimum length of a username to query",
        "max_results": "Stop after finding this many accounts (0 = no limit)",
        "max_workers": "Maximum concurrent workers",
        "timeout": "Timeout per site request (seconds)",
        "priority_only": "Only check priority sites (faster but less comprehensive)"
    }

    # 우선순위 사이트 목록
    PRIORITY_SITES = [
        'github', 'gitlab', 'bitbucket',
        'linkedin', 'twitter', 'instagram', 'facebook', 'tiktok',
        'reddit', 'youtube', 'medium', 'dev.to',
        'stackoverflow', 'hackerone', 'bugcrowd'
    ]

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.reportedUsers = list()
        self.errorState = False
        self.__dataSource__ = "Social Media"
        
        # HTTP 세션 최적화
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=100,
            pool_maxsize=100
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # 느린 사이트 추적
        self.slow_sites = set()
        
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        self.commonNames = SpiderFootHelpers.humanNamesFromWordlists()
        self.words = SpiderFootHelpers.dictionaryWordsFromWordlists()

        # WhatsMyName 데이터 로드
        content = self.sf.cacheGet("sfaccountsv2", 48)
        if content is None:
            url = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
            data = self.sf.fetchUrl(url, useragent="SpiderFoot")

            if data['content'] is None:
                self.error(f"Unable to fetch {url}")
                self.errorState = True
                return

            content = data['content']
            self.sf.cachePut("sfaccountsv2", content)

        try:
            all_sites = json.loads(content)['sites']
            self.sites = [site for site in all_sites if not site.get('valid', True) is False]
            
            # 사이트 우선순위 정렬
            self.sites = self.prioritize_sites(self.sites)
            
        except Exception as e:
            self.error(f"Unable to parse social media accounts list: {e}")
            self.errorState = True
            return

    def prioritize_sites(self, sites):
        """사이트를 우선순위에 따라 정렬"""
        priority = []
        normal = []
        
        for site in sites:
            site_name = site.get('name', '').lower()
            if any(p in site_name for p in self.PRIORITY_SITES):
                priority.append(site)
            else:
                normal.append(site)
        
        if self.opts['priority_only']:
            return priority
        
        return priority + normal

    def watchedEvents(self):
        return ["EMAILADDR", "DOMAIN_NAME", "HUMAN_NAME", "USERNAME"]

    def producedEvents(self):
        return ["USERNAME", "ACCOUNT_EXTERNAL_OWNED", "SIMILAR_ACCOUNT_EXTERNAL"]

    def checkSite(self, username, site):
        """개별 사이트 확인 - 최적화된 버전"""
        if site['name'] in self.slow_sites:
            return None
            
        start_time = time.time()
        
        if 'uri_check' not in site:
            return None

        url = site['uri_check'].format(account=username)
        if 'uri_pretty' in site:
            ret_url = site['uri_pretty'].format(account=username)
        else:
            ret_url = url
            
        retname = f"{site['name']} (Category: {site['cat']})\n<SFURL>{ret_url}</SFURL>"

        try:
            # 최적화된 요청
            headers = {'User-Agent': self.opts['_useragent']}
            if site.get('post_body'):
                response = self.session.post(
                    url, 
                    data=site['post_body'],
                    headers=headers,
                    timeout=self.opts['timeout'],
                    verify=False
                )
            else:
                response = self.session.get(
                    url,
                    headers=headers, 
                    timeout=self.opts['timeout'],
                    verify=False
                )
            
            content = response.text
            code = str(response.status_code)
            
        except Exception as e:
            self.debug(f"Error checking {site['name']}: {e}")
            # 타임아웃이 자주 발생하면 느린 사이트로 분류
            if time.time() - start_time > self.opts['timeout']:
                self.slow_sites.add(site['name'])
            return None

        # 응답 검증
        if site.get('e_code') and site.get('e_code') != site.get('m_code'):
            if code != str(site.get('e_code')):
                return None

        if site.get('e_string') and site.get('e_string') not in content:
            return None
            
        if site.get('m_string') and site.get('m_string') in content:
            return None

        if self.opts['musthavename']:
            if username.lower() not in content.lower():
                self.debug(f"Skipping {site['name']} as username not mentioned.")
                return None

        # 성공
        return retname

    def checkSites(self, username):
        """ThreadPoolExecutor를 사용한 병렬 처리"""
        results = []
        found_count = 0
        max_results = self.opts['max_results']
        
        with ThreadPoolExecutor(max_workers=self.opts['max_workers']) as executor:
            # 모든 작업 제출
            future_to_site = {}
            for site in self.sites:
                if max_results > 0 and found_count >= max_results:
                    break
                    
                future = executor.submit(self.checkSite, username, site)
                future_to_site[future] = site
            
            # 완료된 작업부터 처리
            for future in as_completed(future_to_site):
                result = future.result()
                if result:
                    results.append(result)
                    found_count += 1
                    
                    # 조기 종료
                    if max_results > 0 and found_count >= max_results:
                        self.info(f"Reached max_results limit ({max_results}), stopping search")
                        # 나머지 작업 취소
                        for f in future_to_site:
                            f.cancel()
                        break
        
        return results

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        users = list()

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            return

        self.results[eventData] = True

        # 이벤트별 사용자명 추출
        if eventName == "HUMAN_NAME":
            names = [eventData.lower().replace(" ", ""), eventData.lower().replace(" ", ".")]
            for name in names:
                users.append(name)

        if eventName == "DOMAIN_NAME":
            kw = self.sf.domainKeyword(eventData, self.opts['_internettlds'])
            if kw:
                users.append(kw)

        if eventName == "EMAILADDR" and self.opts['userfromemail']:
            name = eventData.split("@")[0].lower()
            users.append(name)

        if eventName == "USERNAME":
            users.append(eventData)

        # 사용자명 검증 및 처리
        for user in set(users):
            if user in self.opts['_genericusers'].split(","):
                self.debug(f"{user} is a generic account name, skipping.")
                continue

            if self.opts['ignorenamedict'] and user in self.commonNames:
                self.debug(f"{user} is found in our name dictionary, skipping.")
                continue

            if self.opts['ignoreworddict'] and user in self.words:
                self.debug(f"{user} is found in our word dictionary, skipping.")
                continue

            if user not in self.reportedUsers and eventData != user:
                if len(user) < self.opts['usernamesize']:
                    self.debug(f"{user} is too short, skipping.")
                    continue

                evt = SpiderFootEvent("USERNAME", user, self.__name__, event)
                self.notifyListeners(evt)
                self.reportedUsers.append(user)

        # USERNAME 이벤트일 때만 실제 검색 수행
        if eventName == "USERNAME":
            start_time = time.time()
            res = self.checkSites(eventData)
            elapsed = time.time() - start_time
            
            self.info(f"Found {len(res)} accounts for {eventData} in {elapsed:.2f}s")
            
            for site in res:
                evt = SpiderFootEvent("ACCOUNT_EXTERNAL_OWNED", site, self.__name__, event)
                self.notifyListeners(evt)

# End of sfp_accounts_optimized.py