# SpiderFoot 모듈 통합 후 수정 체크리스트

## 1. 코드 수정 필요 사항

### A. 모듈 로더 수정
- [ ] `spiderfoot/helpers.py` - loadModulesAsDict() 함수
  - archived_modules 제외 확인
  - 통합 모듈 정상 로드 확인

### B. 프론트엔드 수정
- [ ] `sfwebui.py` 
  - modules() 함수 - 통합 모듈 표시
  - startscan() - 모듈 선택 로직
- [ ] `templates/newscan.tmpl`
  - 모듈 목록 표시
  - 카테고리별 그룹핑
- [ ] `templates/opts.tmpl`
  - 통합 모듈 설정 옵션 표시

### C. 스캔 엔진 수정
- [ ] `sfscan.py`
  - 통합 모듈 인스턴스 생성
  - 이벤트 라우팅 확인

### D. 데이터베이스 수정
- [ ] `spiderfoot/db.py`
  - 통합 모듈 설정 저장
  - 기존 모듈 설정 마이그레이션

## 2. 테스트 파일 정리

### 삭제 필요 테스트 (64개)
```bash
# Phase 1 모듈 테스트
rm test/unit/modules/test_sfp_myspace.py
rm test/unit/modules/test_sfp_punkspider.py
rm test/unit/modules/test_sfp_adguard_dns.py
# ... (나머지 DNS 필터 모듈들)

# Phase 2 모듈 테스트  
rm test/unit/modules/test_sfp_ipapico.py
rm test/unit/modules/test_sfp_ipapicom.py
# ... (나머지 삭제된 모듈들)
```

### 추가 필요 테스트 (3개)
```bash
# 통합 모듈 테스트
- test/unit/modules/test_sfp_unified_dns_filters.py
- test/unit/modules/test_sfp_unified_ip_info.py
- test/unit/modules/test_sfp_unified_search_engines.py
```

## 3. 설정 파일 업데이트

### 모듈 그룹/카테고리 설정
- [ ] 기본 모듈 그룹에서 삭제된 모듈 제거
- [ ] 통합 모듈을 적절한 카테고리에 추가

### API 키 마이그레이션
- [ ] 기존 모듈 API 키를 통합 모듈로 매핑
  - ipinfo API key → unified_ip_info
  - Google/Bing API keys → unified_search_engines

## 4. 사용자 마이그레이션

### 마이그레이션 스크립트 작성
```python
# migrate_modules.py
def migrate_user_config():
    # 기존 모듈 설정을 통합 모듈로 매핑
    mapping = {
        'sfp_ipinfo': 'sfp_unified_ip_info',
        'sfp_googlesearch': 'sfp_unified_search_engines',
        # ...
    }
```

### 사용자 안내
- [ ] CHANGELOG 업데이트
- [ ] 마이그레이션 가이드 작성
- [ ] 통합 모듈 사용법 문서화

## 5. UI/UX 개선

### 모듈 선택 화면
- [ ] 통합 모듈 하이라이트
- [ ] 카테고리별 정렬 개선
- [ ] 검색 기능 추가

### 설정 화면
- [ ] 통합 모듈의 복잡한 설정을 탭으로 구분
- [ ] API 키 관리 통합 인터페이스

## 6. 성능 모니터링

### 벤치마크
- [ ] 기존 개별 모듈 vs 통합 모듈 성능 비교
- [ ] API 호출 횟수 감소 확인
- [ ] 메모리 사용량 측정

### 로깅
- [ ] 통합 모듈의 상세 로깅
- [ ] 폴백 메커니즘 동작 확인

## 7. 문서화

### README 업데이트
- [ ] 모듈 목록 업데이트 (225 → 174개)
- [ ] 통합 모듈 장점 설명

### API 문서
- [ ] 통합 모듈 API 사용법
- [ ] 이벤트 타입 변경사항

## 8. 배포 준비

### 버전 관리
- [ ] VERSION 파일 업데이트 (4.0 → 4.1?)
- [ ] 호환성 경고 추가

### Docker 이미지
- [ ] Dockerfile 테스트
- [ ] docker-compose 업데이트

이 체크리스트를 따라 진행하면 모듈 통합으로 인한 영향을 최소화하면서 안정적으로 마이그레이션할 수 있습니다.