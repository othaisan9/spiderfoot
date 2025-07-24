# Systemd 서비스 파일

SpiderFoot와 프록시를 시스템 서비스로 실행하기 위한 systemd 설정 파일입니다.

## 설치 방법

1. 서비스 파일 복사
```bash
# 시스템 전역 설치
sudo cp spiderfoot-proxy.service /etc/systemd/system/

# 사용자별 설치 (권장)
mkdir -p ~/.config/systemd/user/
cp spiderfoot-proxy.service ~/.config/systemd/user/
```

2. 경로 수정
서비스 파일에서 다음 경로들을 실제 경로로 수정하세요:
- `WorkingDirectory=/home/wynne/othaisan/Spierfoot_BE/spiderfoot`
- `ExecStart=/usr/bin/python3 /home/wynne/othaisan/Spierfoot_BE/spiderfoot/start_spiderfoot_with_proxy.py`
- `ReadWritePaths=/home/wynne/othaisan/Spierfoot_BE/spiderfoot`

3. 서비스 활성화 및 시작
```bash
# 시스템 서비스로 (root 권한 필요)
sudo systemctl daemon-reload
sudo systemctl enable spiderfoot-proxy@$USER.service
sudo systemctl start spiderfoot-proxy@$USER.service

# 사용자 서비스로 (권장)
systemctl --user daemon-reload
systemctl --user enable spiderfoot-proxy.service
systemctl --user start spiderfoot-proxy.service
```

## 서비스 관리

### 상태 확인
```bash
# 시스템 서비스
sudo systemctl status spiderfoot-proxy@$USER.service

# 사용자 서비스
systemctl --user status spiderfoot-proxy.service
```

### 로그 확인
```bash
# 시스템 서비스
sudo journalctl -u spiderfoot-proxy@$USER.service -f

# 사용자 서비스
journalctl --user -u spiderfoot-proxy.service -f
```

### 서비스 중지
```bash
# 시스템 서비스
sudo systemctl stop spiderfoot-proxy@$USER.service

# 사용자 서비스
systemctl --user stop spiderfoot-proxy.service
```

### 서비스 재시작
```bash
# 시스템 서비스
sudo systemctl restart spiderfoot-proxy@$USER.service

# 사용자 서비스
systemctl --user restart spiderfoot-proxy.service
```

## 자동 시작 설정

부팅 시 자동으로 시작하려면:
```bash
# 시스템 서비스
sudo systemctl enable spiderfoot-proxy@$USER.service

# 사용자 서비스 (사용자 로그인 시 시작)
systemctl --user enable spiderfoot-proxy.service
```

## 문제 해결

1. **권한 오류**: 사용자 서비스로 실행하는 것을 권장합니다.

2. **포트 충돌**: 기본 포트가 사용 중이면 `start_spiderfoot_with_proxy.py`의 인자를 수정하세요:
   ```
   ExecStart=/usr/bin/python3 /path/to/start_spiderfoot_with_proxy.py --sf-port 5002 --socks-port 9150
   ```

3. **Python 경로**: Python 3 경로가 다르면 수정하세요:
   ```bash
   which python3
   ```

4. **서비스 실패**: 로그를 확인하여 원인을 파악하세요:
   ```bash
   journalctl --user -u spiderfoot-proxy.service -n 50
   ```