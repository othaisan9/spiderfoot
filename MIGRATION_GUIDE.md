# SpiderFoot Legacy to BE Migration Guide

## Overview

This guide helps you migrate from legacy SpiderFoot to SpiderFoot BE (Business Edition) while preserving your data, configurations, and workflows.

## Table of Contents
1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Migration Process](#migration-process)
3. [Module Mapping](#module-mapping)
4. [Configuration Migration](#configuration-migration)
5. [API Key Migration](#api-key-migration)
6. [Custom Module Migration](#custom-module-migration)
7. [Post-Migration Verification](#post-migration-verification)
8. [Rollback Plan](#rollback-plan)

## Pre-Migration Checklist

### 1. Backup Current Installation
```bash
# Backup database
cp ~/.spiderfoot/spiderfoot.db ~/.spiderfoot/spiderfoot.db.backup

# Backup custom modules (if any)
cp -r /path/to/spiderfoot/modules/custom_* ./backup/

# Export current configuration
# Via Web UI: Settings → Export Configuration
```

### 2. Document Current Setup
- [ ] List of active API keys
- [ ] Custom module names
- [ ] Proxy configurations
- [ ] Scheduled scans
- [ ] Integration endpoints

### 3. System Requirements Check
- [ ] Python 3.8+ installed
- [ ] Sufficient disk space (2x current database size)
- [ ] Network connectivity for package installation

## Migration Process

### Step 1: Install SpiderFoot BE
```bash
# Clone BE repository
git clone https://github.com/your-repo/spiderfoot-be.git
cd spiderfoot-be/spiderfoot

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Database Migration
SpiderFoot BE uses the same database schema, so no conversion is needed:

```bash
# Option 1: Use existing database location (recommended)
# SpiderFoot BE will automatically use ~/.spiderfoot/spiderfoot.db

# Option 2: Copy database to new location
cp ~/.spiderfoot/spiderfoot.db.backup ~/.spiderfoot/spiderfoot.db

# Verify database
python -c "from spiderfoot import SpiderFootDb; db = SpiderFootDb({}); print('Database OK')"
```

### Step 3: Module Migration
The module consolidation is handled automatically. No action required.

### Step 4: Configuration Migration
```bash
# Configurations are stored in the database and will be preserved
# Verify after starting SpiderFoot BE:
python sf.py -l 127.0.0.1:5001
# Navigate to Settings to confirm configurations
```

## Module Mapping

### Consolidated Modules Reference

#### DNS Filter Modules → `sfp_unified_dns_filters`
| Legacy Module | Status | Notes |
|--------------|---------|--------|
| sfp_adguard_dns | ✅ Consolidated | All functionality preserved |
| sfp_cleanbrowsing | ✅ Consolidated | |
| sfp_cloudflaredns | ✅ Consolidated | |
| sfp_comodo | ✅ Consolidated | |
| sfp_dns_for_family | ✅ Consolidated | |
| sfp_opendns | ✅ Consolidated | |
| sfp_quad9 | ✅ Consolidated | |
| sfp_yandexdns | ✅ Consolidated | |

#### IP Information Modules → `sfp_unified_ip_info`
| Legacy Module | Status | Notes |
|--------------|---------|--------|
| sfp_abstractapi | ✅ Consolidated | API key required |
| sfp_blockchain | ✅ Consolidated | |
| sfp_ipapico | ✅ Consolidated | |
| sfp_ipapicom | ✅ Consolidated | |
| sfp_ipregistry | ✅ Consolidated | API key required |
| sfp_ipstack | ✅ Consolidated | API key required |
| sfp_neutrinoapi | ✅ Consolidated | API key required |
| sfp_numverify | ✅ Consolidated | API key required |
| sfp_whoisology | ✅ Consolidated | API key required |
| sfp_whoxy | ✅ Consolidated | API key required |

#### Search Engine Modules → `sfp_unified_search_engines`
| Legacy Module | Status | Notes |
|--------------|---------|--------|
| sfp_bingsearch | ✅ Consolidated | API key required |
| sfp_duckduckgo | ✅ Consolidated | No API key needed |
| sfp_flickr | ✅ Consolidated | API key required |
| sfp_github | ✅ Consolidated | API key optional |
| sfp_googlesearch | ✅ Consolidated | API key required |
| sfp_stackoverflow | ✅ Consolidated | |
| sfp_wikipediaedits | ✅ Consolidated | |

#### Async-Enhanced Modules
| Module | Enhancement | Performance Gain |
|--------|-------------|------------------|
| sfp_shodan_async | Full async rewrite | 10-50x faster |
| sfp_virustotal_async | Batch processing | 5-20x faster |
| sfp_censys_async | Concurrent queries | 10-30x faster |
| sfp_greynoise_async | Async HTTP client | 5-15x faster |

### Archived Modules
Modules moved to `archived_modules/` are deprecated but can be manually restored if needed:
```bash
# Restore specific archived module
cp archived_modules/sfp_module_name.py modules/
```

## Configuration Migration

### Automatic Migrations
These settings are automatically migrated:
- Database location
- API keys
- Scan history
- Module configurations
- User preferences

### Manual Configuration Updates

#### 1. Proxy Settings
If using Tor for .onion sites:
```bash
# Install and configure Tor
python install_tools.py --install tor
python configure_tor.py
```

#### 2. Thread Pool Settings
BE edition supports higher concurrency:
```python
# Legacy setting
'_maxthreads': 3

# BE recommended
'_maxthreads': 5  # or higher based on system resources
```

#### 3. Timeout Settings
Adjust for async operations:
```python
# Legacy
'_fetchtimeout': 5

# BE recommended for Tor
'_fetchtimeout': 30
```

## API Key Migration

### Unified Module API Keys
API keys are now configured per service, not per module:

| Service | Legacy Modules | BE Configuration |
|---------|---------------|------------------|
| Shodan | sfp_shodan | sfp_shodan_async |
| VirusTotal | sfp_virustotal | sfp_virustotal_async |
| IPStack | sfp_ipstack | sfp_unified_ip_info → IPStack |
| Abstract API | sfp_abstractapi | sfp_unified_ip_info → Abstract |

### Migration Steps
1. Start SpiderFoot BE web interface
2. Navigate to Settings → Module Settings
3. Configure API keys for each service
4. Keys are automatically used by all relevant modules

## Custom Module Migration

### For Custom Modules
1. **Copy custom modules** to BE modules directory:
   ```bash
   cp /path/to/legacy/modules/sfp_custom_*.py ./modules/
   ```

2. **Update imports** if needed:
   ```python
   # Legacy
   from sflib import SpiderFoot
   
   # BE (same, but verify)
   from sflib import SpiderFoot
   ```

3. **Test compatibility**:
   ```bash
   python sf.py -M | grep custom
   ```

### Converting to Async (Optional)
To convert custom modules to async:

```python
# Legacy synchronous module
class sfp_custom(SpiderFootPlugin):
    def handleEvent(self, event):
        data = self.fetchUrl(url)
        # Process data

# BE async module
from spiderfoot.plugin_async import AsyncSpiderFootPlugin

class sfp_custom_async(AsyncSpiderFootPlugin):
    async def handleEvent_async(self, event):
        data = await self.fetchUrl_async(url)
        # Process data
```

## Post-Migration Verification

### 1. Verify Module Loading
```bash
# List all modules
python sf.py -M

# Verify unified modules appear:
# - sfp_unified_dns_filters
# - sfp_unified_ip_info
# - sfp_unified_search_engines
```

### 2. Test Scan Functionality
```bash
# Basic scan test
python sf.py -s example.com -m sfp__stor_db -q

# Test unified modules
python sf.py -s example.com -m sfp_unified_dns_filters,sfp_unified_ip_info -q
```

### 3. Verify API Keys
```python
# Test API key functionality
python sf.py -s example.com -m sfp_shodan_async -q
# Should use Shodan API if key is configured
```

### 4. Check Database Integrity
```sql
# Via Web UI or sqlite3
SELECT COUNT(*) FROM tbl_scan_config;  -- Should show existing scans
SELECT COUNT(*) FROM tbl_scan_results; -- Should show historical results
```

### 5. Performance Comparison
Run identical scans on legacy and BE:
```bash
# Time a scan
time python sf.py -s example.com -m sfp_shodan_async,sfp_virustotal_async -q

# Compare with legacy timing
# BE should be 5-50x faster for async modules
```

## Rollback Plan

If issues arise, you can rollback:

### 1. Stop SpiderFoot BE
```bash
# Stop any running processes
pkill -f "python sf.py"
```

### 2. Restore Database
```bash
# Only if database was modified
cp ~/.spiderfoot/spiderfoot.db.backup ~/.spiderfoot/spiderfoot.db
```

### 3. Return to Legacy
```bash
cd /path/to/legacy/spiderfoot
python sf.py -l 127.0.0.1:5001
```

## Troubleshooting Migration Issues

### Module Not Found
```
ERROR: Module sfp_example not found
```
**Solution**: Check if module was consolidated:
- Look in `archived_modules/` directory
- Check module mapping table above
- Use unified module instead

### API Key Not Working
```
ERROR: API key not configured for service
```
**Solution**: 
- Reconfigure in Settings → Module Settings
- Ensure key is set for the service, not individual module

### Performance Not Improved
**Check**:
- Using async modules (`*_async`)
- Thread pool settings increased
- Network/proxy not bottlenecking

### Database Errors
```
ERROR: Database schema mismatch
```
**Solution**:
- Use original database without modifications
- Let SpiderFoot BE handle any updates
- Check permissions on database file

## Migration Best Practices

1. **Test First**: Run BE in parallel with legacy before full migration
2. **Gradual Migration**: Migrate one workflow at a time
3. **Monitor Performance**: Compare scan times and results
4. **Document Changes**: Keep notes on any custom modifications
5. **Train Users**: Ensure team knows about consolidated modules

## Support Resources

- **Documentation**: See README_BE.md
- **Issues**: GitHub issue tracker
- **Legacy Reference**: Keep legacy docs for comparison
- **Community**: SpiderFoot Discord/Slack

---

## Quick Reference Card

### Module Name Changes
```
Legacy: sfp_shodan       → BE: sfp_shodan_async
Legacy: sfp_ipstack      → BE: sfp_unified_ip_info
Legacy: sfp_duckduckgo   → BE: sfp_unified_search_engines
Legacy: sfp_quad9        → BE: sfp_unified_dns_filters
```

### Command Equivalents
```bash
# Legacy
python sf.py -m sfp_ipstack,sfp_abstractapi,sfp_blockchain

# BE (equivalent)
python sf.py -m sfp_unified_ip_info

# BE (performance)
python sf.py -m sfp_shodan_async,sfp_virustotal_async
```

### Configuration Locations
- Database: `~/.spiderfoot/spiderfoot.db`
- Logs: `~/.spiderfoot/logs/`
- Cache: `~/.spiderfoot/cache/`
- Third-party tools: `./tools/`