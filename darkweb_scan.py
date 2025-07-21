#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Darkweb Scanner - Tor Enabled
Starts SpiderFoot with Tor proxy pre-configured for darkweb scanning
"""

import os
import sys
import time
import socket
import subprocess
import argparse

def check_tor_installed():
    """Check if Tor is installed on the system."""
    try:
        result = subprocess.run(['tor', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def is_tor_running(host='127.0.0.1', port=9050):
    """Check if Tor is running by testing SOCKS connection."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def start_tor():
    """Start Tor service."""
    print("Starting Tor service...")
    try:
        # Try systemctl first (systemd)
        result = subprocess.run(['sudo', 'systemctl', 'start', 'tor'], capture_output=True)
        if result.returncode == 0:
            return True
        
        # Try service command (SysV init)
        result = subprocess.run(['sudo', 'service', 'tor', 'start'], capture_output=True)
        if result.returncode == 0:
            return True
            
        # Try starting tor directly
        subprocess.Popen(['tor'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Failed to start Tor: {e}")
        return False

def test_tor_connection():
    """Test Tor connection by checking IP through Tor."""
    try:
        import requests
        
        proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        
        print("Testing Tor connection...")
        response = requests.get('https://check.torproject.org/api/ip', proxies=proxies, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('IsTor', False):
                print(f"✓ Connected via Tor. Exit IP: {data.get('IP', 'Unknown')}")
                return True
            else:
                print("✗ Connected but not using Tor")
                return False
    except Exception as e:
        print(f"✗ Tor connection test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='SpiderFoot Darkweb Scanner - Tor Enabled')
    parser.add_argument('-p', '--port', default='5001', help='Port for SpiderFoot web UI (default: 5001)')
    parser.add_argument('-i', '--interface', default='0.0.0.0', help='Interface to listen on (default: 0.0.0.0)')
    parser.add_argument('--tor-port', default='9050', help='Tor SOCKS port (default: 9050)')
    parser.add_argument('--no-test', action='store_true', help='Skip Tor connection test')
    
    args = parser.parse_args()
    
    print("========================================")
    print("SpiderFoot Darkweb Scanner (Tor Enabled)")
    print("========================================")
    
    # Check if Tor is installed
    if not check_tor_installed():
        print("Error: Tor is not installed!")
        print("Please install Tor first:")
        print("  Ubuntu/Debian: sudo apt-get install tor")
        print("  MacOS: brew install tor")
        sys.exit(1)
    
    # Check if Tor is running
    if not is_tor_running(port=int(args.tor_port)):
        if not start_tor():
            print("Error: Failed to start Tor service")
            print("Please start Tor manually and try again")
            sys.exit(1)
        
        # Wait for Tor to start
        print("Waiting for Tor to start...")
        for i in range(30):
            if is_tor_running(port=int(args.tor_port)):
                break
            time.sleep(1)
        else:
            print("Error: Tor failed to start within 30 seconds")
            sys.exit(1)
    
    print(f"✓ Tor is running on port {args.tor_port}")
    
    # Test Tor connection (optional)
    if not args.no_test:
        try:
            test_tor_connection()
        except ImportError:
            print("Note: Install 'requests[socks]' for Tor connection testing")
    
    # Prepare SpiderFoot command
    sf_cmd = [
        sys.executable, 'sf.py',
        '-l', f'{args.interface}:{args.port}',
        '-o', '_socks1type=5',
        '-o', '_socks2addr=127.0.0.1',
        '-o', f'_socks3port={args.tor_port}',
        '-o', '_socks4user=',
        '-o', '_socks5pwd='
    ]
    
    print("")
    print(f"Starting SpiderFoot with Tor proxy enabled...")
    print(f"Web UI will be available at: http://{args.interface}:{args.port}")
    print("")
    print("Default Tor proxy settings:")
    print(f"  - SOCKS Type: 5 (SOCKS5)")
    print(f"  - SOCKS Server: 127.0.0.1")
    print(f"  - SOCKS Port: {args.tor_port}")
    print("")
    print("Recommended modules for darkweb scanning:")
    print("  - ahmia (Tor search engine)")
    print("  - torexits (Check for Tor exit nodes)")
    print("  - torch (Tor search engine)")
    print("  - onionsearchengine")
    print("  - bitcoin, bitcoinabuse (Cryptocurrency tracking)")
    print("")
    print("Press Ctrl+C to stop SpiderFoot")
    print("")
    
    # Start SpiderFoot
    try:
        subprocess.run(sf_cmd)
    except KeyboardInterrupt:
        print("\nShutting down SpiderFoot...")
        sys.exit(0)

if __name__ == '__main__':
    main()