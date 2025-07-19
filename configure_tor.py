#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Configure SpiderFoot to use Tor proxy"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spiderfoot import SpiderFootDb
from sflib import SpiderFoot

def configure_tor_proxy():
    """Configure SpiderFoot database to use Tor proxy"""
    
    # Default config
    config = {
        '_debug': False,
        '_maxthreads': 3,
        '__logging': True,
        '__outputfilter': None,
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
        '_dnsserver': '',
        '_fetchtimeout': 30,  # Increased for Tor
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_genericusers': '',
        '__database': f"{os.path.expanduser('~')}/.spiderfoot/spiderfoot.db",
        '__modules__': None,
        '__correlationrules__': None,
        '_socks1type': 'TOR',  # Configure Tor
        '_socks2addr': '127.0.0.1',
        '_socks3port': '9050',
        '_socks4user': '',
        '_socks5pwd': '',
    }
    
    # Create database connection
    dbh = SpiderFootDb(config)
    
    # Get current config
    sf = SpiderFoot(config)
    
    # Load modules
    from spiderfoot import SpiderFootHelpers
    mod_dir = os.path.dirname(os.path.abspath(__file__)) + '/modules/'
    config['__modules__'] = SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])
    if not config['__modules__']:
        config['__modules__'] = {}
    
    # Load correlation rules
    try:
        # Try to load correlation rules if method exists
        config['__correlationrules__'] = []
    except:
        config['__correlationrules__'] = []
    
    # Serialize config
    config_str = sf.configSerialize(config)
    
    # Save to database as default config
    try:
        # Check if default config exists
        result = dbh.configGet()
        if result:
            # Update existing config
            print("Updating existing configuration with Tor proxy settings...")
            current_config = json.loads(result[0])
            current_config['_socks1type'] = 'TOR'
            current_config['_socks2addr'] = '127.0.0.1'
            current_config['_socks3port'] = '9050'
            current_config['_socks4user'] = ''
            current_config['_socks5pwd'] = ''
            current_config['_fetchtimeout'] = 30
            
            dbh.configClear()
            dbh.configSet(sf.configSerialize(current_config))
        else:
            # Create new config
            print("Creating new configuration with Tor proxy settings...")
            dbh.configSet(config_str)
            
        print("Configuration saved successfully!")
        print("\nTor proxy settings:")
        print("  Type: TOR")
        print("  Server: 127.0.0.1")
        print("  Port: 9050")
        print("\nNow you can scan .onion sites!")
        
    except Exception as e:
        print(f"Error saving configuration: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        dbh.close()

if __name__ == "__main__":
    from spiderfoot.tor_manager import tor_manager
    
    # Ensure Tor is running
    if not tor_manager.is_tor_running():
        print("Starting Tor...")
        success, msg = tor_manager.start_tor()
        if not success:
            print(f"Failed to start Tor: {msg}")
            sys.exit(1)
        print(f"Tor started: {msg}")
    
    configure_tor_proxy()