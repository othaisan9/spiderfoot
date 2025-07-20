# SpiderFoot BE Installation Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [Verification](#verification)
5. [Troubleshooting](#troubleshooting)

## System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, Windows 10+
- **Python**: 3.8 or higher
- **RAM**: 2GB minimum (4GB+ recommended)
- **Storage**: 500MB for application + space for data
- **Network**: Internet connection for OSINT data collection

### Recommended Requirements
- **OS**: Ubuntu 20.04+ or macOS 12+
- **Python**: 3.10+
- **RAM**: 8GB+
- **Storage**: 10GB+ (for extensive scan data)
- **CPU**: Multi-core processor for concurrent operations

## Installation Methods

### Method 1: Standard Installation (Recommended)

#### Step 1: Clone Repository
```bash
git clone https://github.com/your-repo/spiderfoot-be.git
cd spiderfoot-be/spiderfoot
```

#### Step 2: Create Virtual Environment
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Initialize Database
```bash
# Database will be created automatically on first run
# Default location: ~/.spiderfoot/spiderfoot.db
```

### Method 2: Docker Installation

```bash
# Build Docker image
docker build -t spiderfoot-be .

# Run container
docker run -p 5001:5001 -v ~/.spiderfoot:/home/spiderfoot/.spiderfoot spiderfoot-be
```

### Method 3: Development Installation

```bash
# Clone with submodules
git clone --recursive https://github.com/your-repo/spiderfoot-be.git
cd spiderfoot-be/spiderfoot

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Method 4: Installing Third-Party Tools

SpiderFoot BE includes several modules that require third-party security tools. Use the included installer:

```bash
# List available tools and their status
python install_tools.py --list

# Install specific tools
python install_tools.py --install nmap nuclei dnstwist

# Install all tools
python install_tools.py --all

# Check installation log
cat tools_install.log
```

#### Important Notes for Ubuntu 23.04+ / Debian 12+

These systems use PEP 668 (externally managed environments) which restricts system-wide Python package installations. The installer handles this automatically by:

1. Using `pipx` for Python applications (recommended)
2. Using system package managers when available
3. Creating isolated environments for each tool

If you encounter issues:
```bash
# Install pipx if not available
sudo apt-get install pipx
pipx ensurepath

# Restart your shell or run
source ~/.bashrc
```

## Configuration

### Basic Configuration

#### 1. Database Location
By default, SpiderFoot BE uses `~/.spiderfoot/spiderfoot.db`. To change:

```python
# In your config or environment
export SPIDERFOOT_DB="/custom/path/spiderfoot.db"
```

#### 2. Web Interface Settings
```bash
# Default: localhost only
python sf.py -l 127.0.0.1:5001

# Allow external access (use with caution)
python sf.py -l 0.0.0.0:5001
```

#### 3. Proxy Configuration

##### For Tor (.onion sites)
```bash
# Install Tor
python install_tools.py --install tor

# Configure SpiderFoot to use Tor
python configure_tor.py

# Verify Tor is running
python -c "from spiderfoot.tor_manager import tor_manager; print(tor_manager.is_tor_running())"
```

##### For HTTP/SOCKS Proxy
Configure via Web UI or set in scan:
- SOCKS Type: 4, 5, HTTP, or TOR
- Server: proxy address
- Port: proxy port

### Advanced Configuration

#### 1. Third-Party Tools Integration
```bash
# List available tools
python install_tools.py --list

# Install specific tools
python install_tools.py --install nuclei,amass,subfinder

# Install all tools
python install_tools.py --install all

# Verify installations
python install_tools.py --verify
```

#### 2. API Keys Configuration
Add API keys through Web UI (Settings → Module Settings) or directly:

```python
# Example: Configure Shodan API key
# Via Web UI: Settings → Modules → Shodan → API Key
```

#### 3. Performance Tuning
```python
# config settings
{
    '_maxthreads': 5,  # Increase for more concurrency
    '_fetchtimeout': 30,  # Increase for slow networks
    '_internettlds_cache': 168,  # Cache TLD list for 1 week
}
```

## Verification

### 1. Test Installation
```bash
# Run simple test
python test_async_simple.py

# Expected output:
# ✓ AsyncHttpClient created successfully
# ✓ AsyncDnsResolver created successfully
# ...
# 7/7 tests passed (100%)
```

### 2. Test Module Loading
```bash
# List available modules
python sf.py -M

# Should show both async and unified modules:
# - sfp_shodan_async
# - sfp_virustotal_async
# - sfp_unified_dns_filters
# - sfp_unified_ip_info
# - sfp_unified_search_engines
```

### 3. Test Basic Scan
```bash
# Command line scan
python sf.py -s example.com -m sfp__stor_db -q

# Should output:
# Source          Type              Data
# SpiderFoot UI   Internet Name     example.com
# SpiderFoot UI   Domain Name       example.com
```

### 4. Test Web Interface
```bash
# Start web server
python sf.py -l 127.0.0.1:5001

# Open browser to http://localhost:5001
# Should see SpiderFoot BE interface
```

## Troubleshooting

### Common Issues

#### 1. Database Location Error
```
ERROR: spiderfoot.db file exists in /path/to/spiderfoot
```
**Solution**: Remove or rename the local database file
```bash
rm spiderfoot.db  # or
mv spiderfoot.db spiderfoot.db.old
```

#### 2. Module Import Errors
```
ImportError: No module named 'aiohttp'
```
**Solution**: Reinstall requirements
```bash
pip install -r requirements.txt
```

#### 3. Permission Denied
```
PermissionError: [Errno 13] Permission denied
```
**Solution**: Check file permissions or use virtual environment
```bash
# Fix permissions
chmod +x sf.py

# Or use virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate
```

#### 4. Port Already in Use
```
error: [Errno 48] Address already in use
```
**Solution**: Use different port or kill existing process
```bash
# Use different port
python sf.py -l 127.0.0.1:5002

# Or find and kill process
lsof -i :5001
kill -9 <PID>
```

#### 5. Tor Connection Issues
```
Failed to connect to .onion site
```
**Solution**: Ensure Tor is running and configured
```bash
# Start Tor
python -c "from spiderfoot.tor_manager import tor_manager; tor_manager.start_tor()"

# Verify connection
python -c "from spiderfoot.tor_manager import tor_manager; print(tor_manager.test_tor_connection())"
```

### Debug Mode
Enable detailed logging for troubleshooting:
```bash
# Command line with debug
python sf.py -d -s example.com -m sfp__stor_db

# Set debug in config
'_debug': True
```

### Tool Installation Issues

#### 6. Python Package Installation Errors (Ubuntu 23.04+)
```
error: externally-managed-environment
```
**Solution**: The installer automatically uses pipx, but if issues persist:
```bash
# Install pipx
sudo apt-get install pipx
pipx ensurepath

# Or use virtual environment
python -m venv .venv
source .venv/bin/activate
python install_tools.py --install dnstwist
```

#### 7. Tool Not Found After Installation
```
command not found: nmap
```
**Solution**: Activate the tool environment:
```bash
# Source the activation script
source activate_tools.sh

# Or add to PATH manually
export PATH="$PWD/tools/bin:$PATH"
```

### Getting Help

1. **Check Logs**
   - Web UI: Look for errors in console
   - CLI: Add `-d` flag for debug output
   - Tool Installation: Check `tools_install.log`

2. **Verify Dependencies**
   ```bash
   pip list | grep -E "aiohttp|asyncio|cherrypy"
   ```

3. **Test Components**
   ```bash
   # Test async framework
   python test_async_simple.py
   
   # Test database connection
   python -c "from spiderfoot import SpiderFootDb; db = SpiderFootDb({}); print('DB OK')"
   
   # Test installed tools
   python install_tools.py --check
   ```

4. **Report Issues**
   - Include Python version: `python --version`
   - Include OS details: `uname -a` (Linux/macOS)
   - Include error messages and logs
   - Check existing issues on GitHub

## Next Steps

After successful installation:

1. **Configure API Keys**: Add keys for Shodan, VirusTotal, etc.
2. **Run First Scan**: Start with a small target to verify setup
3. **Explore Modules**: Review available modules with `python sf.py -M`
4. **Read Documentation**: Check README_BE.md for advanced usage
5. **Join Community**: Participate in discussions and contribute

## Security Considerations

1. **Database Security**: Protect `~/.spiderfoot/spiderfoot.db` - contains API keys
2. **Web Interface**: Use authentication in production environments
3. **API Keys**: Store securely, never commit to version control
4. **Network Access**: Be cautious with `0.0.0.0` binding
5. **Scan Ethics**: Only scan assets you own or have permission to test

---

For more information, see:
- [README_BE.md](README_BE.md) - Full documentation
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Migrating from legacy SpiderFoot
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - API reference