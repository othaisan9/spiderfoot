# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_tool_rustscan
# Purpose:      SpiderFoot plug-in for using RustScan for ultra-fast port scanning
#
# Author:      Your Name
#
# Created:     2025/01/24
# Copyright:   (c) Your Name 2025
# Licence:     MIT
# -------------------------------------------------------------------------------

import os.path
from subprocess import PIPE, Popen

from netaddr import IPNetwork

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_tool_rustscan(SpiderFootPlugin):

    meta = {
        'name': "Tool - RustScan",
        'summary': "Identify open ports using RustScan, a modern ultra-fast port scanner.",
        'flags': ["tool", "slow", "invasive"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        'toolDetails': {
            'name': "RustScan",
            'description': "RustScan is a modern take on the port scanner. Sleek & fast. "
            "All while providing extensive extendability to you.\n"
            "RustScan is a modern port scanner that can scan all 65k ports in 3 seconds. "
            "It automatically pipes results into Nmap for service detection.",
            'website': "https://github.com/RustScan/RustScan",
            'repository': "https://github.com/RustScan/RustScan"
        },
    }

    # Default options
    opts = {
        'rustscanpath': "/snap/bin/rustscan",
        'netblockscan': True,
        'netblockscanmax': 24,
        'ports': '-',  # '-' for all ports, or comma-separated like '80,443,8080'
        'ulimit': 5000,
        'batch_size': 4500,
        'timeout': 2000,
        'greppable': True,
        'top': ''  # empty means scan specified ports, or 'top100', 'top1000' etc
    }

    # Option descriptions
    optdescs = {
        'rustscanpath': "Path to the rustscan binary. Must be set.",
        'netblockscan': "Port scan all IPs within identified owned netblocks?",
        'netblockscanmax': "Maximum netblock/subnet size to scan IPs within (CIDR value, 24 = /24, 16 = /16, etc.)",
        'ports': "Ports to scan. Use '-' for all ports, or comma-separated list (e.g., '80,443,8080').",
        'ulimit': "Ulimit value to set for RustScan (file descriptor limit).",
        'batch_size': "The batch size for port scanning (ports per thread).",
        'timeout': "Timeout in milliseconds for port scanning.",
        'greppable': "Use greppable output format for easier parsing.",
        'top': "Scan top N ports. Options: top100, top1000 (leave empty to use 'ports' setting)."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Target Network"

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ['IP_ADDRESS', 'NETBLOCK_OWNER']

    # What events this module produces
    def producedEvents(self):
        return ["TCP_PORT_OPEN", "TCP_PORT_OPEN_BANNER"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if srcModuleName == "sfp_tool_rustscan":
            self.debug("Skipping event from myself.")
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        try:
            if eventName == "NETBLOCK_OWNER" and self.opts['netblockscan']:
                net = IPNetwork(eventData)
                if net.prefixlen < self.opts['netblockscanmax']:
                    self.debug(f"Skipping port scanning of {eventData}, too big.")
                    return

        except Exception as e:
            self.error(f"Strange netblock identified, unable to parse: {eventData} ({str(e)})")
            return

        # Don't look up stuff twice, check IP == IP here
        if eventData in self.results:
            self.debug(f"Skipping {eventData} as already scanned.")
            return

        # Might be a subnet within a subnet or IP within a subnet
        for addr in self.results:
            if IPNetwork(eventData) in IPNetwork(addr):
                self.debug(f"Skipping {eventData} as already within a scanned range.")
                return

        self.results[eventData] = True

        if not self.opts['rustscanpath']:
            self.error("You enabled sfp_tool_rustscan but did not set a path to the tool!")
            self.errorState = True
            return

        # Normalize path
        if self.opts['rustscanpath'].endswith('rustscan'):
            exe = self.opts['rustscanpath']
        elif self.opts['rustscanpath'].endswith('/'):
            exe = self.opts['rustscanpath'] + "rustscan"
        else:
            self.error("Could not recognize your rustscan path configuration.")
            self.errorState = True
            return

        # If tool is not found, abort
        if not os.path.isfile(exe):
            self.error(f"File does not exist: {exe}")
            self.errorState = True
            return

        # Sanitize domain name.
        if not self.sf.validIP(eventData) and not self.sf.validIpNetwork(eventData):
            self.error("Invalid input, refusing to run.")
            return

        try:
            # Build command
            cmd = [exe]
            
            # Add target
            cmd.extend(['-a', eventData])
            
            # Add ulimit
            cmd.extend(['-u', str(self.opts['ulimit'])])
            
            # Add batch size
            cmd.extend(['-b', str(self.opts['batch_size'])])
            
            # Add timeout
            cmd.extend(['-t', str(self.opts['timeout'])])
            
            # Add ports configuration
            if self.opts['top']:
                # Use top ports setting
                if self.opts['top'] == 'top100':
                    cmd.extend(['--top'])
                elif self.opts['top'] == 'top1000':
                    cmd.extend(['-p', '-'])  # This is RustScan's default for top 1000
            elif self.opts['ports'] != '-':
                # Use specific ports
                cmd.extend(['-p', self.opts['ports']])
            # If ports is '-', RustScan will scan all ports by default
            
            # Add greppable output format
            if self.opts['greppable']:
                cmd.append('--greppable')

            self.info(f"Running RustScan against {eventData} with command: {' '.join(cmd)}")
            
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate(input=None)
            
            if p.returncode == 0:
                content = stdout.decode('utf-8', errors='replace')
            else:
                self.error(f"Unable to run RustScan: {stderr.decode('utf-8', errors='replace')}")
                return

        except Exception as e:
            self.error(f"Unable to run RustScan: {e}")
            return

        if not content:
            self.debug("No content from RustScan to parse.")
            return

        # Parse greppable output
        if eventName == "IP_ADDRESS":
            self.parseRustScanOutput(content, event, eventData)

        if eventName == "NETBLOCK_OWNER":
            # For netblocks, RustScan might scan multiple IPs
            # We need to parse each IP's results separately
            self.parseRustScanOutput(content, event)

    def parseRustScanOutput(self, content, srcEvent, singleIp=None):
        """Parse RustScan greppable output and generate events"""
        
        # RustScan greppable format: "IP -> [port1,port2,port3]"
        for line in content.split('\n'):
            line = line.strip()
            if not line or '->' not in line:
                continue
                
            try:
                # Split IP and ports
                ip_part, ports_part = line.split(' -> ')
                ip = ip_part.strip()
                
                # Extract ports from brackets
                if '[' in ports_part and ']' in ports_part:
                    ports_str = ports_part.strip('[]')
                    if not ports_str:
                        continue
                    
                    # Split comma-separated ports
                    ports = [p.strip() for p in ports_str.split(',') if p.strip()]
                    
                    # Generate IP_ADDRESS event if we're scanning a netblock
                    if singleIp is None and ip != srcEvent.data:
                        ipevent = SpiderFootEvent("IP_ADDRESS", ip, self.__name__, srcEvent)
                        self.notifyListeners(ipevent)
                        evt_parent = ipevent
                    else:
                        evt_parent = srcEvent
                    
                    # Generate TCP_PORT_OPEN events
                    for port in ports:
                        if port.isdigit():
                            peer = f"{ip}:{port}"
                            self.info(f"Found open port: {peer}")
                            evt = SpiderFootEvent("TCP_PORT_OPEN", peer, self.__name__, evt_parent)
                            self.notifyListeners(evt)
                            
            except Exception as e:
                self.error(f"Error parsing RustScan output line: {line} ({e})")
                continue

# End of sfp_tool_rustscan class