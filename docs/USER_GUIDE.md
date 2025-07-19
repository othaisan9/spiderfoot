# 🦇 SpiderFoot BE User Guide

## Welcome to SpiderFoot BE (BAT INTELLIGENCE Edition)

This comprehensive guide will help you master SpiderFoot BE's powerful OSINT capabilities, from basic scanning to advanced graph intelligence analysis.

---

## 📋 **Table of Contents**

1. [Getting Started](#getting-started)
2. [Basic OSINT Scanning](#basic-osint-scanning)
3. [Neo4j Graph Intelligence](#neo4j-graph-intelligence)
4. [Async Framework Features](#async-framework-features)
5. [Advanced Investigation Techniques](#advanced-investigation-techniques)
6. [Visualization and Analysis](#visualization-and-analysis)
7. [API Usage](#api-usage)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## 🚀 **Getting Started**

### **System Requirements**
- **OS**: Linux, macOS, Windows
- **Python**: 3.8+ 
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space
- **Network**: Internet access for OSINT data sources

### **Quick Installation**

#### **Option 1: Docker (Recommended)**
```bash
# Clone repository
git clone https://github.com/your-repo/spiderfoot-be
cd spiderfoot-be/spiderfoot

# Launch complete stack
docker-compose -f docker-compose.neo4j.yml up -d

# Access services
# SpiderFoot BE: http://localhost:5001
# Neo4j Browser: http://localhost:7474
```

#### **Option 2: Manual Installation**
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements_neo4j.txt

# Start SpiderFoot
python3 sf.py -l 0.0.0.0:5001
```

### **First Login**
1. Open web browser to http://localhost:5001
2. No authentication required by default (see Security section)
3. You'll see the SpiderFoot BE dashboard

---

## 🕷️ **Basic OSINT Scanning**

### **Starting Your First Scan**

#### **1. Navigate to New Scan**
- Click **"New Scan"** from the main menu
- Or go directly to `/newscan`

#### **2. Configure Scan Target**
```
Target Examples:
✅ Domain: example.com
✅ IP Address: 192.168.1.1
✅ Email: user@example.com
✅ Username: johndoe
✅ Bitcoin Address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

#### **3. Select Scan Type**
| Scan Type | Description | Use Cases |
|-----------|-------------|-----------|
| **Passive** | No direct contact with target | Stealth reconnaissance |
| **Footprint** | Minimal target interaction | Initial assessment |
| **Investigate** | Comprehensive data gathering | Detailed investigation |
| **All** | Maximum coverage | Thorough analysis |

#### **4. Choose Modules**
**Essential Modules for Beginners:**
- ✅ **DNS (Common)** - Basic DNS enumeration
- ✅ **Whois** - Domain registration info
- ✅ **Search Engines** - Public search results
- ✅ **Certificate Transparency** - SSL certificate data
- ✅ **Neo4j Graph Database** - Graph intelligence (NEW!)

**Advanced Modules:**
- **Shodan** - Internet-connected devices
- **VirusTotal** - Malware and threat intelligence
- **Have I Been Pwned** - Data breach information
- **Social Media** - Social network presence

### **Understanding Scan Results**

#### **Event Types**
| Event Type | Description | Example |
|------------|-------------|---------|
| `DOMAIN_NAME` | Discovered domains | `example.com` |
| `INTERNET_NAME` | Subdomains | `mail.example.com` |
| `IP_ADDRESS` | IP addresses | `192.168.1.1` |
| `EMAILADDR` | Email addresses | `admin@example.com` |
| `URL` | Web URLs | `https://example.com/page` |
| `AFFILIATE_*` | Related entities | Connected infrastructure |

#### **Confidence & Risk Scores**
- **Confidence (0-100)**: How certain we are about the data
- **Risk (0-100)**: Potential security concern level
- **Visibility (0-100)**: How easily discoverable the data is

---

## 🧠 **Neo4j Graph Intelligence**

### **Enabling Graph Analysis**

#### **1. Configure Neo4j Module**
```
Settings → Modules → Neo4j Graph Database

Required Settings:
- Neo4j URI: bolt://localhost:7687
- Username: neo4j
- Password: spiderfoot
- Enable Real-time: ✅
- Target Suggestions: ✅
```

#### **2. Neo4j Database Setup**
**Using Docker (Automatic):**
```bash
docker-compose -f docker-compose.neo4j.yml up -d
```

**Manual Setup:**
```bash
# Download Neo4j Community Edition
wget https://neo4j.com/artifact.php?name=neo4j-community-5.20.0-unix.tar.gz
tar -xzf neo4j-community-*.tar.gz
cd neo4j-community-*/

# Configure and start
./bin/neo4j-admin dbms set-initial-password spiderfoot
./bin/neo4j start

# Access Neo4j Browser at http://localhost:7474
```

### **Graph Intelligence Features**

#### **Real-time Graph Building**
As your scan progresses, watch the graph build automatically:
- **Nodes**: Entities discovered (domains, IPs, emails)
- **Relationships**: Connections between entities
- **Hierarchies**: Domain/subdomain structures
- **Cross-references**: Multi-source correlations

#### **Graph Analysis Algorithms**

**PageRank Analysis**
```
Purpose: Identify most important entities
Best for: Finding key infrastructure
Algorithm: Ranks nodes by connection importance
```

**Betweenness Centrality**
```
Purpose: Find bridge entities
Best for: Identifying critical connection points
Algorithm: Measures shortest path frequency
```

**Closeness Centrality**
```
Purpose: Find well-connected entities
Best for: Locating coordination centers
Algorithm: Measures average distance to all nodes
```

### **Using Graph Visualization**

#### **Accessing Graph View**
1. Complete a scan with Neo4j module enabled
2. Go to scan results page
3. Click **"Graph Analysis"** tab
4. Explore interactive visualization

#### **Graph Navigation**
| Action | Method |
|--------|--------|
| **Zoom** | Mouse wheel |
| **Pan** | Click & drag background |
| **Select Node** | Click on node |
| **Node Details** | Click selected node |
| **Algorithm Toggle** | Use dropdown menu |
| **Filter Nodes** | Select node type filter |

#### **Graph Analysis Workflow**
```
1. Start with PageRank view
   → Identify highest-scoring entities

2. Switch to Betweenness view  
   → Find critical connection points

3. Use Node Details panel
   → Examine specific entities

4. Apply filters
   → Focus on specific entity types

5. Generate target suggestions
   → Discover new investigation leads
```

---

## ⚡ **Async Framework Features**

### **Performance Benefits**
SpiderFoot BE's async architecture provides:
- **5-50x faster** API queries
- **Concurrent processing** of multiple targets
- **Intelligent rate limiting** respecting API limits
- **Connection pooling** for optimal resource usage

### **Monitoring Async Performance**

#### **Performance Dashboard**
```
Statistics → Performance Metrics

Key Metrics:
- Concurrent Operations: Current async tasks
- Events per Second: Processing rate
- Queue Size: Pending operations
- Memory Usage: Resource consumption
```

#### **Async Configuration**
```
Settings → Advanced → Async Framework

Tunable Parameters:
- Max Concurrent Operations: 10-50 (default: 20)
- HTTP Connection Pool: 20-100 (default: 50)
- DNS Cache TTL: 300-3600 seconds (default: 3600)
- Rate Limit: 1-100 req/sec per API (default: 10)
```

### **Async-Enabled Modules**
- ✅ **Shodan Async** - Concurrent IP intelligence
- ✅ **VirusTotal Async** - Parallel threat analysis
- ✅ **Censys Async** - High-speed scan data
- ✅ **Unified IP Info Async** - Multi-source geolocation

---

## 🔍 **Advanced Investigation Techniques**

### **Target Correlation**

#### **1. Multi-Domain Investigation**
```
Scenario: Investigate organization's digital footprint

Process:
1. Start with primary domain (company.com)
2. Enable Neo4j graph analysis
3. Run comprehensive scan
4. Analyze graph for related domains
5. Use target suggestions for expansion
6. Cross-reference findings
```

#### **2. Infrastructure Mapping**
```
Goal: Map complete infrastructure

Technique:
1. Identify seed domains/IPs
2. Use DNS enumeration modules
3. Analyze SSL certificate relationships
4. Map IP address ranges
5. Correlate hosting providers
6. Visualize in graph format
```

#### **3. Threat Intelligence Gathering**
```
Objective: Assess security posture

Approach:
1. Enable threat intelligence modules
2. Check breach databases
3. Analyze malware associations
4. Review certificate transparency logs
5. Assess risk scores in graph view
6. Generate threat summary
```

### **Custom Investigation Workflows**

#### **Stealth Reconnaissance**
```
Module Selection:
✅ Passive DNS only
✅ Certificate Transparency
✅ Search Engines (cached)
✅ Public registries
❌ Direct scanning modules
❌ Active enumeration

Configuration:
- Scan Type: Passive
- User-Agent: Randomized
- Rate Limiting: Conservative
```

#### **Comprehensive Assessment**
```
Module Selection:
✅ All DNS modules
✅ All search engines
✅ Social media modules
✅ Breach databases
✅ Threat intelligence
✅ Neo4j graph analysis

Configuration:
- Scan Type: All
- Async Framework: Enabled
- Target Suggestions: Enabled
```

---

## 🎨 **Visualization and Analysis**

### **Graph Visualization Features**

#### **Interactive Elements**
- **Node Colors**: Entity type identification
- **Node Sizes**: Risk or confidence-based sizing
- **Edge Thickness**: Relationship strength
- **Layout Algorithms**: Force-directed positioning
- **Clustering**: Automatic grouping of related entities

#### **Analysis Tools**
```
Toolbar Functions:
🔍 Zoom Controls
🎯 Focus on Node
📊 Algorithm Selection
🔧 Filter Options
💾 Export Data
📸 Save Screenshot
```

#### **Detail Panels**
```
Node Information:
- Entity Data
- Confidence Score
- Risk Assessment
- Discovery Source
- Relationship Count
- Connected Entities
```

### **Report Generation**

#### **Built-in Reports**
1. **Summary Report** - High-level findings overview
2. **Detailed Report** - Complete scan results
3. **Graph Analysis Report** - Centrality and relationships
4. **Risk Assessment** - Security-focused analysis
5. **Timeline Report** - Discovery chronology

#### **Export Formats**
- **JSON** - Programmatic access
- **CSV** - Spreadsheet analysis
- **XML** - Structured data exchange
- **GraphML** - Graph visualization tools
- **PDF** - Executive reports (coming soon)

---

## 🔌 **API Usage**

### **Getting Started with API**

#### **Authentication (Optional)**
```bash
# Generate API key
curl -X POST http://localhost:5001/api/auth/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "My API Key", "permissions": ["scans:read", "scans:write"]}'

# Use API key
curl -H "Authorization: Bearer your_api_key" \
  http://localhost:5001/api/scans
```

#### **Starting a Scan via API**
```bash
curl -X POST http://localhost:5001/api/scans \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "modules": ["sfp_dns", "sfp_neo4j_graph"],
    "scan_name": "API Test Scan",
    "use_async": true
  }'
```

#### **Getting Graph Data**
```bash
# Get graph visualization data
curl "http://localhost:5001/api/neo4j/graph/{scan_id}?algorithm=pagerank"

# Get target suggestions
curl "http://localhost:5001/api/neo4j/suggestions/{scan_id}"
```

### **Python SDK Example**
```python
import requests

class SpiderFootBE:
    def __init__(self, base_url="http://localhost:5001"):
        self.base_url = base_url
    
    def start_scan(self, target, modules=None):
        data = {
            "target": target,
            "modules": modules or ["sfp_dns", "sfp_neo4j_graph"],
            "use_async": True
        }
        response = requests.post(f"{self.base_url}/api/scans", json=data)
        return response.json()
    
    def get_graph_data(self, scan_id):
        response = requests.get(f"{self.base_url}/api/neo4j/graph/{scan_id}")
        return response.json()

# Usage
sf = SpiderFootBE()
scan = sf.start_scan("example.com")
graph = sf.get_graph_data(scan["scan_id"])
```

---

## 💡 **Best Practices**

### **Scan Configuration**

#### **Target Selection**
```
✅ DO:
- Use specific, relevant targets
- Verify target ownership/authorization
- Start with primary domains
- Use graph suggestions for expansion

❌ DON'T:
- Scan unauthorized targets
- Use overly broad wildcards
- Ignore rate limiting
- Skip graph analysis
```

#### **Module Selection**
```
For Speed:
- Focus on essential modules
- Enable async variants
- Use targeted scanning

For Completeness:
- Enable comprehensive module sets
- Include threat intelligence
- Use graph correlation
```

### **Performance Optimization**

#### **Async Framework Tuning**
```
High-Performance Setup:
- Max Concurrent Operations: 30-50
- HTTP Connection Pool: 100
- DNS Cache TTL: 3600
- Enable all async modules

Memory-Constrained Setup:
- Max Concurrent Operations: 10
- HTTP Connection Pool: 20
- Reduce batch sizes
- Focus on essential modules
```

#### **Neo4j Optimization**
```
Database Configuration:
- Heap Size: 2-4GB
- Page Cache: 1-2GB
- Connection Pool: 10-20
- Query Timeout: 30s

Index Creation:
- Node hash indexes
- Data property indexes
- Composite indexes for queries
```

### **Investigation Methodology**

#### **Structured Approach**
```
Phase 1: Initial Reconnaissance
- Target identification
- Basic enumeration
- Infrastructure mapping

Phase 2: Deep Analysis
- Graph relationship analysis
- Threat intelligence correlation
- Risk assessment

Phase 3: Expansion
- Target suggestions
- Related entity investigation
- Comprehensive coverage

Phase 4: Reporting
- Graph visualization
- Risk summarization
- Executive briefing
```

---

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Neo4j Connection Problems**
```
Problem: "Neo4j connection failed"
Solutions:
1. Verify Neo4j is running: docker ps
2. Check connection settings in module config
3. Test connection: curl http://localhost:7474
4. Review firewall settings
```

#### **Slow Performance**
```
Problem: Scans taking too long
Solutions:
1. Enable async framework
2. Increase concurrent operations
3. Use targeted module selection
4. Check API rate limits
```

#### **Memory Issues**
```
Problem: High memory usage
Solutions:
1. Reduce concurrent operations
2. Lower batch sizes
3. Enable result streaming
4. Restart services periodically
```

### **Debug Mode**
```bash
# Enable debug logging
export SPIDERFOOT_DEBUG=1
python3 sf.py -l 0.0.0.0:5001

# Check logs
tail -f logs/spiderfoot.log
```

### **Getting Help**
- **Documentation**: `/docs` directory
- **GitHub Issues**: Report bugs and feature requests
- **Community**: SpiderFoot forums and discussions
- **Professional Support**: Contact for enterprise assistance

---

## 📚 **Additional Resources**

### **Learning Materials**
- **OSINT Methodology**: Framework and techniques
- **Graph Theory**: Understanding network analysis
- **Threat Intelligence**: Advanced correlation methods
- **Neo4j Training**: Graph database fundamentals

### **Integration Examples**
- **SIEM Integration**: Forward results to security platforms
- **Automation Scripts**: Scheduled scanning workflows
- **Custom Modules**: Develop organization-specific modules
- **API Integrations**: Connect with existing tools

### **Community**
- **GitHub**: Source code and issues
- **Discord**: Real-time community support
- **Blog**: Latest features and techniques
- **Conferences**: OSINT and security events

---

**🦇 Welcome to the Future of OSINT Intelligence** 🦇

*SpiderFoot BE (BAT INTELLIGENCE Edition) - Where Speed Meets Intelligence*

---

*This guide covers SpiderFoot BE v0.2. For the latest updates and features, visit our [GitHub repository](https://github.com/your-repo/spiderfoot-be).*