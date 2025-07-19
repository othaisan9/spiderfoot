#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot 모듈 카테고리 재구성 스크립트
각 모듈을 적절한 카테고리 폴더로 분류
"""

import os
import shutil

# 모듈 카테고리 매핑
MODULE_CATEGORIES = {
    'osint': [
        'sfp_alienvault.py',
        'sfp_alienvaultiprep.py', 
        'sfp_binaryedge.py',
        'sfp_censys.py',
        'sfp_fullhunt.py',
        'sfp_greynoise.py',
        'sfp_greynoise_community.py',
        'sfp_hackertarget.py',
        'sfp_intelx.py',
        'sfp_onyphe.py',
        'sfp_riskiq.py',
        'sfp_securitytrails.py',
        'sfp_shodan.py',
        'sfp_spyonweb.py',
        'sfp_urlscan.py',
        'sfp_virustotal.py',
        'sfp_xforce.py',
        'sfp_zetalytics.py'
    ],
    'security': [
        'sfp_abusech.py',
        'sfp_abuseipdb.py',
        'sfp_badpackets.py',
        'sfp_blocklistde.py',
        'sfp_botscout.py',
        'sfp_botvrij.py',
        'sfp_cinsscore.py',
        'sfp_citadel.py',
        'sfp_cleantalk.py',
        'sfp_cybercrimetracker.py',
        'sfp_dronebl.py',
        'sfp_emergingthreats.py',
        'sfp_fortinet.py',
        'sfp_fraudguard.py',
        'sfp_googlesafebrowsing.py',
        'sfp_greensnow.py',
        'sfp_honeypot.py',
        'sfp_hybrid_analysis.py',
        'sfp_ipqualityscore.py',
        'sfp_isc.py',
        'sfp_maltiverse.py',
        'sfp_malwarepatrol.py',
        'sfp_metadefender.py',
        'sfp_multiproxy.py',
        'sfp_openphish.py',
        'sfp_phishstats.py',
        'sfp_phishtank.py',
        'sfp_projectdiscovery.py',
        'sfp_pulsedive.py',
        'sfp_sorbs.py',
        'sfp_spamcop.py',
        'sfp_spamhaus.py',
        'sfp_spur.py',
        'sfp_stevenblack_hosts.py',
        'sfp_surbl.py',
        'sfp_talosintel.py',
        'sfp_threatcrowd.py',
        'sfp_threatfox.py',
        'sfp_threatjammer.py',
        'sfp_threatminer.py',
        'sfp_torexits.py',
        'sfp_uceprotect.py',
        'sfp_unified_dns_filters.py',  # 새로 만든 통합 모듈
        'sfp_voipbl.py',
        'sfp_vxvault.py',
        'sfp_zoneh.py'
    ],
    'social': [
        'sfp_accounts.py',
        'sfp_facebook.py',
        'sfp_flickr.py',
        'sfp_github.py',
        'sfp_gravatar.py',
        'sfp_instagram.py',
        'sfp_keybase.py',
        'sfp_linkedin.py',
        'sfp_myspace.py',
        'sfp_skymem.py',
        'sfp_slideshare.py',
        'sfp_social.py',
        'sfp_sociallinks.py',
        'sfp_socialprofiles.py',
        'sfp_stackoverflow.py',
        'sfp_twitter.py',
        'sfp_venmo.py',
        'sfp_whoisology.py',
        'sfp_wikileaks.py',
        'sfp_wikipediaedits.py'
    ],
    'dns': [
        'sfp_dnsbrute.py',
        'sfp_dnscommonsrv.py',
        'sfp_dnsneighbor.py',
        'sfp_dnsraw.py',
        'sfp_dnsresolve.py',
        'sfp_dnszonexfer.py',
        'sfp_opennic.py',
        'sfp_reversewhois.py',
        'sfp_similar.py',
        'sfp_tldsearch.py'
    ],
    'passive_dns': [
        'sfp_circl.py',
        'sfp_crobat_api.py',
        'sfp_dnsdb.py',
        'sfp_dnsdumpster.py',
        'sfp_dnsgrep.py',
        'sfp_mnemonic.py',
        'sfp_robtex.py',
        'sfp_sublist3r.py',
        'sfp_viewdns.py'
    ],
    'search': [
        'sfp_ahmia.py',
        'sfp_archiveorg.py',
        'sfp_bingsearch.py',
        'sfp_bingsharedip.py',
        'sfp_commoncrawl.py',
        'sfp_crossref.py',
        'sfp_duckduckgo.py',
        'sfp_googlesearch.py',
        'sfp_grep_app.py',
        'sfp_onionsearchengine.py',
        'sfp_pastebin.py',
        'sfp_psbdmp.py',
        'sfp_searchcode.py',
        'sfp_torch.py',
        'sfp_trashpanda.py',
        'sfp_websearch.py'
    ],
    'data_leaks': [
        'sfp_dehashed.py',
        'sfp_haveibeenpwned.py',
        'sfp_leakix.py',
        'sfp_snov.py'
    ],
    'reputation': [
        'sfp_abusix.py',
        'sfp_bgpview.py',
        'sfp_blockchain.py',
        'sfp_builtwith.py',
        'sfp_clearbit.py',
        'sfp_emailcrawlr.py',
        'sfp_emailformat.py',
        'sfp_emailrep.py',
        'sfp_focsec.py',
        'sfp_fullcontact.py',
        'sfp_host.py',
        'sfp_hostio.py',
        'sfp_hunter.py',
        'sfp_ipapi.py',
        'sfp_ipapico.py',
        'sfp_ipinfo.py',
        'sfp_ipregistry.py',
        'sfp_ipstack.py',
        'sfp_jsonwhoiscom.py',
        'sfp_nameapi.py',
        'sfp_networksdb.py',
        'sfp_neutrinoapi.py',
        'sfp_numverify.py',
        'sfp_opencorporates.py',
        'sfp_openstreetmap.py',
        'sfp_seon.py',
        'sfp_textmagic.py',
        'sfp_trumail.py',
        'sfp_twilio.py',
        'sfp_whois.py',
        'sfp_whoxy.py',
        'sfp_wigle.py'
    ],
    'utilities': [
        'sfp__stor_db.py',
        'sfp__stor_stdout.py',
        'sfp_abstractapi.py',
        'sfp_base64.py',
        'sfp_binstring.py',
        'sfp_bitcoin.py',
        'sfp_company.py',
        'sfp_cookie.py',
        'sfp_countryname.py',
        'sfp_creditcard.py',
        'sfp_customfeed.py',
        'sfp_email.py',
        'sfp_errors.py',
        'sfp_ethereum.py',
        'sfp_filemeta.py',
        'sfp_hashes.py',
        'sfp_hosting.py',
        'sfp_iban.py',
        'sfp_intfiles.py',
        'sfp_junkfiles.py',
        'sfp_names.py',
        'sfp_pageinfo.py',
        'sfp_pgp.py',
        'sfp_phone.py',
        'sfp_portscan_tcp.py',
        'sfp_spider.py',
        'sfp_sslcert.py',
        'sfp_strangeheaders.py',
        'sfp_subdomain_takeover.py',
        'sfp_template.py',
        'sfp_webanalytics.py',
        'sfp_webframework.py',
        'sfp_webserver.py'
    ]
}

# 도구 관련 모듈은 별도 처리 (tool_ prefix)
TOOL_MODULES = [
    'sfp_tool_cmseek.py',
    'sfp_tool_dnstwist.py', 
    'sfp_tool_nbtscan.py',
    'sfp_tool_nmap.py',
    'sfp_tool_nuclei.py',
    'sfp_tool_onesixtyone.py',
    'sfp_tool_retirejs.py',
    'sfp_tool_snallygaster.py',
    'sfp_tool_testsslsh.py',
    'sfp_tool_trufflehog.py',
    'sfp_tool_wafw00f.py',
    'sfp_tool_wappalyzer.py',
    'sfp_tool_whatweb.py'
]

# 클라우드 스토리지 관련 모듈
CLOUD_MODULES = [
    'sfp_azureblobstorage.py',
    'sfp_digitaloceanspace.py',
    'sfp_googleobjectstorage.py',
    'sfp_grayhatwarfare.py',
    'sfp_s3bucket.py'
]

# 암호화폐 관련 모듈
CRYPTO_MODULES = [
    'sfp_bitcoin.py',
    'sfp_bitcoinabuse.py', 
    'sfp_bitcoinwhoswho.py',
    'sfp_blockchain.py',
    'sfp_ethereum.py',
    'sfp_etherscan.py'
]

def print_migration_summary():
    """마이그레이션 요약 출력"""
    print("\n=== SpiderFoot 모듈 카테고리 재구성 계획 ===\n")
    
    total = 0
    for category, modules in MODULE_CATEGORIES.items():
        print(f"{category}: {len(modules)}개 모듈")
        total += len(modules)
    
    print(f"\n도구 모듈 (tools/): {len(TOOL_MODULES)}개")
    print(f"클라우드 모듈 (cloud/): {len(CLOUD_MODULES)}개")
    print(f"암호화폐 모듈 (crypto/): {len(CRYPTO_MODULES)}개")
    print(f"\n총 분류된 모듈: {total + len(TOOL_MODULES) + len(CLOUD_MODULES) + len(CRYPTO_MODULES)}개")

if __name__ == "__main__":
    print_migration_summary()
    
    # 실제 마이그레이션은 주석 처리
    # 실행하려면 아래 주석 해제
    """
    # 추가 디렉토리 생성
    os.makedirs('modules/tools', exist_ok=True)
    os.makedirs('modules/cloud', exist_ok=True) 
    os.makedirs('modules/crypto', exist_ok=True)
    
    # 모듈 이동
    for category, modules in MODULE_CATEGORIES.items():
        for module in modules:
            src = f'modules/{module}'
            dst = f'modules/{category}/{module}'
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"Moved {module} to {category}/")
    
    # 도구 모듈 이동
    for module in TOOL_MODULES:
        src = f'modules/{module}'
        dst = f'modules/tools/{module}'
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"Moved {module} to tools/")
    
    # 클라우드 모듈 이동
    for module in CLOUD_MODULES:
        src = f'modules/{module}'
        dst = f'modules/cloud/{module}'
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"Moved {module} to cloud/")
    
    # 암호화폐 모듈 이동
    for module in CRYPTO_MODULES:
        src = f'modules/{module}'
        dst = f'modules/crypto/{module}'
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"Moved {module} to crypto/")
    """