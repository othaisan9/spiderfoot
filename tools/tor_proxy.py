#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SpiderFoot Tor Proxy Tool

A Python-based Tor proxy manager for SpiderFoot that handles:
- Automatic Tor installation and configuration
- SOCKS5 proxy connection management
- Circuit rotation and IP address cycling
- Connection testing and validation
"""

import os
import sys
import time
import socket
import subprocess
import tempfile
import shutil
import requests
from pathlib import Path
from typing import Optional, Dict, Any
import logging
import signal
import atexit

try:
    import stem
    from stem import Signal
    from stem.control import Controller
    from stem.process import launch_tor_with_config
except ImportError:
    print("Installing required dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "stem", "PySocks"])
    import stem
    from stem import Signal
    from stem.control import Controller
    from stem.process import launch_tor_with_config

try:
    import socks
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "PySocks"])
    import socks


class TorProxy:
    """Tor proxy manager for SpiderFoot"""
    
    def __init__(self, 
                 socks_port: int = 9050,
                 control_port: int = 9051,
                 data_dir: Optional[str] = None,
                 log_level: str = "INFO"):
        """
        Initialize Tor proxy manager
        
        Args:
            socks_port: SOCKS5 proxy port (default: 9050)
            control_port: Tor control port (default: 9051)
            data_dir: Directory for Tor data (default: temp directory)
            log_level: Logging level (default: INFO)
        """
        self.socks_port = socks_port
        self.control_port = control_port
        self.data_dir = data_dir or tempfile.mkdtemp(prefix="tor_data_")
        self.tor_process = None
        self.controller = None
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Register cleanup
        atexit.register(self.stop)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        self.logger.info("Received termination signal, shutting down...")
        self.stop()
        sys.exit(0)
    
    def check_tor_installed(self) -> bool:
        """Check if Tor is installed on the system"""
        return shutil.which('tor') is not None
    
    def install_tor(self):
        """Attempt to install Tor based on the operating system"""
        system = sys.platform
        
        if system == "linux" or system == "linux2":
            # Try apt-get first (Debian/Ubuntu)
            if shutil.which('apt-get'):
                self.logger.info("Installing Tor via apt-get...")
                subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'tor'], check=True)
            # Try yum (CentOS/RHEL/Fedora)
            elif shutil.which('yum'):
                self.logger.info("Installing Tor via yum...")
                subprocess.run(['sudo', 'yum', 'install', '-y', 'tor'], check=True)
            # Try pacman (Arch)
            elif shutil.which('pacman'):
                self.logger.info("Installing Tor via pacman...")
                subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'tor'], check=True)
            else:
                raise Exception("Unable to install Tor. Please install manually.")
        
        elif system == "darwin":  # macOS
            if shutil.which('brew'):
                self.logger.info("Installing Tor via Homebrew...")
                subprocess.run(['brew', 'install', 'tor'], check=True)
            else:
                raise Exception("Homebrew not found. Please install Tor manually.")
        
        else:
            raise Exception(f"Unsupported platform: {system}. Please install Tor manually.")
    
    def start(self) -> bool:
        """Start the Tor proxy service"""
        try:
            # Check if Tor is already running on the specified port
            if self._is_tor_running():
                self.logger.info(f"Tor is already running on port {self.socks_port}")
                
                # Try to connect to existing Tor instance control port
                try:
                    self.controller = Controller.from_port(port=self.control_port)
                    self.controller.authenticate()
                    self.logger.info("Connected to existing Tor instance")
                except Exception as e:
                    self.logger.info(f"Could not connect to control port (this is OK): {e}")
                    self.controller = None  # Will work without control port
                
                # Test connection through SOCKS proxy
                if self.test_connection():
                    self.logger.info("Existing Tor proxy is working correctly")
                    return True
                else:
                    self.logger.error("Existing Tor proxy test failed")
                    return False
            
            # Check if Tor is installed
            if not self.check_tor_installed():
                self.logger.warning("Tor not found. Attempting to install...")
                self.install_tor()
            
            # Create data directory
            Path(self.data_dir).mkdir(parents=True, exist_ok=True)
            
            # Tor configuration
            config = {
                'SocksPort': str(self.socks_port),
                'ControlPort': str(self.control_port),
                'DataDirectory': self.data_dir,
                'ExitPolicy': 'reject *:*',  # Don't be an exit node
                'BandwidthRate': '1MB',
                'BandwidthBurst': '2MB',
                'MaxCircuitDirtiness': '600',  # Rotate circuit every 10 minutes
                'NewCircuitPeriod': '15',
                'CookieAuthentication': '1',
                'CookieAuthFileGroupReadable': '1',
            }
            
            self.logger.info(f"Starting Tor on SOCKS port {self.socks_port}...")
            
            # Launch Tor
            self.tor_process = launch_tor_with_config(
                config=config,
                take_ownership=True,
                completion_percent=100,
                timeout=90
            )
            
            # Connect to control port
            self.controller = Controller.from_port(port=self.control_port)
            self.controller.authenticate()
            
            self.logger.info("Tor started successfully")
            
            # Test connection
            if self.test_connection():
                self.logger.info("Tor proxy is working correctly")
                return True
            else:
                self.logger.error("Tor proxy test failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Tor: {e}")
            return False
    
    def _is_tor_running(self) -> bool:
        """Check if Tor is already running on the specified port"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('127.0.0.1', self.socks_port))
            sock.close()
            return result == 0
        except:
            return False
    
    def stop(self):
        """Stop the Tor proxy service"""
        try:
            if self.controller:
                self.controller.close()
                self.controller = None
            
            if self.tor_process:
                self.tor_process.terminate()
                self.tor_process.wait()
                self.tor_process = None
            
            # Clean up data directory
            if os.path.exists(self.data_dir) and self.data_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(self.data_dir, ignore_errors=True)
            
            self.logger.info("Tor stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping Tor: {e}")
    
    def get_current_ip(self) -> Optional[str]:
        """Get current external IP address through Tor"""
        try:
            # Configure session to use Tor
            session = self._get_tor_session()
            response = session.get('https://api.ipify.org?format=json', timeout=10)
            return response.json()['ip']
        except Exception as e:
            self.logger.error(f"Failed to get current IP: {e}")
            return None
    
    def rotate_identity(self) -> bool:
        """Request a new Tor identity (new IP address)"""
        try:
            if not self.controller:
                self.logger.warning("Controller not connected - cannot rotate identity without control port")
                return False
            
            # Get current IP
            old_ip = self.get_current_ip()
            self.logger.info(f"Current IP: {old_ip}")
            
            # Signal for new identity
            self.controller.signal(Signal.NEWNYM)
            
            # Wait for circuit to rebuild
            time.sleep(5)
            
            # Verify IP changed
            new_ip = self.get_current_ip()
            self.logger.info(f"New IP: {new_ip}")
            
            return old_ip != new_ip
            
        except Exception as e:
            self.logger.error(f"Failed to rotate identity: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test if Tor proxy is working"""
        try:
            # Test direct connection first
            direct_ip = requests.get('https://api.ipify.org?format=json', timeout=5).json()['ip']
            
            # Test through Tor
            tor_ip = self.get_current_ip()
            
            if tor_ip and direct_ip != tor_ip:
                self.logger.info(f"Direct IP: {direct_ip}, Tor IP: {tor_ip}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def _get_tor_session(self) -> requests.Session:
        """Create a requests session configured to use Tor"""
        session = requests.Session()
        session.proxies = {
            'http': f'socks5h://127.0.0.1:{self.socks_port}',
            'https': f'socks5h://127.0.0.1:{self.socks_port}'
        }
        return session
    
    def get_proxy_dict(self) -> Dict[str, str]:
        """Get proxy dictionary for use with requests"""
        return {
            'http': f'socks5h://127.0.0.1:{self.socks_port}',
            'https': f'socks5h://127.0.0.1:{self.socks_port}'
        }
    
    def configure_socket(self):
        """Configure the default socket to use Tor"""
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", self.socks_port)
        socket.socket = socks.socksocket
    
    def reset_socket(self):
        """Reset socket to default (no proxy)"""
        socket.socket = socket._socketobject if hasattr(socket, '_socketobject') else socket.socket


def main():
    """Example usage and CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SpiderFoot Tor Proxy Manager')
    parser.add_argument('--socks-port', type=int, default=9050, help='SOCKS5 port (default: 9050)')
    parser.add_argument('--control-port', type=int, default=9051, help='Control port (default: 9051)')
    parser.add_argument('--data-dir', type=str, help='Data directory (default: temp)')
    parser.add_argument('--test', action='store_true', help='Test mode: start, test, rotate, stop')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    # Create proxy instance
    proxy = TorProxy(
        socks_port=args.socks_port,
        control_port=args.control_port,
        data_dir=args.data_dir
    )
    
    if args.test:
        # Test mode
        print("Starting Tor proxy...")
        if proxy.start():
            print(f"✓ Tor proxy started on port {args.socks_port}")
            
            # Show current IP
            ip = proxy.get_current_ip()
            print(f"✓ Current Tor IP: {ip}")
            
            # Test rotation
            print("\nRotating identity...")
            if proxy.rotate_identity():
                print("✓ Identity rotated successfully")
            
            # Example usage
            print("\nExample usage in your code:")
            print(f"proxies = {proxy.get_proxy_dict()}")
            print("response = requests.get('https://example.com', proxies=proxies)")
            
            print("\nPress Ctrl+C to stop...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        else:
            print("✗ Failed to start Tor proxy")
    
    elif args.daemon:
        # Daemon mode
        print(f"Starting Tor proxy daemon on port {args.socks_port}...")
        if proxy.start():
            print(f"Tor proxy running. PID: {os.getpid()}")
            print(f"SOCKS5 proxy: socks5h://127.0.0.1:{args.socks_port}")
            print("Press Ctrl+C to stop...")
            
            try:
                while True:
                    time.sleep(60)
                    # Optionally rotate identity periodically
                    # proxy.rotate_identity()
            except KeyboardInterrupt:
                pass
        else:
            print("Failed to start Tor proxy")
            sys.exit(1)
    
    else:
        # Interactive mode
        if proxy.start():
            print(f"\nTor proxy started successfully!")
            print(f"SOCKS5 proxy: socks5h://127.0.0.1:{args.socks_port}")
            print(f"Current IP: {proxy.get_current_ip()}")
            
            while True:
                print("\nOptions:")
                print("1. Show current IP")
                print("2. Rotate identity (get new IP)")
                print("3. Test connection")
                print("4. Show proxy settings")
                print("5. Exit")
                
                choice = input("\nSelect option: ").strip()
                
                if choice == '1':
                    ip = proxy.get_current_ip()
                    print(f"Current IP: {ip}")
                
                elif choice == '2':
                    print("Rotating identity...")
                    if proxy.rotate_identity():
                        print("✓ Identity rotated successfully")
                    else:
                        print("✗ Failed to rotate identity")
                
                elif choice == '3':
                    if proxy.test_connection():
                        print("✓ Tor connection is working")
                    else:
                        print("✗ Tor connection test failed")
                
                elif choice == '4':
                    print(f"Proxy settings: {proxy.get_proxy_dict()}")
                
                elif choice == '5':
                    break
                
                else:
                    print("Invalid option")
            
            proxy.stop()
        else:
            print("Failed to start Tor proxy")
            sys.exit(1)


if __name__ == '__main__':
    main()