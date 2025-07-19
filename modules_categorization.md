# SpiderFoot 모듈 카테고리 분류 및 리팩토링 계획

## 1. 제거된 모듈 (archived_modules/)
- **sfp_myspace.py** - MySpace가 읽기 전용 모드로 전환, 기능 제한적
- **sfp_punkspider.py** - API 가용성 불명확
- **sfp_socialprofiles.py** - Google+ 코드 제거 (수정됨)

## 2. 중복 모듈 통합 계획

### DNS 차단 서비스 체크 모듈 (8개)
통합 대상:
- sfp_adguard_dns.py
- sfp_cleanbrowsing.py
- sfp_cloudflaredns.py
- sfp_comodo.py
- sfp_dns_for_family.py
- sfp_opendns.py
- sfp_quad9.py
- sfp_yandexdns.py

→ **sfp_unified_dns_filters.py**로 통합

### 검색 엔진 모듈
통합 대상:
- sfp_googlesearch.py
- sfp_bingsearch.py
- sfp_duckduckgo.py

→ **sfp_unified_search_engines.py**로 통합

## 3. 모듈 카테고리 재구성

### OSINT/정보수집
- 검색 엔진 (통합 모듈)
- 소셜 미디어 스캔
- 데이터 유출 조회

### 보안/위협 분석
- 악성코드/블랙리스트 체크
- 취약점 스캔
- 평판 조회

### DNS/네트워크
- DNS 조회 및 분석
- 네트워크 정보 수집
- IP 정보 분석

### 도메인/웹
- 웹 기술 스택 분석
- SSL 인증서 분석
- 웹 서버 정보

### 유틸리티
- 데이터 추출 (이메일, 전화번호 등)
- 파일 메타데이터 분석
- 해시/암호화 관련

## 4. 다음 단계
1. DNS 필터 통합 모듈 구현
2. 검색 엔진 통합 모듈 구현
3. 모듈 디렉토리 구조 재구성