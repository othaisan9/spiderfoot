#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot BE Tool Installation Manager

Manages the installation of third-party security tools used by SpiderFoot modules.
Supports various package managers and installation methods.
"""

import os
import sys
import logging
import subprocess
import platform
import shutil
import argparse
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class InstallMethod(Enum):
    """Supported installation methods."""
    APT = "apt"
    YUM = "yum"
    BREW = "brew"
    SNAP = "snap"
    PIP = "pip"
    NPM = "npm"
    GO = "go"
    GIT = "git"
    WGET = "wget"
    CURL = "curl"
    SCRIPT = "script"
    MANUAL = "manual"


@dataclass
class ToolInfo:
    """Information about a third-party tool."""
    name: str
    description: str
    version: str
    install_methods: Dict[str, List[str]]  # OS -> [commands]
    verify_command: str
    required_by: List[str]  # SpiderFoot modules that require this
    website: str
    repository: str
    dependencies: List[str] = None
    post_install: List[str] = None


class ToolInstaller:
    """Manages installation of third-party tools for SpiderFoot."""
    
    def __init__(self, verbose: bool = False, project_dir: str = None):
        """Initialize the tool installer."""
        self.verbose = verbose
        self.logger = self._setup_logging()
        self.os_type = self._detect_os()
        self.package_manager = self._detect_package_manager()
        
        # Set up log file
        self.log_file = None
        
        # Set up project-local installation directories
        if project_dir is None:
            self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.project_dir = project_dir
            
        self.tools_dir = os.path.join(self.project_dir, "tools")
        self.bin_dir = os.path.join(self.tools_dir, "bin")
        self.lib_dir = os.path.join(self.tools_dir, "lib")
        self.node_modules_dir = os.path.join(self.tools_dir, "node_modules")
        self.python_packages_dir = os.path.join(self.tools_dir, "python_packages")
        
        # Create directories if they don't exist
        for dir_path in [self.tools_dir, self.bin_dir, self.lib_dir, self.node_modules_dir, self.python_packages_dir]:
            os.makedirs(dir_path, exist_ok=True)
            
        # Update environment variables
        self._setup_environment()
        
        # Set up log file after project_dir is set
        self.log_file = os.path.join(self.project_dir, "tools_install.log")
        self._add_file_logging()
        
        self.tools_config = self._load_tools_config()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger('SpiderFootToolInstaller')
        handler = logging.StreamHandler(sys.stdout)
        
        if self.verbose:
            logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        else:
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(message)s')
            
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger
        
    def _add_file_logging(self):
        """Add file logging handler."""
        file_handler = logging.FileHandler(self.log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        
        # Always use detailed format for log file
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.info("="*60)
        self.logger.info(f"Starting SpiderFoot Tool Installer session")
        self.logger.info(f"Platform: {platform.platform()}")
        self.logger.info(f"Python: {sys.version}")
        self.logger.info(f"Project directory: {self.project_dir}")
        self.logger.info("="*60)
        
    def _setup_environment(self):
        """Setup environment variables for project-local installations."""
        # Add project bin directory to PATH
        current_path = os.environ.get('PATH', '')
        if self.bin_dir not in current_path:
            os.environ['PATH'] = f"{self.bin_dir}{os.pathsep}{current_path}"
            
        # Set up Python package path
        python_path = os.environ.get('PYTHONPATH', '')
        if self.python_packages_dir not in python_path:
            os.environ['PYTHONPATH'] = f"{self.python_packages_dir}{os.pathsep}{python_path}"
            
        # Set up Node.js module path
        os.environ['NODE_PATH'] = self.node_modules_dir
        
        # Set Go path for local installations
        os.environ['GOPATH'] = os.path.join(self.tools_dir, 'go')
        os.environ['GOBIN'] = self.bin_dir
        os.environ['GO111MODULE'] = 'on'
        os.environ['GOCACHE'] = os.path.join(self.tools_dir, 'go-cache')
        os.environ['GOMODCACHE'] = os.path.join(self.tools_dir, 'go', 'pkg', 'mod')
        
        # NPM prefix for local installations
        os.environ['NPM_CONFIG_PREFIX'] = self.tools_dir
        os.environ['NPM_CONFIG_CACHE'] = os.path.join(self.tools_dir, 'npm-cache')
        
        # Ruby gem paths
        os.environ['GEM_HOME'] = os.path.join(self.tools_dir, 'gems')
        os.environ['GEM_PATH'] = os.path.join(self.tools_dir, 'gems')
        gem_bin = os.path.join(self.tools_dir, 'gems', 'bin')
        if gem_bin not in current_path:
            os.environ['PATH'] = f"{gem_bin}{os.pathsep}{os.environ['PATH']}"
        
        # Nuclei template path
        os.environ['NUCLEI_TEMPLATES_PATH'] = os.path.join(self.tools_dir, 'nuclei-templates')
        
    def _detect_os(self) -> str:
        """Detect the operating system."""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "linux":
            # Try to detect specific Linux distribution
            if os.path.exists("/etc/debian_version"):
                return "debian"
            elif os.path.exists("/etc/redhat-release"):
                return "redhat"
            else:
                return "linux"
        elif system == "windows":
            return "windows"
        else:
            return "unknown"
            
    def _detect_package_manager(self) -> Optional[str]:
        """Detect available package manager."""
        package_managers = {
            "apt": ["apt", "apt-get"],
            "yum": ["yum", "dnf"],
            "brew": ["brew"],
            "snap": ["snap"],
            "choco": ["choco"]
        }
        
        for pm_name, commands in package_managers.items():
            for cmd in commands:
                if shutil.which(cmd):
                    return pm_name
                    
        return None
    
    def _get_go_download_url(self) -> str:
        """Get the appropriate Go download URL for the current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Map machine types to Go arch names
        arch_map = {
            'x86_64': 'amd64',
            'amd64': 'amd64',
            'aarch64': 'arm64',
            'arm64': 'arm64',
            'armv7l': 'armv6l'
        }
        
        arch = arch_map.get(machine, 'amd64')
        
        if system == 'darwin':
            return f"https://go.dev/dl/go1.21.5.darwin-{arch}.tar.gz"
        elif system == 'windows':
            return f"https://go.dev/dl/go1.21.5.windows-{arch}.zip"
        else:  # linux
            return f"https://go.dev/dl/go1.21.5.linux-{arch}.tar.gz"
    
    def _get_node_download_url(self) -> str:
        """Get the appropriate Node.js download URL for the current platform."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Map machine types to Node arch names
        arch_map = {
            'x86_64': 'x64',
            'amd64': 'x64',
            'aarch64': 'arm64',
            'arm64': 'arm64',
            'armv7l': 'armv7l'
        }
        
        arch = arch_map.get(machine, 'x64')
        
        if system == 'darwin':
            return f"https://nodejs.org/dist/v20.10.0/node-v20.10.0-darwin-{arch}.tar.gz"
        elif system == 'windows':
            return f"https://nodejs.org/dist/v20.10.0/node-v20.10.0-win-{arch}.zip"
        else:  # linux
            return f"https://nodejs.org/dist/v20.10.0/node-v20.10.0-linux-{arch}.tar.gz"
    
    def _get_node_dir_name(self) -> str:
        """Get the Node.js directory name after extraction."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        arch_map = {
            'x86_64': 'x64',
            'amd64': 'x64',
            'aarch64': 'arm64',
            'arm64': 'arm64',
            'armv7l': 'armv7l'
        }
        
        arch = arch_map.get(machine, 'x64')
        
        if system == 'darwin':
            return f"node-v20.10.0-darwin-{arch}"
        elif system == 'windows':
            return f"node-v20.10.0-win-{arch}"
        else:
            return f"node-v20.10.0-linux-{arch}"
        
    def _load_tools_config(self) -> Dict[str, ToolInfo]:
        """Load tool configuration."""
        tools = {
            "nmap": ToolInfo(
                name="nmap",
                description="Network discovery and security auditing",
                version="7.90+",
                install_methods={
                    "debian": [
                        "sudo apt-get update",
                        "sudo apt-get install -y nmap",
                        f"ln -sf $(which nmap) {os.path.join(self.bin_dir, 'nmap')}"
                    ],
                    "redhat": [
                        "sudo yum install -y nmap",
                        f"ln -sf $(which nmap) {os.path.join(self.bin_dir, 'nmap')}"
                    ],
                    "macos": [
                        "brew install nmap",
                        f"ln -sf $(which nmap) {os.path.join(self.bin_dir, 'nmap')}"
                    ],
                    "all": [
                        "echo 'Please install nmap using your system package manager:'",
                        "echo '  Debian/Ubuntu: sudo apt-get install nmap'",
                        "echo '  RedHat/CentOS: sudo yum install nmap'",
                        "echo '  macOS: brew install nmap'"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'nmap')} --version",
                required_by=["sfp_tool_nmap"],
                website="https://nmap.org/",
                repository="https://github.com/nmap/nmap"
            ),
            
            "nuclei": ToolInfo(
                name="nuclei",
                description="Fast and customizable vulnerability scanner",
                version="2.9+",
                install_methods={
                    "all": [
                        f"GOPATH={os.path.join(self.tools_dir, 'go')} GOBIN={self.bin_dir} go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest",
                        f"HOME={self.tools_dir} {os.path.join(self.bin_dir, 'nuclei')} -update-templates"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'nuclei')} -version",
                required_by=["sfp_tool_nuclei"],
                website="https://nuclei.projectdiscovery.io/",
                repository="https://github.com/projectdiscovery/nuclei",
                dependencies=["go"]
            ),
            
            "whatweb": ToolInfo(
                name="whatweb",
                description="Web scanner to identify technologies",
                version="0.5+",
                install_methods={
                    "debian": [
                        "sudo apt-get update",
                        "sudo apt-get install -y whatweb",
                        f"ln -sf $(which whatweb) {os.path.join(self.bin_dir, 'whatweb')}"
                    ],
                    "redhat": [
                        "sudo yum install -y epel-release",
                        "sudo yum install -y whatweb",
                        f"ln -sf $(which whatweb) {os.path.join(self.bin_dir, 'whatweb')}"
                    ],
                    "all": [
                        "echo 'WhatWeb installation via source requires Ruby dependencies.'",
                        "echo 'Please install using your system package manager:'",
                        "echo '  Debian/Ubuntu: sudo apt-get install whatweb'",
                        "echo '  RedHat/CentOS: sudo yum install whatweb'"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'whatweb')} --version 2>&1 | head -1",
                required_by=["sfp_tool_whatweb"],
                website="https://www.morningstarsecurity.com/research/whatweb",
                repository="https://github.com/urbanadventurer/WhatWeb",
                dependencies=[]
            ),
            
            "wappalyzer": ToolInfo(
                name="wappalyzer",
                description="Technology profiler for web applications",
                version="6.10+",
                install_methods={
                    "all": [
                        "npm install -g wappalyzer",
                        f"ln -sf $(which wappalyzer) {os.path.join(self.bin_dir, 'wappalyzer')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'wappalyzer')} --version",
                required_by=["sfp_tool_wappalyzer"],
                website="https://www.wappalyzer.com/",
                repository="https://github.com/wappalyzer/wappalyzer",
                dependencies=["node", "npm"]
            ),
            
            "wafw00f": ToolInfo(
                name="wafw00f",
                description="Web Application Firewall detection tool",
                version="2.0+",
                install_methods={
                    "debian": [
                        "which pipx >/dev/null 2>&1 || sudo apt-get install -y pipx",
                        "pipx install wafw00f",
                        f"ln -sf $HOME/.local/bin/wafw00f {os.path.join(self.bin_dir, 'wafw00f')}"
                    ],
                    "all": [
                        "pipx install wafw00f || pip3 install --user --break-system-packages wafw00f",
                        f"ln -sf $HOME/.local/bin/wafw00f {os.path.join(self.bin_dir, 'wafw00f')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'wafw00f')} --version",
                required_by=["sfp_tool_wafw00f"],
                website="https://github.com/EnableSecurity/wafw00f",
                repository="https://github.com/EnableSecurity/wafw00f",
                dependencies=["python3", "pipx"]
            ),
            
            "testssl": ToolInfo(
                name="testssl.sh",
                description="Testing TLS/SSL encryption",
                version="3.0+",
                install_methods={
                    "all": [
                        f"git clone --depth 1 https://github.com/drwetter/testssl.sh.git {os.path.join(self.tools_dir, 'testssl')}",
                        f"chmod +x {os.path.join(self.tools_dir, 'testssl', 'testssl.sh')}",
                        f"ln -sf {os.path.join(self.tools_dir, 'testssl', 'testssl.sh')} {os.path.join(self.bin_dir, 'testssl.sh')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'testssl.sh')} --version",
                required_by=["sfp_tool_testsslsh"],
                website="https://testssl.sh/",
                repository="https://github.com/drwetter/testssl.sh"
            ),
            
            "trufflehog": ToolInfo(
                name="trufflehog",
                description="Search for secrets in git repositories",
                version="3.0+",
                install_methods={
                    "debian": [
                        "which pipx >/dev/null 2>&1 || sudo apt-get install -y pipx",
                        "pipx install truffleHog3",
                        f"ln -sf $HOME/.local/bin/trufflehog3 {os.path.join(self.bin_dir, 'trufflehog3')}"
                    ],
                    "all": [
                        "pipx install truffleHog3 || pip3 install --user --break-system-packages truffleHog3",
                        f"ln -sf $HOME/.local/bin/trufflehog3 {os.path.join(self.bin_dir, 'trufflehog3')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'trufflehog3')} --version",
                required_by=["sfp_tool_trufflehog"],
                website="https://github.com/feeltheajf/truffleHog3",
                repository="https://github.com/feeltheajf/truffleHog3",
                dependencies=["python3", "pipx"]
            ),
            
            "retirejs": ToolInfo(
                name="retire.js",
                description="Scanner for JavaScript library vulnerabilities",
                version="3.0+",
                install_methods={
                    "all": [
                        "npm install -g retire",
                        f"ln -sf $(which retire) {os.path.join(self.bin_dir, 'retire')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'retire')} --version",
                required_by=["sfp_tool_retirejs"],
                website="https://retirejs.github.io/retire.js/",
                repository="https://github.com/RetireJS/retire.js",
                dependencies=["node", "npm"]
            ),
            
            "dnstwist": ToolInfo(
                name="dnstwist",
                description="Domain name permutation engine",
                version="20201228+",
                install_methods={
                    "debian": [
                        "which pipx >/dev/null 2>&1 || sudo apt-get install -y pipx",
                        "pipx install 'dnstwist[full]'",
                        f"ln -sf $HOME/.local/bin/dnstwist {os.path.join(self.bin_dir, 'dnstwist')}"
                    ],
                    "all": [
                        "pipx install 'dnstwist[full]' || pip3 install --user --break-system-packages 'dnstwist[full]'",
                        f"ln -sf $HOME/.local/bin/dnstwist {os.path.join(self.bin_dir, 'dnstwist')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'dnstwist')} --version",
                required_by=["sfp_tool_dnstwist"],
                website="https://github.com/elceef/dnstwist",
                repository="https://github.com/elceef/dnstwist",
                dependencies=["python3", "pipx"]
            ),
            
            "nbtscan": ToolInfo(
                name="nbtscan",
                description="NetBIOS scanner",
                version="1.5+",
                install_methods={
                    "debian": [
                        "sudo apt-get update",
                        "sudo apt-get install -y nbtscan",
                        f"ln -sf $(which nbtscan) {os.path.join(self.bin_dir, 'nbtscan')}"
                    ],
                    "redhat": [
                        "sudo yum install -y nbtscan",
                        f"ln -sf $(which nbtscan) {os.path.join(self.bin_dir, 'nbtscan')}"
                    ],
                    "all": [
                        f"git clone https://github.com/resurrecting-open-source-projects/nbtscan.git {os.path.join(self.tools_dir, 'nbtscan-src')}",
                        f"cd {os.path.join(self.tools_dir, 'nbtscan-src')} && ./autogen.sh && ./configure --prefix={self.tools_dir} && make && make install"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'nbtscan')} -h 2>&1 | head -1",
                required_by=["sfp_tool_nbtscan"],
                website="http://www.unixwiz.net/tools/nbtscan.html",
                repository="https://github.com/resurrecting-open-source-projects/nbtscan"
            ),
            
            "onesixtyone": ToolInfo(
                name="onesixtyone",
                description="SNMP scanner",
                version="0.3+",
                install_methods={
                    "all": [
                        f"git clone https://github.com/trailofbits/onesixtyone.git {os.path.join(self.tools_dir, 'onesixtyone-src')}",
                        f"cd {os.path.join(self.tools_dir, 'onesixtyone-src')} && make",
                        f"cp {os.path.join(self.tools_dir, 'onesixtyone-src', 'onesixtyone')} {os.path.join(self.bin_dir, 'onesixtyone')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'onesixtyone')} -h 2>&1 | head -1",
                required_by=["sfp_tool_onesixtyone"],
                website="https://github.com/trailofbits/onesixtyone",
                repository="https://github.com/trailofbits/onesixtyone"
            ),
            
            "snallygaster": ToolInfo(
                name="snallygaster",
                description="Scan for secret files on web servers",
                version="0.0.12+",
                install_methods={
                    "debian": [
                        "which pipx >/dev/null 2>&1 || sudo apt-get install -y pipx",
                        "pipx install snallygaster",
                        f"ln -sf $HOME/.local/bin/snallygaster {os.path.join(self.bin_dir, 'snallygaster')}"
                    ],
                    "all": [
                        "pipx install snallygaster || pip3 install --user --break-system-packages snallygaster",
                        f"ln -sf $HOME/.local/bin/snallygaster {os.path.join(self.bin_dir, 'snallygaster')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'snallygaster')} --version",
                required_by=["sfp_tool_snallygaster"],
                website="https://github.com/hannob/snallygaster",
                repository="https://github.com/hannob/snallygaster",
                dependencies=["python3", "pipx"]
            ),
            
            "cmseek": ToolInfo(
                name="cmseek",
                description="CMS detection and exploitation",
                version="1.1.3+",
                install_methods={
                    "all": [
                        f"git clone https://github.com/Tuhinshubhra/CMSeeK {os.path.join(self.tools_dir, 'cmseek')}",
                        f"cd {os.path.join(self.tools_dir, 'cmseek')} && pip3 install --target={self.python_packages_dir} -r requirements.txt",
                        f"echo '#!/bin/bash\npython3 {os.path.join(self.tools_dir, 'cmseek', 'cmseek.py')} \"$@\"' > {os.path.join(self.bin_dir, 'cmseek')}",
                        f"chmod +x {os.path.join(self.bin_dir, 'cmseek')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'cmseek')} --version",
                required_by=["sfp_tool_cmseek"],
                website="https://github.com/Tuhinshubhra/CMSeeK",
                repository="https://github.com/Tuhinshubhra/CMSeeK",
                dependencies=["python3", "pip3", "git"]
            ),
            
            "tor": ToolInfo(
                name="tor",
                description="The Onion Router - Anonymous communication network",
                version="0.4+",
                install_methods={
                    "debian": [
                        "sudo apt-get update",
                        "sudo apt-get install -y tor",
                        f"mkdir -p {os.path.join(self.tools_dir, 'tor', 'data')}",
                        f"echo 'SocksPort 9050\\nDataDirectory {os.path.join(self.tools_dir, 'tor', 'data')}' > {os.path.join(self.tools_dir, 'tor', 'torrc')}"
                    ],
                    "redhat": [
                        "sudo yum install -y epel-release",
                        "sudo yum install -y tor",
                        f"mkdir -p {os.path.join(self.tools_dir, 'tor', 'data')}",
                        f"echo 'SocksPort 9050\\nDataDirectory {os.path.join(self.tools_dir, 'tor', 'data')}' > {os.path.join(self.tools_dir, 'tor', 'torrc')}"
                    ],
                    "macos": [
                        "brew install tor",
                        f"mkdir -p {os.path.join(self.tools_dir, 'tor', 'data')}",
                        f"echo 'SocksPort 9050\\nDataDirectory {os.path.join(self.tools_dir, 'tor', 'data')}' > {os.path.join(self.tools_dir, 'tor', 'torrc')}"
                    ],
                    "all": [
                        f"echo 'Tor requires system installation. Please use your package manager to install tor.'"
                    ]
                },
                verify_command="tor --version",
                required_by=["sfp_ahmia", "sfp_torch"],
                website="https://www.torproject.org/",
                repository="https://github.com/torproject/tor"
            ),
            
            "pysocks": ToolInfo(
                name="pysocks",
                description="Python SOCKS client module for Tor integration",
                version="1.7+",
                install_methods={
                    "all": [
                        f"pip3 install --target={self.python_packages_dir} pysocks"
                    ]
                },
                verify_command=f"python3 -c 'import sys; sys.path.insert(0, \"{self.python_packages_dir}\"); import socks; print(\"PySocks\", socks.__version__)'",
                required_by=["tor"],
                website="https://github.com/Anorov/PySocks",
                repository="https://github.com/Anorov/PySocks",
                dependencies=["python3", "pip3"]
            ),
            
            "stem": ToolInfo(
                name="stem",
                description="Python controller library for Tor",
                version="1.8+",
                install_methods={
                    "all": [
                        f"pip3 install --target={self.python_packages_dir} stem"
                    ]
                },
                verify_command=f"python3 -c 'import sys; sys.path.insert(0, \"{self.python_packages_dir}\"); import stem; print(\"Stem\", stem.__version__)'",
                required_by=["tor"],
                website="https://stem.torproject.org/",
                repository="https://github.com/torproject/stem",
                dependencies=["python3", "pip3"]
            ),
            
            # Dependencies
            "go": ToolInfo(
                name="go",
                description="Go programming language",
                version="1.18+",
                install_methods={
                    "all": [
                        f"wget -O {os.path.join(self.tools_dir, 'go.tar.gz')} {self._get_go_download_url()}",
                        f"tar -C {self.tools_dir} -xzf {os.path.join(self.tools_dir, 'go.tar.gz')}",
                        f"ln -sf {os.path.join(self.tools_dir, 'go', 'bin', 'go')} {os.path.join(self.bin_dir, 'go')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'go')} version",
                required_by=[],
                website="https://golang.org/",
                repository="https://github.com/golang/go"
            ),
            
            "node": ToolInfo(
                name="node",
                description="Node.js JavaScript runtime",
                version="14+",
                install_methods={
                    "all": [
                        f"wget -O {os.path.join(self.tools_dir, 'node.tar.gz')} {self._get_node_download_url()}",
                        f"tar -C {self.tools_dir} -xzf {os.path.join(self.tools_dir, 'node.tar.gz')}",
                        f"ln -sf {os.path.join(self.tools_dir, self._get_node_dir_name(), 'bin', 'node')} {os.path.join(self.bin_dir, 'node')}",
                        f"ln -sf {os.path.join(self.tools_dir, self._get_node_dir_name(), 'bin', 'npm')} {os.path.join(self.bin_dir, 'npm')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'node')} --version",
                required_by=[],
                website="https://nodejs.org/",
                repository="https://github.com/nodejs/node"
            ),
            
            "npm": ToolInfo(
                name="npm",
                description="Node.js package manager",
                version="6+",
                install_methods={
                    "all": ["echo 'NPM is installed with Node.js'"]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'npm')} --version",
                required_by=[],
                website="https://www.npmjs.com/",
                repository="https://github.com/npm/cli",
                dependencies=["node"]
            ),
            
            "ruby": ToolInfo(
                name="ruby",
                description="Ruby programming language",
                version="2.7+",
                install_methods={
                    "debian": ["sudo apt-get update", "sudo apt-get install -y ruby-full ruby-dev libyaml-dev"],
                    "redhat": ["sudo yum install -y ruby ruby-devel libyaml-devel"],
                    "macos": ["brew install ruby"],
                    "all": ["echo 'Ruby typically requires system installation. Please install using your package manager.'"] 
                },
                verify_command="ruby --version",
                required_by=[],
                website="https://www.ruby-lang.org/",
                repository="https://github.com/ruby/ruby"
            ),
            
            "bundler": ToolInfo(
                name="bundler",
                description="Ruby dependency manager",
                version="2.0+",
                install_methods={
                    "all": [
                        f"gem install --install-dir {os.path.join(self.tools_dir, 'gems')} bundler",
                        f"ln -sf {os.path.join(self.tools_dir, 'gems', 'bin', 'bundle')} {os.path.join(self.bin_dir, 'bundle')}",
                        f"ln -sf {os.path.join(self.tools_dir, 'gems', 'bin', 'bundler')} {os.path.join(self.bin_dir, 'bundler')}"
                    ]
                },
                verify_command=f"{os.path.join(self.bin_dir, 'bundle')} --version",
                required_by=[],
                website="https://bundler.io/",
                repository="https://github.com/rubygems/bundler",
                dependencies=["ruby"]
            ),
            
            "python3": ToolInfo(
                name="python3",
                description="Python 3 programming language",
                version="3.6+",
                install_methods={
                    "debian": ["sudo apt-get update", "sudo apt-get install -y python3 python3-pip"],
                    "redhat": ["sudo yum install -y python3 python3-pip"],
                    "macos": ["brew install python3"],
                    "all": ["echo 'Python3 is usually pre-installed. Please install using your system package manager if missing.'"]
                },
                verify_command="python3 --version",
                required_by=[],
                website="https://www.python.org/",
                repository="https://github.com/python/cpython"
            ),
            
            "pip3": ToolInfo(
                name="pip3",
                description="Python package installer",
                version="20.0+",
                install_methods={
                    "debian": ["sudo apt-get update", "sudo apt-get install -y python3-pip"],
                    "redhat": ["sudo yum install -y python3-pip"],
                    "macos": ["python3 -m ensurepip --upgrade"],
                    "all": ["python3 -m ensurepip --upgrade"]
                },
                verify_command="pip3 --version",
                required_by=[],
                website="https://pip.pypa.io/",
                repository="https://github.com/pypa/pip",
                dependencies=["python3"]
            ),
            
            "git": ToolInfo(
                name="git",
                description="Distributed version control system",
                version="2.0+",
                install_methods={
                    "debian": ["sudo apt-get update", "sudo apt-get install -y git"],
                    "redhat": ["sudo yum install -y git"],
                    "macos": ["brew install git"],
                    "all": ["echo 'Git is usually pre-installed. Please install using your system package manager if missing.'"]
                },
                verify_command="git --version",
                required_by=[],
                website="https://git-scm.com/",
                repository="https://github.com/git/git"
            ),
            
            "pipx": ToolInfo(
                name="pipx",
                description="Install and Run Python Applications in Isolated Environments",
                version="1.0+",
                install_methods={
                    "debian": ["sudo apt-get update", "sudo apt-get install -y pipx", "pipx ensurepath"],
                    "redhat": ["python3 -m pip install --user pipx", "python3 -m pipx ensurepath"],
                    "macos": ["brew install pipx", "pipx ensurepath"],
                    "all": ["python3 -m pip install --user pipx", "python3 -m pipx ensurepath"]
                },
                verify_command="pipx --version",
                required_by=[],
                website="https://pipx.pypa.io/",
                repository="https://github.com/pypa/pipx",
                dependencies=["python3"]
            )
        }
        
        return tools
        
    def check_tool(self, tool_name: str) -> Tuple[bool, str]:
        """Check if a tool is installed and get its version."""
        if tool_name not in self.tools_config:
            return False, f"Unknown tool: {tool_name}"
            
        tool = self.tools_config[tool_name]
        
        try:
            # Use shell=True if command contains pipes or redirections
            use_shell = any(char in tool.verify_command for char in ['|', '>', '<', '&'])
            
            if use_shell:
                result = subprocess.run(
                    tool.verify_command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=os.environ.copy()
                )
            else:
                result = subprocess.run(
                    tool.verify_command.split(),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    env=os.environ.copy()
                )
            
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                return True, version
            else:
                return False, "Not installed"
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False, "Not installed"
        except Exception as e:
            return False, f"Check failed: {str(e)}"
            
    def install_dependencies(self, tool_name: str) -> bool:
        """Install dependencies for a tool."""
        tool = self.tools_config.get(tool_name)
        if not tool or not tool.dependencies:
            return True
            
        self.logger.info(f"Installing dependencies for {tool_name}...")
        
        for dep in tool.dependencies:
            if dep not in self.tools_config:
                # Check if it's a system dependency that might already be installed
                if dep in ['python3', 'pip3', 'ruby', 'git']:
                    # Try to verify if it's already installed using common commands
                    check_commands = {
                        'python3': 'python3 --version',
                        'pip3': 'pip3 --version',
                        'ruby': 'ruby --version',
                        'git': 'git --version'
                    }
                    if dep in check_commands:
                        try:
                            result = subprocess.run(
                                check_commands[dep].split(),
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                self.logger.info(f"✓ {dep} is already installed (system): {result.stdout.strip()}")
                                continue
                        except:
                            pass
                    self.logger.warning(f"Dependency {dep} not found in tools config and not installed")
                    return False
                else:
                    self.logger.warning(f"Unknown dependency: {dep}")
                    continue
                
            installed, _ = self.check_tool(dep)
            if not installed:
                self.logger.info(f"Installing dependency: {dep}")
                if not self.install_tool(dep):
                    self.logger.error(f"Failed to install dependency: {dep}")
                    return False
                    
        return True
        
    def install_tool(self, tool_name: str) -> bool:
        """Install a specific tool."""
        if tool_name not in self.tools_config:
            self.logger.error(f"Unknown tool: {tool_name}")
            return False
            
        tool = self.tools_config[tool_name]
        
        # Check if already installed
        installed, version = self.check_tool(tool_name)
        if installed:
            self.logger.info(f"✓ {tool_name} is already installed: {version}")
            return True
            
        self.logger.info(f"Installing {tool_name}...")
        
        # Install dependencies first
        if not self.install_dependencies(tool_name):
            return False
            
        # Find appropriate install method
        install_commands = None
        
        # Check OS-specific methods first
        if self.os_type in tool.install_methods:
            install_commands = tool.install_methods[self.os_type]
        elif "all" in tool.install_methods:
            install_commands = tool.install_methods["all"]
        else:
            self.logger.error(f"No installation method available for {tool_name} on {self.os_type}")
            return False
            
        # Execute installation commands
        for cmd in install_commands:
            self.logger.debug(f"Executing: {cmd}")
            
            try:
                # Always use shell=True for all commands to handle complex shell operations
                # This allows proper handling of &&, ||, cd, and other shell constructs
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    env=os.environ.copy(),
                    cwd=self.project_dir  # Set working directory to project root
                )
                
                if result.returncode != 0:
                    self.logger.error(f"Command failed: {cmd}")
                    self.logger.error(f"Return code: {result.returncode}")
                    self.logger.error(f"Error: {result.stderr}")
                    if result.stdout:
                        self.logger.error(f"Output: {result.stdout}")
                    return False
                else:
                    if result.stdout:
                        self.logger.debug(f"Command output: {result.stdout}")
                    
            except subprocess.TimeoutExpired:
                self.logger.error(f"Command timed out: {cmd}")
                return False
            except Exception as e:
                self.logger.error(f"Failed to execute command: {cmd}")
                self.logger.error(f"Error: {str(e)}")
                return False
                
        # Run post-install commands if any
        if tool.post_install:
            for cmd in tool.post_install:
                self.logger.debug(f"Running post-install: {cmd}")
                subprocess.run(cmd, shell=True, env=os.environ.copy())
                
        # Verify installation
        installed, version = self.check_tool(tool_name)
        if installed:
            self.logger.info(f"✓ Successfully installed {tool_name}: {version}")
            return True
        else:
            self.logger.error(f"✗ Installation verification failed for {tool_name}")
            return False
            
    def install_all(self) -> Dict[str, bool]:
        """Install all tools."""
        results = {}
        
        # Filter out dependencies (they'll be installed automatically)
        main_tools = [
            name for name, tool in self.tools_config.items()
            if tool.required_by  # Only tools required by SpiderFoot modules
        ]
        
        self.logger.info(f"Installing {len(main_tools)} tools...")
        
        for tool_name in main_tools:
            results[tool_name] = self.install_tool(tool_name)
            
        return results
        
    def list_tools(self) -> None:
        """List all available tools and their status."""
        print("\n🦇 SpiderFoot BE Tool Status\n")
        print(f"{'Tool':<20} {'Status':<15} {'Version':<30} {'Required By':<30}")
        print("-" * 95)
        
        for name, tool in self.tools_config.items():
            if not tool.required_by:  # Skip dependencies
                continue
                
            installed, version = self.check_tool(name)
            status = "✓ Installed" if installed else "✗ Not installed"
            modules = ", ".join(tool.required_by)
            
            print(f"{name:<20} {status:<15} {version[:28]:<30} {modules:<30}")
            
    def generate_dockerfile(self) -> str:
        """Generate Dockerfile with all tools installed."""
        dockerfile = """# SpiderFoot BE with Third-Party Tools
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    wget \\
    sudo \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Install SpiderFoot BE
WORKDIR /app
COPY . /app/

# Install Python requirements
RUN pip install -r requirements.txt

# Install third-party tools
"""
        
        # Add tool installation commands
        for name, tool in self.tools_config.items():
            if not tool.required_by:
                continue
                
            dockerfile += f"\n# Install {name}\n"
            
            if "debian" in tool.install_methods:
                for cmd in tool.install_methods["debian"]:
                    # Remove sudo for Docker
                    cmd = cmd.replace("sudo ", "")
                    dockerfile += f"RUN {cmd}\n"
            elif "all" in tool.install_methods:
                for cmd in tool.install_methods["all"]:
                    dockerfile += f"RUN {cmd}\n"
                    
        dockerfile += """
# Expose SpiderFoot port
EXPOSE 5001

# Run SpiderFoot
CMD ["python", "sf.py", "-l", "0.0.0.0:5001"]
"""
        
        return dockerfile
    
    def create_activation_script(self) -> None:
        """Create shell activation script for tool environment."""
        activate_script = f"""#!/bin/bash
# SpiderFoot BE Tool Environment Activation Script

# Add tool binaries to PATH
export PATH="{self.bin_dir}:$PATH"

# Set Python package path
export PYTHONPATH="{self.python_packages_dir}:$PYTHONPATH"

# Set Node modules path
export NODE_PATH="{self.node_modules_dir}"

# Set Go paths
export GOPATH="{os.path.join(self.tools_dir, 'go')}"
export GOBIN="{self.bin_dir}"
export GO111MODULE="on"
export GOCACHE="{os.path.join(self.tools_dir, 'go-cache')}"
export GOMODCACHE="{os.path.join(self.tools_dir, 'go', 'pkg', 'mod')}"

# NPM prefix
export NPM_CONFIG_PREFIX="{self.tools_dir}"
export NPM_CONFIG_CACHE="{os.path.join(self.tools_dir, 'npm-cache')}"

# Ruby gem path
export GEM_HOME="{os.path.join(self.tools_dir, 'gems')}"
export GEM_PATH="{os.path.join(self.tools_dir, 'gems')}"

# Nuclei template path
export NUCLEI_TEMPLATES_PATH="{os.path.join(self.tools_dir, 'nuclei-templates')}"

echo "🦇 SpiderFoot BE Tool Environment Activated"
echo "   Tool directory: {self.tools_dir}"
echo "   Binary directory: {self.bin_dir}"
echo ""
echo "Run 'python install_tools.py --list' to see available tools"
"""
        
        activate_path = os.path.join(self.project_dir, "activate_tools.sh")
        with open(activate_path, 'w') as f:
            f.write(activate_script)
        
        os.chmod(activate_path, 0o755)
        
        self.logger.info(f"✓ Created activation script: {activate_path}")
        self.logger.info(f"  To activate: source {activate_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SpiderFoot BE Tool Installation Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all tools and their status
  python install_tools.py --list
  
  # Install all tools
  python install_tools.py --all
  
  # Install specific tool
  python install_tools.py --install nmap
  
  # Install multiple tools
  python install_tools.py --install nuclei whatweb wappalyzer
  
  # Check if tools are installed
  python install_tools.py --check
  
  # Generate Dockerfile
  python install_tools.py --dockerfile > Dockerfile.tools
"""
    )
    
    parser.add_argument("-l", "--list", action="store_true",
                      help="List all tools and their status")
    parser.add_argument("-a", "--all", action="store_true",
                      help="Install all tools")
    parser.add_argument("-i", "--install", metavar="TOOL", nargs='+',
                      help="Install specific tool(s) - can specify multiple tools")
    parser.add_argument("-c", "--check", action="store_true",
                      help="Check installation status of all tools")
    parser.add_argument("-d", "--dockerfile", action="store_true",
                      help="Generate Dockerfile with all tools")
    parser.add_argument("-v", "--verbose", action="store_true",
                      help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Initialize installer
    installer = ToolInstaller(verbose=args.verbose)
    
    # Always create activation script
    installer.create_activation_script()
    
    # Handle commands
    if args.list:
        installer.list_tools()
        print(f"\n📄 Installation log saved to: {installer.log_file}")
        
    elif args.all:
        results = installer.install_all()
        
        print("\n📊 Installation Summary\n")
        success = sum(1 for v in results.values() if v)
        total = len(results)
        
        print(f"Successfully installed: {success}/{total}")
        
        if success < total:
            print("\nFailed installations:")
            for tool, result in results.items():
                if not result:
                    print(f"  - {tool}")
        
        print(f"\n📄 Installation log saved to: {installer.log_file}")
                    
    elif args.install:
        results = {}
        for tool in args.install:
            print(f"\n📦 Installing {tool}...")
            results[tool] = installer.install_tool(tool)
        
        # Show summary
        print("\n📊 Installation Summary\n")
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        print(f"Successfully installed: {success_count}/{total_count}")
        
        if success_count < total_count:
            print("\nFailed installations:")
            for tool, result in results.items():
                if not result:
                    print(f"  - {tool}")
        
        print(f"\n📄 Installation log saved to: {installer.log_file}")
        sys.exit(0 if success_count == total_count else 1)
        
    elif args.check:
        installer.list_tools()
        print(f"\n📄 Installation log saved to: {installer.log_file}")
        
    elif args.dockerfile:
        print(installer.generate_dockerfile())
        
    else:
        parser.print_help()
        print(f"\n📄 Installation log saved to: {installer.log_file}")


if __name__ == "__main__":
    main()