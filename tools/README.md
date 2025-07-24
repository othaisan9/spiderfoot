# SpiderFoot 프록시 도구

SpiderFoot에서 사용할 수 있는 Tor 및 Privoxy 프록시 관리 도구입니다.

## 도구 목록

- **tor_proxy.py**: Tor SOCKS5 프록시 관리자
- **privoxy_proxy.py**: Privoxy HTTP 프록시 관리자 (Tor와 연동 가능)

## 설치 방법

### 1. 시스템 패키지 설치

#### Ubuntu/Debian
```bash
# Tor 설치
sudo apt-get update
sudo apt-get install -y tor

# Privoxy 설치
sudo apt-get install -y privoxy

# 추가 유틸리티 (선택사항)
sudo apt-get install -y python3-pip python3-dev
```

#### CentOS/RHEL/Fedora
```bash
# Tor 설치
sudo yum install -y epel-release
sudo yum install -y tor

# Privoxy 설치
sudo yum install -y privoxy
```

#### macOS
```bash
# Homebrew가 필요합니다
brew install tor
brew install privoxy
```

#### Arch Linux
```bash
sudo pacman -S tor
sudo pacman -S privoxy
```

### 2. Python 패키지 설치

```bash
# tools 디렉토리로 이동
cd tools/

# 필요한 Python 패키지 설치
pip install -r requirements.txt
```

## 사용 방법

### Tor SOCKS5 프록시

#### 기본 사용법
```bash
# 대화형 모드로 실행
python tools/tor_proxy.py

# 테스트 모드 (기능 시연)
python tools/tor_proxy.py --test

# 데몬 모드로 실행
python tools/tor_proxy.py --daemon

# 사용자 정의 포트
python tools/tor_proxy.py --socks-port 9150 --control-port 9151
```

#### Python에서 사용
```python
from tools.tor_proxy import TorProxy

# 프록시 시작
proxy = TorProxy()
proxy.start()

# 현재 IP 확인
current_ip = proxy.get_current_ip()
print(f"현재 IP: {current_ip}")

# requests와 함께 사용
import requests
proxies = proxy.get_proxy_dict()
response = requests.get('https://api.ipify.org', proxies=proxies)

# IP 변경 (새로운 신원)
proxy.rotate_identity()

# 종료
proxy.stop()
```

### Privoxy HTTP 프록시

#### 기본 사용법
```bash
# Privoxy만 실행 (Tor 연동)
python tools/privoxy_proxy.py

# Tor 없이 실행 (직접 연결)
python tools/privoxy_proxy.py --no-tor

# Tor + Privoxy 통합 실행
python tools/privoxy_proxy.py --with-tor

# 테스트 모드
python tools/privoxy_proxy.py --test
```

#### Python에서 사용
```python
from tools.privoxy_proxy import TorHttpProxy

# Tor + HTTP 프록시 시작
proxy = TorHttpProxy()
proxy.start()

# HTTP 요청
proxies = proxy.get_proxy_dict()
response = requests.get('http://example.com', proxies=proxies)

# 현재 IP 확인
print(f"현재 IP: {proxy.get_current_ip()}")

# IP 변경
proxy.rotate_identity()

# 종료
proxy.stop()
```

### SpiderFoot 모듈에서 사용

```python
from spiderfoot import SpiderFootPlugin
from tools.tor_proxy import TorProxy

class sfp_my_module(SpiderFootPlugin):
    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        
        # Tor 프록시 사용 옵션이 있으면
        if userOpts.get('use_tor', False):
            self.proxy = TorProxy()
            self.proxy.start()
            self.proxies = self.proxy.get_proxy_dict()
        else:
            self.proxies = None
    
    def fetchUrl(self, url):
        if self.proxies:
            # Tor를 통한 익명 요청
            return self.sf.fetchUrl(url, proxy=self.proxies)
        else:
            # 일반 요청
            return self.sf.fetchUrl(url)
    
    def finish(self):
        if hasattr(self, 'proxy') and self.proxy:
            self.proxy.stop()
```

## 프록시 설정

### 기본 포트
- **Tor SOCKS5**: 9050
- **Tor Control**: 9051  
- **Privoxy HTTP**: 8118

### 환경 변수
```bash
# Tor 프록시
export SOCKS_PROXY=socks5h://127.0.0.1:9050

# HTTP 프록시
export HTTP_PROXY=http://127.0.0.1:8118
export HTTPS_PROXY=http://127.0.0.1:8118
```

### 브라우저 설정
- Firefox: 설정 → 네트워크 설정 → 수동 프록시 구성
  - SOCKS 호스트: 127.0.0.1, 포트: 9050 (SOCKS5)
  - HTTP 프록시: 127.0.0.1, 포트: 8118

## 주요 기능

### Tor 프록시 (tor_proxy.py)
- ✅ 자동 Tor 설치 및 구성
- ✅ SOCKS5 프록시 제공
- ✅ IP 주소 순환 (신원 변경)
- ✅ 연결 테스트 및 검증
- ✅ 세션 관리

### Privoxy 프록시 (privoxy_proxy.py)
- ✅ HTTP/HTTPS 프록시 제공
- ✅ SOCKS5를 HTTP로 변환
- ✅ Tor와 통합 가능
- ✅ 필터 및 액션 규칙
- ✅ 광고 차단 가능

## 보안 주의사항

1. **IP 유출 방지**
   - DNS 유출 방지를 위해 `socks5h://` 프로토콜 사용
   - WebRTC 유출 주의

2. **신원 관리**
   - 민감한 요청 사이에는 신원 순환
   - 동일 세션에서 실명 계정 접근 금지

3. **트래픽 분석**
   - HTTPS 사용 권장
   - 자바스크립트 비활성화 고려

4. **로컬 전용**
   - 프록시는 localhost에서만 접근 가능
   - 원격 접근 차단됨

## 문제 해결

### Tor가 시작되지 않을 때
```bash
# Tor 프로세스 확인
ps aux | grep tor

# 포트 사용 확인
sudo lsof -i :9050

# Tor 로그 확인
sudo journalctl -u tor
```

### Privoxy가 시작되지 않을 때
```bash
# Privoxy 프로세스 확인
ps aux | grep privoxy

# 포트 사용 확인
sudo lsof -i :8118

# Privoxy 설정 테스트
privoxy --config-test
```

### 연결 실패
- 방화벽 규칙 확인
- 프록시 포트가 열려있는지 확인
- Tor 브리지 사용 고려 (검열 지역)

## 성능 최적화

1. **회로 수명 조정**
   - `MaxCircuitDirtiness`: 회로 교체 주기 (기본 10분)
   - `NewCircuitPeriod`: 새 회로 생성 주기

2. **대역폭 제한**
   - `BandwidthRate`: 평균 대역폭
   - `BandwidthBurst`: 최대 대역폭

3. **연결 공유**
   - HTTP Keep-Alive 활성화
   - 연결 재사용으로 성능 향상

## 라이선스

SpiderFoot 프로젝트와 동일한 라이선스를 따릅니다.