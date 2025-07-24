#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SpiderFoot 프록시 통합 실행 스크립트

Tor와 Privoxy를 자동으로 시작하고 SpiderFoot를 실행합니다.
"""

import os
import sys
import time
import subprocess
import signal
import argparse
import logging
from pathlib import Path

# SpiderFoot 루트 디렉토리 설정
SPIDERFOOT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(SPIDERFOOT_ROOT))

from tools.tor_proxy import TorProxy
from tools.privoxy_proxy import PrivoxyProxy, TorHttpProxy


class SpiderFootLauncher:
    """SpiderFoot를 프록시와 함께 실행하는 런처"""
    
    def __init__(self, use_tor=True, use_privoxy=True, 
                 socks_port=9050, http_port=8118, 
                 sf_port=5001, sf_host='127.0.0.1'):
        self.use_tor = use_tor
        self.use_privoxy = use_privoxy
        self.socks_port = socks_port
        self.http_port = http_port
        self.sf_port = sf_port
        self.sf_host = sf_host
        
        self.tor_proxy = None
        self.privoxy_proxy = None
        self.combined_proxy = None
        self.sf_process = None
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """종료 시그널 처리"""
        self.logger.info("종료 시그널을 받았습니다. 정리 중...")
        self.stop()
        sys.exit(0)
    
    def start_proxies(self):
        """프록시 서비스 시작"""
        try:
            if self.use_tor and self.use_privoxy:
                # Tor + Privoxy 통합 모드
                self.logger.info("Tor + Privoxy 통합 프록시를 시작합니다...")
                self.combined_proxy = TorHttpProxy(
                    http_port=self.http_port,
                    socks_port=self.socks_port
                )
                if not self.combined_proxy.start():
                    raise Exception("Tor + Privoxy 시작 실패")
                
                self.logger.info(f"✓ HTTP 프록시: http://127.0.0.1:{self.http_port}")
                self.logger.info(f"✓ SOCKS5 프록시: socks5h://127.0.0.1:{self.socks_port}")
                
                # 현재 IP 표시
                ip = self.combined_proxy.get_current_ip()
                self.logger.info(f"✓ 현재 Tor IP: {ip}")
                
            elif self.use_tor:
                # Tor만 사용
                self.logger.info("Tor SOCKS5 프록시를 시작합니다...")
                self.tor_proxy = TorProxy(socks_port=self.socks_port)
                if not self.tor_proxy.start():
                    raise Exception("Tor 시작 실패")
                
                self.logger.info(f"✓ SOCKS5 프록시: socks5h://127.0.0.1:{self.socks_port}")
                
                # 현재 IP 표시
                ip = self.tor_proxy.get_current_ip()
                self.logger.info(f"✓ 현재 Tor IP: {ip}")
                
            elif self.use_privoxy:
                # Privoxy만 사용 (직접 연결)
                self.logger.info("Privoxy HTTP 프록시를 시작합니다...")
                self.privoxy_proxy = PrivoxyProxy(
                    http_port=self.http_port,
                    forward_socks_port=None
                )
                if not self.privoxy_proxy.start():
                    raise Exception("Privoxy 시작 실패")
                
                self.logger.info(f"✓ HTTP 프록시: http://127.0.0.1:{self.http_port}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"프록시 시작 실패: {e}")
            return False
    
    def start_spiderfoot(self, cli_mode=False, args=None):
        """SpiderFoot 시작"""
        try:
            # 환경 변수 설정
            env = os.environ.copy()
            
            if self.use_tor and self.use_privoxy:
                # HTTP 프록시 설정
                env['HTTP_PROXY'] = f'http://127.0.0.1:{self.http_port}'
                env['HTTPS_PROXY'] = f'http://127.0.0.1:{self.http_port}'
                env['http_proxy'] = f'http://127.0.0.1:{self.http_port}'
                env['https_proxy'] = f'http://127.0.0.1:{self.http_port}'
            elif self.use_tor:
                # SOCKS5 프록시 설정
                env['ALL_PROXY'] = f'socks5h://127.0.0.1:{self.socks_port}'
                env['all_proxy'] = f'socks5h://127.0.0.1:{self.socks_port}'
            elif self.use_privoxy:
                # HTTP 프록시 설정
                env['HTTP_PROXY'] = f'http://127.0.0.1:{self.http_port}'
                env['HTTPS_PROXY'] = f'http://127.0.0.1:{self.http_port}'
            
            if cli_mode:
                # CLI 모드
                self.logger.info("SpiderFoot CLI를 시작합니다...")
                cmd = [sys.executable, 'sfcli.py']
                if args:
                    cmd.extend(args)
            else:
                # Web UI 모드
                self.logger.info(f"SpiderFoot Web UI를 시작합니다 (포트: {self.sf_port})...")
                cmd = [
                    sys.executable, 'sf.py',
                    '-l', f'{self.sf_host}:{self.sf_port}'
                ]
            
            # SpiderFoot 실행
            self.sf_process = subprocess.Popen(
                cmd,
                env=env,
                cwd=SPIDERFOOT_ROOT
            )
            
            if not cli_mode:
                self.logger.info(f"✓ SpiderFoot Web UI: http://{self.sf_host}:{self.sf_port}")
                
                # 프록시 사용 안내
                if self.use_tor or self.use_privoxy:
                    self.logger.info("\n프록시 설정:")
                    if self.use_tor and self.use_privoxy:
                        self.logger.info(f"  HTTP/HTTPS: http://127.0.0.1:{self.http_port}")
                        self.logger.info(f"  SOCKS5: socks5h://127.0.0.1:{self.socks_port}")
                    elif self.use_tor:
                        self.logger.info(f"  SOCKS5: socks5h://127.0.0.1:{self.socks_port}")
                    else:
                        self.logger.info(f"  HTTP/HTTPS: http://127.0.0.1:{self.http_port}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"SpiderFoot 시작 실패: {e}")
            return False
    
    def wait(self):
        """SpiderFoot 프로세스가 종료될 때까지 대기"""
        if self.sf_process:
            try:
                self.sf_process.wait()
            except KeyboardInterrupt:
                self.logger.info("사용자가 중단했습니다.")
    
    def stop(self):
        """모든 서비스 중지"""
        # SpiderFoot 중지
        if self.sf_process:
            self.logger.info("SpiderFoot를 중지합니다...")
            self.sf_process.terminate()
            try:
                self.sf_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.sf_process.kill()
        
        # 프록시 중지
        if self.combined_proxy:
            self.logger.info("Tor + Privoxy를 중지합니다...")
            self.combined_proxy.stop()
        elif self.tor_proxy:
            self.logger.info("Tor를 중지합니다...")
            self.tor_proxy.stop()
        elif self.privoxy_proxy:
            self.logger.info("Privoxy를 중지합니다...")
            self.privoxy_proxy.stop()
        
        self.logger.info("모든 서비스가 중지되었습니다.")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='SpiderFoot를 프록시와 함께 실행',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예제:
  # Tor + Privoxy와 함께 실행 (기본값)
  %(prog)s
  
  # Tor만 사용
  %(prog)s --tor-only
  
  # 프록시 없이 실행
  %(prog)s --no-proxy
  
  # CLI 모드로 실행
  %(prog)s --cli -m example.com
        """
    )
    
    # 프록시 옵션
    proxy_group = parser.add_mutually_exclusive_group()
    proxy_group.add_argument('--tor-only', action='store_true',
                           help='Tor SOCKS5 프록시만 사용')
    proxy_group.add_argument('--privoxy-only', action='store_true',
                           help='Privoxy HTTP 프록시만 사용 (직접 연결)')
    proxy_group.add_argument('--no-proxy', action='store_true',
                           help='프록시 없이 실행')
    
    # 포트 설정
    parser.add_argument('--socks-port', type=int, default=9050,
                      help='Tor SOCKS5 포트 (기본값: 9050)')
    parser.add_argument('--http-port', type=int, default=8118,
                      help='Privoxy HTTP 포트 (기본값: 8118)')
    parser.add_argument('--sf-port', type=int, default=5001,
                      help='SpiderFoot 웹 포트 (기본값: 5001)')
    parser.add_argument('--sf-host', default='127.0.0.1',
                      help='SpiderFoot 호스트 (기본값: 127.0.0.1)')
    
    # SpiderFoot 모드
    parser.add_argument('--cli', action='store_true',
                      help='CLI 모드로 실행 (sfcli.py)')
    
    # CLI 모드 인자 (나머지 모든 인자)
    parser.add_argument('cli_args', nargs='*',
                      help='CLI 모드 인자들')
    
    args = parser.parse_args()
    
    # 프록시 설정 결정
    use_tor = True
    use_privoxy = True
    
    if args.no_proxy:
        use_tor = False
        use_privoxy = False
    elif args.tor_only:
        use_tor = True
        use_privoxy = False
    elif args.privoxy_only:
        use_tor = False
        use_privoxy = True
    
    # 런처 생성
    launcher = SpiderFootLauncher(
        use_tor=use_tor,
        use_privoxy=use_privoxy,
        socks_port=args.socks_port,
        http_port=args.http_port,
        sf_port=args.sf_port,
        sf_host=args.sf_host
    )
    
    # 프록시 시작
    if use_tor or use_privoxy:
        if not launcher.start_proxies():
            print("프록시 시작 실패!")
            sys.exit(1)
        
        # 프록시가 완전히 시작될 때까지 잠시 대기
        time.sleep(3)
    
    # SpiderFoot 시작
    if not launcher.start_spiderfoot(cli_mode=args.cli, args=args.cli_args):
        print("SpiderFoot 시작 실패!")
        launcher.stop()
        sys.exit(1)
    
    # 프로세스 대기
    try:
        launcher.wait()
    except KeyboardInterrupt:
        pass
    finally:
        launcher.stop()


if __name__ == '__main__':
    main()