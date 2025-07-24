#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SpiderFoot Privoxy HTTP Proxy Manager

Provides HTTP proxy functionality by running Privoxy, which can:
- Convert SOCKS5 (Tor) to HTTP proxy
- Filter and modify HTTP traffic
- Block ads and tracking
- Add custom headers
"""

import os
import sys
import time
import subprocess
import tempfile
import shutil
import requests
import signal
import atexit
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging
import socket
import threading


class PrivoxyProxy:
    """Privoxy HTTP proxy manager for SpiderFoot"""
    
    def __init__(self,
                 http_port: int = 8118,
                 forward_socks_port: Optional[int] = 9050,
                 config_dir: Optional[str] = None,
                 log_level: str = "INFO",
                 use_system_config: bool = False):
        """
        Initialize Privoxy proxy manager
        
        Args:
            http_port: HTTP proxy port (default: 8118)
            forward_socks_port: Forward to SOCKS5 port, None for direct (default: 9050 for Tor)
            config_dir: Directory for Privoxy config (default: temp directory)
            log_level: Logging level (default: INFO)
            use_system_config: Use system Privoxy config files if available (default: False)
        """
        self.http_port = http_port
        self.forward_socks_port = forward_socks_port
        self.use_system_config = use_system_config
        
        # Use a directory in the user's home instead of /tmp
        if config_dir:
            self.config_dir = config_dir
        else:
            # Create config directory in user's home
            home_dir = os.path.expanduser("~")
            privoxy_dir = os.path.join(home_dir, ".spiderfoot", "privoxy")
            os.makedirs(privoxy_dir, exist_ok=True)
            self.config_dir = tempfile.mkdtemp(prefix="config_", dir=privoxy_dir)
        
        self.privoxy_process = None
        self.config_file = None
        
        # Path to bundled Privoxy files
        self.bundle_dir = os.path.join(os.path.dirname(__file__), 'privoxy')
        
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
    
    def check_privoxy_installed(self) -> bool:
        """Check if Privoxy is installed on the system"""
        return shutil.which('privoxy') is not None
    
    def install_privoxy(self):
        """Attempt to install Privoxy based on the operating system"""
        system = sys.platform
        
        if system == "linux" or system == "linux2":
            # Try apt-get first (Debian/Ubuntu)
            if shutil.which('apt-get'):
                self.logger.info("Installing Privoxy via apt-get...")
                subprocess.run(['sudo', 'apt-get', 'update'], check=True)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'privoxy'], check=True)
            # Try yum (CentOS/RHEL/Fedora)
            elif shutil.which('yum'):
                self.logger.info("Installing Privoxy via yum...")
                subprocess.run(['sudo', 'yum', 'install', '-y', 'privoxy'], check=True)
            # Try pacman (Arch)
            elif shutil.which('pacman'):
                self.logger.info("Installing Privoxy via pacman...")
                subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'privoxy'], check=True)
            else:
                raise Exception("Unable to install Privoxy. Please install manually.")
        
        elif system == "darwin":  # macOS
            if shutil.which('brew'):
                self.logger.info("Installing Privoxy via Homebrew...")
                subprocess.run(['brew', 'install', 'privoxy'], check=True)
            else:
                raise Exception("Homebrew not found. Please install Privoxy manually.")
        
        else:
            raise Exception(f"Unsupported platform: {system}. Please install Privoxy manually.")
    
    def _is_port_open(self, port: int, host: str = '127.0.0.1') -> bool:
        """Check if a port is open"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _wait_for_port(self, port: int, timeout: int = 30) -> bool:
        """Wait for a port to become available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._is_port_open(port):
                return True
            time.sleep(0.5)
        return False
    
    def _get_bundled_file_path(self, filename: str) -> str:
        """Get path to bundled Privoxy file"""
        # Get the directory where this module is located
        module_dir = os.path.dirname(os.path.abspath(__file__))
        bundled_path = os.path.join(module_dir, 'privoxy', filename)
        
        # Check if bundled file exists
        if os.path.exists(bundled_path):
            return bundled_path
        
        # Fallback to system file if available
        system_path = os.path.join('/etc/privoxy', filename)
        if os.path.exists(system_path):
            self.logger.info(f"Using system file: {system_path}")
            return system_path
        
        # Return bundled path anyway (will cause error if missing)
        return bundled_path
    
    def _generate_config(self) -> str:
        """Generate Privoxy configuration"""
        config_lines = [
            f"# SpiderFoot Privoxy Configuration",
            f"# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"# Listen on localhost only",
            f"listen-address  127.0.0.1:{self.http_port}",
            "",
            "# Enable connection sharing (keep-alive)",
            "keep-alive-timeout 300",
            "socket-timeout 300",
            "",
            "# Buffer sizes",
            "buffer-limit 4096",
            "",
            "# Forwarding",
        ]
        
        if self.forward_socks_port:
            # Forward through SOCKS5 (Tor)
            config_lines.extend([
                f"# Forward all traffic through Tor SOCKS5",
                f"forward-socks5t / 127.0.0.1:{self.forward_socks_port} .",
                "",
                "# Don't forward local addresses through Tor",
                "forward 192.168.*.*/ .",
                "forward 10.*.*.*/ .",
                "forward 127.*.*.*/ .",
                "forward localhost/ .",
            ])
        else:
            # Direct connection
            config_lines.append("# Direct connection (no forwarding)")
        
        config_lines.extend([
            "",
            "# Privacy settings",
            "hostname privoxy.spiderfoot",
            "",
            "# Enable Privoxy",
            "toggle 1",
            "",
            "# Accept intercepted requests",
            "accept-intercepted-requests 1",
            "",
            "# Allow all clients from localhost",
            "permit-access 127.0.0.1",
            "",
        ])
        
        # Add filter and action files based on configuration
        if self.use_system_config and os.path.exists('/etc/privoxy/default.filter'):
            # Use system files if requested and available
            config_lines.extend([
                "# Filter settings (using system files)",
                "filterfile /etc/privoxy/default.filter",
                f"filterfile {os.path.join(self.config_dir, 'user.filter')}",
                "",
                "# Action files (using system files)",
                "actionsfile /etc/privoxy/default.action",
                "actionsfile /etc/privoxy/match-all.action",
                f"actionsfile {os.path.join(self.config_dir, 'user.action')}",
            ])
        else:
            # Use bundled minimal files or no files at all
            if os.path.exists(self.bundle_dir):
                # Copy bundled files to config directory
                config_lines.extend([
                    "# Filter settings (using bundled minimal files)",
                    f"filterfile {os.path.join(self.config_dir, 'minimal.filter')}",
                    f"filterfile {os.path.join(self.config_dir, 'user.filter')}",
                    "",
                    "# Action files (using bundled minimal files)",
                    f"actionsfile {os.path.join(self.config_dir, 'minimal.action')}",
                    f"actionsfile {os.path.join(self.config_dir, 'user.action')}",
                ])
            else:
                # No filter/action files - pure proxy mode
                # Note: Privoxy requires at least one action file to function
                # We'll create a minimal one on the fly
                config_lines.extend([
                    "# Minimal configuration - pure HTTP proxy mode",
                    "# Creating minimal action file for basic operation",
                    f"actionsfile {os.path.join(self.config_dir, 'minimal.action')}",
                ])
        
        config_lines.extend([
            "",
            "# Compression",
            "compression-level 0",
            "",
            "# Logging",
            "debug 1",  # Log errors only
            f"logfile {os.path.join(self.config_dir, 'privoxy.log')}",
        ])
        
        return '\n'.join(config_lines)
    
    def _create_empty_files(self):
        """Create empty action and filter files"""
        # Create empty user.action file
        action_file = os.path.join(self.config_dir, 'user.action')
        with open(action_file, 'w') as f:
            f.write("# User actions file\n")
            f.write("# Add custom actions here\n")
        
        # Create empty user.filter file
        filter_file = os.path.join(self.config_dir, 'user.filter')
        with open(filter_file, 'w') as f:
            f.write("# User filter file\n")
            f.write("# Add custom filters here\n")
        
        # Create minimal.action if it doesn't exist (fallback)
        minimal_action = os.path.join(self.config_dir, 'minimal.action')
        if not os.path.exists(minimal_action):
            with open(minimal_action, 'w') as f:
                f.write("# Minimal action file\n")
                f.write("# This allows Privoxy to function as a basic HTTP proxy\n")
                f.write("{}\n")  # Empty action block
                f.write("/\n")   # Match all URLs
    
    def start(self) -> bool:
        """Start the Privoxy HTTP proxy service"""
        try:
            # First check if the desired port is already in use (system Privoxy)
            if self._is_port_open(self.http_port):
                self.logger.info(f"Port {self.http_port} is already in use. Testing existing proxy...")
                
                # Test if it's a working proxy
                if self.test_connection():
                    self.logger.info(f"Existing proxy on port {self.http_port} is working correctly.")
                    self.logger.info("Using existing proxy instead of starting a new instance.")
                    return True
                else:
                    self.logger.warning(f"Port {self.http_port} is in use but proxy test failed.")
                    self.logger.info("The existing service might not be configured as a proxy.")
                    
                    # If it's the default port, suggest using a different port
                    if self.http_port == 8118:
                        self.logger.info("Consider using a different port (e.g., 8119) to avoid conflicts.")
                        return False
                    else:
                        self.logger.error(f"Cannot start Privoxy on port {self.http_port} - already in use.")
                        return False
            
            # Check if Privoxy is installed
            if not self.check_privoxy_installed():
                self.logger.warning("Privoxy not found. Attempting to install...")
                self.install_privoxy()
            
            # Check if forwarding port is available (if using Tor)
            if self.forward_socks_port and not self._is_port_open(self.forward_socks_port):
                self.logger.warning(f"SOCKS5 port {self.forward_socks_port} not available. "
                                  "Starting without forwarding (direct connection).")
                self.forward_socks_port = None
            
            # Create config directory with proper permissions
            Path(self.config_dir).mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Copy bundled files if they exist and we're not using system config
            if not self.use_system_config and os.path.exists(self.bundle_dir):
                # Copy minimal action file
                minimal_action = os.path.join(self.bundle_dir, 'minimal.action')
                if os.path.exists(minimal_action):
                    shutil.copy2(minimal_action, os.path.join(self.config_dir, 'minimal.action'))
                    self.logger.info("Copied bundled minimal.action file")
                
                # Copy minimal filter file
                minimal_filter = os.path.join(self.bundle_dir, 'minimal.filter')
                if os.path.exists(minimal_filter):
                    shutil.copy2(minimal_filter, os.path.join(self.config_dir, 'minimal.filter'))
                    self.logger.info("Copied bundled minimal.filter file")
            
            # Generate configuration
            config_content = self._generate_config()
            self.config_file = os.path.join(self.config_dir, 'config')
            
            with open(self.config_file, 'w') as f:
                f.write(config_content)
            
            # Set proper permissions on config file
            os.chmod(self.config_file, 0o644)
            
            # Create empty action and filter files
            self._create_empty_files()
            
            # Set permissions on action and filter files
            action_file = os.path.join(self.config_dir, 'user.action')
            filter_file = os.path.join(self.config_dir, 'user.filter')
            if os.path.exists(action_file):
                os.chmod(action_file, 0o644)
            if os.path.exists(filter_file):
                os.chmod(filter_file, 0o644)
            
            self.logger.info(f"Starting Privoxy on HTTP port {self.http_port}...")
            
            # Start Privoxy
            cmd = ['privoxy', '--no-daemon', self.config_file]
            self.privoxy_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Wait for Privoxy to start
            if self._wait_for_port(self.http_port):
                self.logger.info("Privoxy started successfully")
                
                # Test connection
                if self.test_connection():
                    self.logger.info("Privoxy proxy is working correctly")
                    return True
                else:
                    self.logger.error("Privoxy proxy test failed")
                    return False
            else:
                self.logger.error("Privoxy failed to start (port not available)")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Privoxy: {e}")
            return False
    
    def stop(self):
        """Stop the Privoxy proxy service"""
        try:
            if self.privoxy_process:
                self.privoxy_process.terminate()
                try:
                    self.privoxy_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.privoxy_process.kill()
                self.privoxy_process = None
            
            # Clean up config directory
            if os.path.exists(self.config_dir) and "config_" in os.path.basename(self.config_dir):
                shutil.rmtree(self.config_dir, ignore_errors=True)
            
            self.logger.info("Privoxy stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping Privoxy: {e}")
    
    def test_connection(self) -> bool:
        """Test if HTTP proxy is working"""
        try:
            # Configure session to use proxy
            proxies = self.get_proxy_dict()
            
            # Test request
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                ip_data = response.json()
                self.logger.info(f"Proxy test successful. IP: {ip_data.get('origin', 'unknown')}")
                return True
            elif response.status_code == 503:
                # System Privoxy might be configured to not accept proxy requests
                self.logger.warning("Proxy returned 503 - it may not be configured to accept requests")
                return False
            else:
                self.logger.warning(f"Proxy test failed with status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_proxy_dict(self) -> Dict[str, str]:
        """Get proxy dictionary for use with requests"""
        proxy_url = f'http://127.0.0.1:{self.http_port}'
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def get_proxy_url(self) -> str:
        """Get proxy URL string"""
        return f'http://127.0.0.1:{self.http_port}'
    
    def add_filter_rule(self, rule: str):
        """Add a filter rule to Privoxy"""
        filter_file = os.path.join(self.config_dir, 'user.filter')
        with open(filter_file, 'a') as f:
            f.write(f"\n{rule}\n")
        
        # Reload Privoxy config
        if self.privoxy_process:
            self.privoxy_process.send_signal(signal.SIGHUP)
    
    def add_action_rule(self, rule: str):
        """Add an action rule to Privoxy"""
        action_file = os.path.join(self.config_dir, 'user.action')
        with open(action_file, 'a') as f:
            f.write(f"\n{rule}\n")
        
        # Reload Privoxy config
        if self.privoxy_process:
            self.privoxy_process.send_signal(signal.SIGHUP)


class TorHttpProxy:
    """Combined Tor + Privoxy HTTP proxy manager"""
    
    def __init__(self,
                 http_port: int = 8118,
                 socks_port: int = 9050,
                 tor_control_port: int = 9051,
                 data_dir: Optional[str] = None,
                 log_level: str = "INFO",
                 use_system_config: bool = False):
        """
        Initialize combined Tor + Privoxy proxy
        
        Args:
            http_port: HTTP proxy port for Privoxy (default: 8118)
            socks_port: SOCKS5 port for Tor (default: 9050)
            tor_control_port: Tor control port (default: 9051)
            data_dir: Directory for data (default: temp directory)
            log_level: Logging level (default: INFO)
            use_system_config: Use system Privoxy config files if available (default: False)
        """
        # Import tor_proxy module
        from tools.tor_proxy import TorProxy
        
        self.tor_proxy = TorProxy(
            socks_port=socks_port,
            control_port=tor_control_port,
            data_dir=data_dir,
            log_level=log_level
        )
        
        self.privoxy_proxy = PrivoxyProxy(
            http_port=http_port,
            forward_socks_port=socks_port,
            log_level=log_level,
            use_system_config=use_system_config
        )
        
        self.logger = logging.getLogger(__name__)
    
    def start(self) -> bool:
        """Start both Tor and Privoxy"""
        try:
            # Start Tor first
            self.logger.info("Starting Tor...")
            if not self.tor_proxy.start():
                self.logger.error("Failed to start Tor")
                return False
            
            # Then start Privoxy
            self.logger.info("Starting Privoxy...")
            if not self.privoxy_proxy.start():
                self.logger.error("Failed to start Privoxy")
                self.tor_proxy.stop()
                return False
            
            self.logger.info("Tor + Privoxy HTTP proxy started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start Tor + Privoxy: {e}")
            return False
    
    def stop(self):
        """Stop both proxies"""
        self.privoxy_proxy.stop()
        self.tor_proxy.stop()
    
    def rotate_identity(self) -> bool:
        """Rotate Tor identity"""
        return self.tor_proxy.rotate_identity()
    
    def get_proxy_dict(self) -> Dict[str, str]:
        """Get HTTP proxy dictionary"""
        return self.privoxy_proxy.get_proxy_dict()
    
    def get_current_ip(self) -> Optional[str]:
        """Get current external IP through the proxy chain"""
        try:
            proxies = self.get_proxy_dict()
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=10
            )
            return response.json().get('origin', '').split(',')[0].strip()
        except Exception as e:
            self.logger.error(f"Failed to get current IP: {e}")
            return None


def main():
    """Example usage and CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SpiderFoot Privoxy HTTP Proxy Manager')
    parser.add_argument('--http-port', type=int, default=8118, help='HTTP proxy port (default: 8118)')
    parser.add_argument('--socks-port', type=int, default=9050, help='SOCKS5 port to forward to (default: 9050)')
    parser.add_argument('--no-tor', action='store_true', help='Run without Tor forwarding')
    parser.add_argument('--with-tor', action='store_true', help='Run with integrated Tor')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--use-system-config', action='store_true', help='Use system Privoxy config files from /etc/privoxy')
    
    args = parser.parse_args()
    
    if args.with_tor:
        # Combined Tor + Privoxy mode
        print("Starting Tor + Privoxy HTTP proxy...")
        proxy = TorHttpProxy(
            http_port=args.http_port,
            socks_port=args.socks_port,
            use_system_config=args.use_system_config
        )
        
        if proxy.start():
            print(f"✓ HTTP proxy ready at http://127.0.0.1:{args.http_port}")
            print(f"✓ Current IP: {proxy.get_current_ip()}")
            
            if args.daemon:
                print("Running in daemon mode. Press Ctrl+C to stop...")
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    pass
            else:
                # Interactive mode
                while True:
                    print("\nOptions:")
                    print("1. Show current IP")
                    print("2. Rotate Tor identity")
                    print("3. Test proxy")
                    print("4. Exit")
                    
                    choice = input("\nSelect option: ").strip()
                    
                    if choice == '1':
                        ip = proxy.get_current_ip()
                        print(f"Current IP: {ip}")
                    
                    elif choice == '2':
                        print("Rotating identity...")
                        if proxy.rotate_identity():
                            print(f"✓ New IP: {proxy.get_current_ip()}")
                        else:
                            print("✗ Failed to rotate identity")
                    
                    elif choice == '3':
                        proxies = proxy.get_proxy_dict()
                        try:
                            resp = requests.get('http://httpbin.org/headers', proxies=proxies, timeout=10)
                            print("✓ Proxy test successful")
                            print(f"Headers: {resp.json()}")
                        except Exception as e:
                            print(f"✗ Proxy test failed: {e}")
                    
                    elif choice == '4':
                        break
            
            proxy.stop()
        else:
            print("✗ Failed to start proxy")
            sys.exit(1)
    
    else:
        # Privoxy only mode
        proxy = PrivoxyProxy(
            http_port=args.http_port,
            forward_socks_port=None if args.no_tor else args.socks_port,
            use_system_config=args.use_system_config
        )
        
        if args.test:
            print("Starting Privoxy HTTP proxy...")
            if proxy.start():
                print(f"✓ HTTP proxy started on port {args.http_port}")
                
                # Test proxy
                print("\nTesting proxy...")
                if proxy.test_connection():
                    print("✓ Proxy is working")
                
                # Show usage
                print("\nExample usage:")
                print(f"export http_proxy=http://127.0.0.1:{args.http_port}")
                print(f"export https_proxy=http://127.0.0.1:{args.http_port}")
                print("curl http://httpbin.org/ip")
                
                print("\nOr in Python:")
                print(f"proxies = {proxy.get_proxy_dict()}")
                print("requests.get('http://example.com', proxies=proxies)")
                
                print("\nPress Ctrl+C to stop...")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            else:
                print("✗ Failed to start proxy")
        
        elif args.daemon:
            print(f"Starting Privoxy daemon on port {args.http_port}...")
            if proxy.start():
                print(f"HTTP proxy running at http://127.0.0.1:{args.http_port}")
                print("Press Ctrl+C to stop...")
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    pass
            else:
                print("Failed to start proxy")
                sys.exit(1)
        
        else:
            # Normal start
            if proxy.start():
                print(f"\nPrivoxy HTTP proxy started!")
                print(f"HTTP proxy: http://127.0.0.1:{args.http_port}")
                
                if not args.no_tor:
                    print("Forwarding through Tor SOCKS5")
                else:
                    print("Direct connection (no Tor)")
                
                print("\nPress Enter to stop...")
                input()
                
                proxy.stop()
            else:
                print("Failed to start proxy")
                sys.exit(1)


if __name__ == '__main__':
    main()