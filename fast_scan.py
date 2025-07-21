#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Fast Scan Mode
Optimized settings for faster scans with reduced module cascading
"""

import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description='SpiderFoot Fast Scan Mode')
    parser.add_argument('target', help='Target domain/IP to scan')
    parser.add_argument('-p', '--port', default='5001', help='Port for SpiderFoot web UI (default: 5001)')
    parser.add_argument('-i', '--interface', default='127.0.0.1', help='Interface to listen on (default: 127.0.0.1)')
    parser.add_argument('-m', '--modules', help='Comma-separated list of modules to run')
    
    args = parser.parse_args()
    
    print("====================================")
    print("SpiderFoot Fast Scan Mode")
    print("====================================")
    print(f"Target: {args.target}")
    print("")
    
    # Base command
    cmd = [
        sys.executable, 'sf.py',
        '-l', f'{args.interface}:{args.port}',
        '-s', args.target
    ]
    
    # Add module selection if specified
    if args.modules:
        cmd.extend(['-m', args.modules])
    else:
        # Default fast scan modules (avoid cascading effects)
        fast_modules = [
            'sfp_dnsresolve',
            'sfp_portscan_tcp',
            'sfp_pageinfo',
            'sfp_sslcert',
            'sfp_webserver',
            'sfp_whatcms',
            'sfp_wappalyzer',
            'sfp_builtwith',
            'sfp_shodan',
            'sfp_hackertarget',
            'sfp_whois',
            'sfp_bgpview',
            'sfp_ripe'
        ]
        cmd.extend(['-m', ','.join(fast_modules)])
    
    # Fast scan options
    fast_options = [
        '-o', 'sfp_tldsearch:max_results=10',  # Limit similar domains
        '-o', 'sfp_tldsearch:_maxthreads=20',   # Reduce threads
        '-o', '_maxthreads=5',                  # Global thread limit
        '-o', '_fetchtimeout=10',               # Increase timeout
        '-o', 'sfp_spider:maxpages=20',         # Limit web spidering
        '-o', 'sfp_crossref:checkaffiliates=False',  # Disable affiliate checking
    ]
    cmd.extend(fast_options)
    
    print("Fast scan settings:")
    print("  - Limited similar domain discovery (max 10)")
    print("  - Reduced concurrent threads")
    print("  - Limited web spidering (max 20 pages)")
    print("  - Disabled affiliate checking")
    print("")
    print("Running modules:")
    if args.modules:
        print(f"  {args.modules}")
    else:
        print(f"  {', '.join(fast_modules)}")
    print("")
    
    # Start SpiderFoot
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nScan interrupted by user")
        sys.exit(0)

if __name__ == '__main__':
    main()