# -*- coding: utf-8 -*-
"""
SpiderFoot BE Tor Manager

Manages Tor integration for accessing .onion sites and anonymous scanning.
"""

import os
import sys
import time
import subprocess
import socket
from typing import Optional, Dict, Tuple
import logging


class TorManager:
    """Manages Tor service and SOCKS proxy configuration."""
    
    def __init__(self, project_dir: Optional[str] = None):
        """Initialize Tor manager.
        
        Args:
            project_dir: Project root directory (optional)
        """
        self.logger = logging.getLogger("spiderfoot.tor_manager")
        
        if project_dir is None:
            self.project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            self.project_dir = project_dir
            
        self.tools_dir = os.path.join(self.project_dir, "tools")
        self.tor_data_dir = os.path.join(self.tools_dir, "tor", "data")
        self.tor_config_file = os.path.join(self.tools_dir, "tor", "torrc")
        self.tor_pid_file = os.path.join(self.tools_dir, "tor", "tor.pid")
        
        # Default Tor SOCKS proxy settings
        self.socks_host = "127.0.0.1"
        self.socks_port = 9050
        self.control_port = 9051
        
        # Create directories if needed
        os.makedirs(self.tor_data_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.tor_config_file), exist_ok=True)
        
    def create_tor_config(self) -> None:
        """Create Tor configuration file."""
        config_content = f"""# SpiderFoot BE Tor Configuration
SocksPort {self.socks_port}
ControlPort {self.control_port}
DataDirectory {self.tor_data_dir}
PidFile {self.tor_pid_file}
Log notice file {os.path.join(self.tools_dir, 'tor', 'tor.log')}

# Security settings
CookieAuthentication 1
HashedControlPassword 16:872860B76453A77D60CA2BB8C1A7042072093276A3D701AD684053EC4C

# Performance settings
CircuitBuildTimeout 10
LearnCircuitBuildTimeout 0
MaxCircuitDirtiness 300
"""
        
        with open(self.tor_config_file, 'w') as f:
            f.write(config_content)
            
        self.logger.info(f"Created Tor config at {self.tor_config_file}")
    
    def is_tor_installed(self) -> bool:
        """Check if Tor is installed.
        
        Returns:
            bool: True if Tor is installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["tor", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def is_tor_running(self) -> bool:
        """Check if Tor is running by testing SOCKS connection.
        
        Returns:
            bool: True if Tor is running, False otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.socks_host, self.socks_port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def start_tor(self) -> Tuple[bool, str]:
        """Start Tor service.
        
        Returns:
            tuple: (success, message)
        """
        if not self.is_tor_installed():
            return False, "Tor is not installed. Run 'python install_tools.py --install tor' first."
        
        if self.is_tor_running():
            return True, "Tor is already running."
        
        # Create config if it doesn't exist
        if not os.path.exists(self.tor_config_file):
            self.create_tor_config()
        
        try:
            # Start Tor with our config
            cmd = ["tor", "-f", self.tor_config_file]
            
            self.logger.info(f"Starting Tor with command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for Tor to start
            for i in range(30):  # 30 second timeout
                if self.is_tor_running():
                    self.logger.info("Tor started successfully")
                    return True, f"Tor started on {self.socks_host}:{self.socks_port}"
                time.sleep(1)
            
            # Check if process failed
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                return False, f"Tor failed to start: {stderr}"
            
            return False, "Tor failed to start within 30 seconds"
            
        except Exception as e:
            return False, f"Error starting Tor: {str(e)}"
    
    def stop_tor(self) -> Tuple[bool, str]:
        """Stop Tor service.
        
        Returns:
            tuple: (success, message)
        """
        if not self.is_tor_running():
            return True, "Tor is not running."
        
        try:
            # Try to read PID file
            if os.path.exists(self.tor_pid_file):
                with open(self.tor_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    
                try:
                    os.kill(pid, 15)  # SIGTERM
                    time.sleep(2)
                    
                    # Check if still running
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, 9)  # SIGKILL if still running
                    except ProcessLookupError:
                        pass
                        
                except ProcessLookupError:
                    pass
                    
                # Remove PID file
                os.remove(self.tor_pid_file)
            
            # Fallback: killall tor
            subprocess.run(["killall", "tor"], capture_output=True)
            
            return True, "Tor stopped successfully"
            
        except Exception as e:
            return False, f"Error stopping Tor: {str(e)}"
    
    def restart_tor(self) -> Tuple[bool, str]:
        """Restart Tor service.
        
        Returns:
            tuple: (success, message)
        """
        self.stop_tor()
        time.sleep(2)
        return self.start_tor()
    
    def get_tor_config(self) -> Dict[str, str]:
        """Get Tor proxy configuration for SpiderFoot.
        
        Returns:
            dict: Configuration dictionary
        """
        return {
            '_socks1type': '5',
            '_socks2addr': self.socks_host,
            '_socks3port': str(self.socks_port),
            '_socks4user': '',
            '_socks5pwd': ''
        }
    
    def test_tor_connection(self) -> Tuple[bool, str]:
        """Test Tor connection by fetching check.torproject.org.
        
        Returns:
            tuple: (success, IP address or error message)
        """
        if not self.is_tor_running():
            return False, "Tor is not running"
        
        try:
            # Import here to avoid circular dependency
            import requests
            
            # Use Tor SOCKS proxy
            proxies = {
                'http': f'socks5h://{self.socks_host}:{self.socks_port}',
                'https': f'socks5h://{self.socks_host}:{self.socks_port}'
            }
            
            # Test connection
            response = requests.get(
                'https://check.torproject.org/api/ip',
                proxies=proxies,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('IsTor', False):
                    return True, f"Connected via Tor. Exit IP: {data.get('IP', 'Unknown')}"
                else:
                    return False, "Connected but not using Tor"
            else:
                return False, f"HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def create_onion_service(self, port: int = 5001) -> Tuple[bool, str]:
        """Create a hidden service for SpiderFoot.
        
        Args:
            port: Local port to expose as hidden service
            
        Returns:
            tuple: (success, onion address or error message)
        """
        # This would require additional Tor configuration
        # Implementation depends on specific requirements
        return False, "Onion service creation not implemented yet"


# Global instance for easy access
tor_manager = TorManager()