# SpiderFoot 비동기 처리 아키텍처 설계

## 개요

SpiderFoot의 성능을 대폭 향상시키기 위해 비동기 처리를 도입합니다. 
기존 동기식 코드와의 호환성을 유지하면서 점진적으로 마이그레이션할 수 있는 구조를 설계합니다.

## 핵심 컴포넌트

### 1. AsyncSpiderFootPlugin (비동기 플러그인 베이스 클래스)
- 기존 SpiderFootPlugin을 상속
- 비동기 메서드 지원
- 동기/비동기 모듈 공존 가능

### 2. AsyncHttpClient (비동기 HTTP 클라이언트)
- aiohttp 기반
- 연결 풀링
- 자동 재시도
- Rate limiting
- 프록시 지원

### 3. AsyncDnsResolver (비동기 DNS 리졸버)
- aiodns 기반
- 캐싱
- 동시 쿼리 제한

### 4. AsyncEventQueue (비동기 이벤트 큐)
- asyncio.Queue 기반
- 백프레셔 처리
- 우선순위 큐 지원

### 5. RateLimiter (속도 제한기)
- 토큰 버킷 알고리즘
- 도메인별 제한
- 글로벌 제한

## 아키텍처 다이어그램

```
┌─────────────────┐     ┌─────────────────┐
│ Sync Modules    │     │ Async Modules   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ├───────────┬───────────┤
         │           │           │
         ▼           ▼           ▼
┌─────────────────────────────────────────┐
│       AsyncSpiderFootPlugin             │
│  - async handleEvent()                  │
│  - async setup()                        │
│  - backward compatible                  │
└─────────────┬───────────────────────────┘
              │
              ├────────────┬────────────┬────────────┐
              ▼            ▼            ▼            ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ AsyncHttpClient  │ │AsyncDnsResolver│ │AsyncEventQueue│ │ RateLimiter  │
│ - get()         │ │ - resolve()    │ │ - put()      │ │ - acquire()  │
│ - post()        │ │ - reverse()    │ │ - get()      │ │ - release()  │
│ - session pool  │ │ - cache        │ │ - priority   │ │ - per domain │
└──────────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## 단계별 구현 계획

### Phase 1: 기본 인프라 (1주)
1. AsyncSpiderFootPlugin 베이스 클래스
2. AsyncHttpClient 구현
3. RateLimiter 구현
4. 기본 테스트 작성

### Phase 2: 핵심 모듈 변환 (2주)
1. API 호출이 많은 모듈 선정
   - sfp_shodan
   - sfp_virustotal
   - sfp_censys
   - 통합 모듈들 (unified_*)
2. 비동기 버전 작성
3. 성능 테스트

### Phase 3: DNS 및 네트워크 모듈 (1주)
1. AsyncDnsResolver 구현
2. DNS 관련 모듈 변환
3. 포트 스캔 모듈 비동기화

### Phase 4: 최적화 및 안정화 (1주)
1. 이벤트 큐 최적화
2. 메모리 사용량 최적화
3. 에러 처리 강화
4. 문서화

## 코드 예시

### AsyncSpiderFootPlugin
```python
class AsyncSpiderFootPlugin(SpiderFootPlugin):
    def __init__(self):
        super().__init__()
        self.http_client: Optional[AsyncHttpClient] = None
        
    async def setup(self, sf, opts):
        """비동기 설정 메서드"""
        self.sf = sf
        self.opts = opts
        self.http_client = AsyncHttpClient(
            proxy=opts.get('_socks1type'),
            rate_limiter=self.rate_limiter
        )
        
    async def handleEvent(self, event):
        """비동기 이벤트 처리"""
        raise NotImplementedError
        
    # 동기 메서드와의 호환성을 위한 래퍼
    def handleEvent_sync(self, event):
        """동기식 호출을 위한 래퍼"""
        return asyncio.run(self.handleEvent(event))
```

### 사용 예시
```python
class sfp_shodan_async(AsyncSpiderFootPlugin):
    async def handleEvent(self, event):
        if event.eventType == "IP_ADDRESS":
            # 비동기 API 호출
            results = await self.http_client.get(
                f"https://api.shodan.io/shodan/host/{event.data}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            
            # 동시에 여러 요청 처리
            tasks = []
            for port in results.get('ports', []):
                task = self.check_service(event.data, port)
                tasks.append(task)
            
            services = await asyncio.gather(*tasks)
```

## 성능 목표

- API 호출 속도: 10x 향상 (동시 요청)
- DNS 조회: 5x 향상 (비동기 + 캐싱)
- 메모리 사용량: 30% 감소 (스트리밍 처리)
- 전체 스캔 시간: 3-5x 단축

## 주의사항

1. **호환성 유지**
   - 기존 동기 모듈과 공존
   - 점진적 마이그레이션 가능
   - API 변경 최소화

2. **리소스 관리**
   - 연결 수 제한
   - 메모리 사용량 모니터링
   - 타임아웃 설정

3. **에러 처리**
   - 재시도 로직
   - 폴백 메커니즘
   - 상세한 로깅

## 테스트 전략

1. **단위 테스트**
   - 각 비동기 컴포넌트
   - Mock을 활용한 API 테스트

2. **통합 테스트**
   - 동기/비동기 모듈 혼용
   - 실제 API 엔드포인트 테스트

3. **성능 테스트**
   - 부하 테스트
   - 메모리 프로파일링
   - 응답 시간 측정

## 모니터링

- 동시 연결 수
- API 호출 속도
- 큐 크기
- 에러율
- 메모리 사용량