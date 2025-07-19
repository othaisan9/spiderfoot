# SpiderFoot 공격적 모듈 정리 계획

## 1. 즉시 삭제 대상 모듈 (50개)

### IP 지리정보 조회 (중복) - 4개 삭제
```bash
# sfp_ipinfo.py 하나로 통합
rm modules/sfp_ipapico.py
rm modules/sfp_ipapicom.py  
rm modules/sfp_ipstack.py
rm modules/sfp_ipregistry.py
```

### 검색 엔진 (중복) - 5개 삭제
```bash
# 일반 검색은 Google 하나로
rm modules/sfp_bingsearch.py
rm modules/sfp_duckduckgo.py

# Tor 검색은 Ahmia 하나로
rm modules/sfp_torch.py
rm modules/sfp_onionsearchengine.py
rm modules/sfp_onioncity.py
```

### 이메일 관련 (중복) - 5개 삭제
```bash
rm modules/sfp_emailformat.py
rm modules/sfp_skymem.py
rm modules/sfp_debounce.py
rm modules/sfp_nameapi.py  # 중복 이메일 검증
rm modules/sfp_emailrep.py  # 너무 제한적
```

### WHOIS (중복/유료) - 3개 삭제
```bash
rm modules/sfp_whoisology.py  # 유료
rm modules/sfp_jsonwhoiscom.py  # 유료
rm modules/sfp_whoxy.py  # 유료, reversewhois와 중복
```

### DNS 관련 (과도한 중복) - 8개 삭제
```bash
rm modules/sfp_dnsneighbor.py  # 특수 기능, 거의 안씀
rm modules/sfp_opennic.py  # 대체 DNS, 필요성 낮음
rm modules/sfp_robtex.py  # 다른 모듈과 중복
rm modules/sfp_viewdns.py  # 신뢰도 낮음
rm modules/sfp_networksdb.py  # IP 정보와 중복
rm modules/sfp_sublist3r.py  # 다른 서브도메인 모듈과 중복
rm modules/sfp_hackertarget.py  # 여러 기능 중복
rm modules/sfp_dnsdumpster.py  # 불안정
```

### 오래되거나 신뢰도 낮은 서비스 - 15개 삭제
```bash
rm modules/sfp_multiproxy.py
rm modules/sfp_callername.py
rm modules/sfp_citadel.py
rm modules/sfp_cybercrimetracker.py
rm modules/sfp_botvrij.py
rm modules/sfp_malwarepatrol.py  # 유료 전환
rm modules/sfp_vxvault.py  # 업데이트 중단
rm modules/sfp_emergingthreats.py  # 접근성 문제
rm modules/sfp_fortinet.py  # 제한적
rm modules/sfp_greensnow.py  # 신뢰도 낮음
rm modules/sfp_focsec.py  # 제한적 데이터
rm modules/sfp_honeypot.py  # Project Honeypot 제한적
rm modules/sfp_psbdmp.py  # 불안정한 서비스
rm modules/sfp_searchcode.py  # GitHub으로 대체 가능
rm modules/sfp_wikileaks.py  # OSINT와 관련성 낮음
```

### 소셜 미디어 (오래됨/중복) - 5개 삭제
```bash
rm modules/sfp_myspace.py  # 이미 archived
rm modules/sfp_slideshare.py  # LinkedIn과 통합됨
rm modules/sfp_stackoverflow.py  # OSINT 가치 낮음
rm modules/sfp_flickr.py  # 사용 감소
rm modules/sfp_gravatar.py  # 제한적 정보
```

### 비트코인/암호화폐 (중복) - 2개 삭제
```bash
rm modules/sfp_bitcoinwhoswho.py  # bitcoinabuse와 중복
rm modules/sfp_blockchain.py  # bitcoin 모듈과 통합
```

### 기타 저가치 모듈 - 8개 삭제
```bash
rm modules/sfp_abstractapi.py  # 여러 모듈과 중복
rm modules/sfp_numverify.py  # 제한적 전화번호 검증
rm modules/sfp_textmagic.py  # numverify와 중복
rm modules/sfp_trashpanda.py  # 불안정한 paste 서비스
rm modules/sfp_h1nobbdde.py  # 비공식 서비스
rm modules/sfp_gleif.py  # 매우 특수한 용도
rm modules/sfp_wikipediaedits.py  # OSINT 가치 낮음
rm modules/sfp_c99.py  # 상업적/회색지대 서비스
```

## 2. 통합 대상 모듈

### IP 정보 통합 모듈
```python
# sfp_unified_ip_info.py
# 통합: ipinfo + 기본 GeoIP 기능
```

### 검색 엔진 통합 모듈
```python
# sfp_unified_search.py
# Google + Bing + DuckDuckGo API 통합
```

### 암호화폐 통합 모듈
```python
# sfp_unified_crypto.py
# Bitcoin + Ethereum + 악성 주소 DB 통합
```

### 평판 조회 통합 모듈
```python
# sfp_unified_reputation.py
# 여러 평판 서비스 통합
```

## 3. 최종 결과

- **삭제 전**: 220개 모듈
- **삭제 후**: 170개 모듈 (50개 삭제)
- **통합 후**: 150개 모듈 (추가 20개 통합)

**32% 감소** - 유지보수 부담 대폭 감소