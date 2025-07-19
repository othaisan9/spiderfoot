# 🦇 SpiderFoot BE Neo4j Integration Guide

## Overview

SpiderFoot BE v0.2 introduces comprehensive **Neo4j graph database integration** that transforms OSINT investigations through intelligent relationship mapping and advanced graph analytics.

### 🌟 Key Features

- **Real-time Event Streaming** - Live graph updates during scans
- **Async Architecture** - High-performance concurrent processing  
- **Graph Algorithms** - PageRank, centrality analysis, target suggestions
- **Interactive Visualization** - D3.js-powered graph explorer
- **Intelligence Correlation** - Discover hidden relationships

---

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Neo4j dependencies
pip install -r requirements_neo4j.txt

# Or install manually
pip install neo4j>=5.20.0 py2neo>=2021.2.4 tld>=0.13.0
```

### 2. Docker Deployment (Recommended)

```bash
# Launch complete stack
docker-compose -f docker-compose.neo4j.yml up -d

# Verify services
docker-compose -f docker-compose.neo4j.yml ps
```

**Services:**
- **Neo4j Database**: http://localhost:7474 (neo4j/spiderfoot)
- **SpiderFoot BE**: http://localhost:5001
- **Redis Cache**: localhost:6379

### 3. Manual Neo4j Setup

```bash
# Download and start Neo4j
wget https://neo4j.com/artifact.php?name=neo4j-community-5.20.0-unix.tar.gz
tar -xzf neo4j-community-*.tar.gz
cd neo4j-community-*/

# Install required plugins
./bin/neo4j-admin dbms set-initial-password spiderfoot
echo "dbms.security.procedures.unrestricted=apoc.*,gds.*" >> conf/neo4j.conf
echo "dbms.security.procedures.allowlist=apoc.*,gds.*" >> conf/neo4j.conf

# Start database
./bin/neo4j start
```

### 4. Enable Neo4j Module

```bash
# In SpiderFoot Web UI:
# 1. Go to Settings → Modules
# 2. Enable "Neo4j Graph Database"
# 3. Configure connection settings:
#    - URI: bolt://localhost:7687
#    - Username: neo4j
#    - Password: spiderfoot
```

---

## 🔧 Configuration

### Module Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `neo4j_uri` | `bolt://localhost:7687` | Neo4j connection URI |
| `neo4j_username` | `neo4j` | Database username |
| `neo4j_password` | `spiderfoot` | Database password |
| `enable_realtime` | `True` | Real-time event streaming |
| `enable_batch_import` | `True` | Batch import historical data |
| `batch_size` | `1000` | Events per batch |
| `suggest_targets` | `False` | Generate target suggestions |
| `target_suggestion_algorithm` | `pagerank` | Algorithm for suggestions |

### Environment Variables

```bash
# Docker environment
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=spiderfoot

# Performance tuning
NEO4J_MAX_CONNECTIONS=10
NEO4J_CONNECTION_TIMEOUT=30.0
```

---

## 📊 Graph Analysis Features

### 1. Real-time Event Streaming

Every SpiderFoot event automatically creates graph nodes and relationships:

```python
# Example: Domain discovery creates hierarchy
DOMAIN_NAME: example.com
  └── INTERNET_NAME: subdomain.example.com
      └── EMAILADDR: user@subdomain.example.com
          └── IP_ADDRESS: 192.168.1.100
```

### 2. Graph Algorithms

**PageRank Analysis**
- Identifies most important entities in investigation
- Higher scores = more connected/central nodes
- Best for finding key infrastructure

**Betweenness Centrality**
- Finds entities that bridge different parts of network
- Identifies critical connection points
- Useful for understanding information flow

**Closeness Centrality**  
- Measures how quickly entity can reach all others
- High scores = efficient network position
- Good for identifying coordination centers

### 3. Target Suggestions

Based on graph analysis, the system suggests new investigation targets:

```cypher
# Example Cypher query for suggestions
CALL gds.pageRank.stream('investigation_graph')
YIELD nodeId, score
RETURN gds.util.asNode(nodeId) AS entity, score
WHERE entity.scanned = false
ORDER BY score DESC
LIMIT 10
```

---

## 🎨 Visualization Interface

### Accessing Graph Visualization

1. **Complete a scan** with Neo4j module enabled
2. **Go to scan results** page  
3. **Click "Graph Analysis"** tab
4. **Explore interactive graph** with controls

### Visualization Features

- **Zoom/Pan** - Mouse wheel and drag
- **Node Selection** - Click nodes for details
- **Algorithm Toggle** - Switch between analysis types
- **Type Filtering** - Show specific entity types
- **Export Options** - Save graph data

### Graph Navigation

| Action | Method |
|--------|--------|
| **Zoom** | Mouse wheel |
| **Pan** | Click and drag background |
| **Select Node** | Click on node |
| **Node Details** | Click selected node |
| **Reset View** | Reset Zoom button |
| **Focus Node** | Double-click node |

---

## 🔍 Advanced Usage

### 1. Custom Cypher Queries

Access Neo4j Browser at http://localhost:7474:

```cypher
-- Find all domains with high risk scores
MATCH (d:DOMAIN_NAME)
WHERE d.risk > 75
RETURN d.data, d.risk, d.confidence
ORDER BY d.risk DESC

-- Discover email patterns
MATCH (e:EMAILADDR)-[:PARENT_DOMAIN]->(d:INTERNET_NAME)
RETURN d.data as domain, count(e) as email_count
ORDER BY email_count DESC

-- Find affiliate relationships
MATCH (a)-[r]->(b)
WHERE a.affiliate = true OR b.affiliate = true
RETURN a.data, type(r), b.data
```

### 2. API Integration

```python
# Access graph data via API
import requests

# Get graph data for scan
response = requests.get(f'/api/neo4j/graph/{scan_id}')
graph_data = response.json()

# Get target suggestions
response = requests.get(f'/api/neo4j/suggestions/{scan_id}')
suggestions = response.json()

# Get graph statistics
response = requests.get(f'/api/neo4j/statistics/{scan_id}')
stats = response.json()
```

### 3. Batch Data Import

```python
# Import existing SpiderFoot data
from spiderfoot.neo4j_async import AsyncNeo4jClient, Neo4jConfig

config = Neo4jConfig(uri="bolt://localhost:7687")
async with AsyncNeo4jClient(config) as client:
    # Import scan events
    events = load_spiderfoot_events(scan_id)
    imported = await client.import_events_batch(events)
    print(f"Imported {imported} events to graph")
```

---

## 🚀 Performance Optimization

### 1. Memory Configuration

**Neo4j Settings** (neo4j.conf):
```
dbms.memory.heap.initial_size=1G
dbms.memory.heap.max_size=4G
dbms.memory.pagecache.size=2G
```

**SpiderFoot Settings**:
```python
# Async processing limits
MAX_CONCURRENT_EVENTS = 100
BATCH_SIZE = 1000
CONNECTION_POOL_SIZE = 10
```

### 2. Index Optimization

```cypher
-- Create performance indexes
CREATE INDEX FOR (n:DOMAIN_NAME) ON (n.data);
CREATE INDEX FOR (n:INTERNET_NAME) ON (n.data);
CREATE INDEX FOR (n:EMAILADDR) ON (n.data);
CREATE INDEX FOR (n:IP_ADDRESS) ON (n.data);

-- Composite indexes for queries
CREATE INDEX FOR (n:DOMAIN_NAME) ON (n.scanned, n.risk);
```

### 3. Query Optimization

```cypher
-- Use PROFILE to analyze query performance
PROFILE MATCH (d:DOMAIN_NAME)
WHERE d.risk > 50
RETURN d.data, d.risk

-- Use EXPLAIN for query planning
EXPLAIN MATCH (a)-[r]->(b)
WHERE a.scanned = true
RETURN count(r)
```

---

## 🛠️ Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check Neo4j status
docker-compose logs neo4j

# Verify network connectivity
telnet localhost 7687
```

**2. Memory Issues**
```bash
# Increase Neo4j memory
echo "dbms.memory.heap.max_size=4G" >> neo4j.conf

# Monitor memory usage
docker stats spiderfoot-neo4j
```

**3. Slow Queries**
```cypher
-- Check for missing indexes
CALL db.indexes();

-- Analyze slow queries
CALL dbms.listQueries();
```

**4. Import Errors**
```python
# Check event format
print(f"Event type: {event.eventType}")
print(f"Event data: {event.data}")

# Verify constraints
SHOW CONSTRAINTS;
```

### Debug Mode

```bash
# Enable debug logging
export SPIDERFOOT_DEBUG=1
export NEO4J_DEBUG=1

# Check logs
tail -f logs/spiderfoot.log | grep neo4j
```

---

## 📈 Use Cases

### 1. Infrastructure Mapping

**Scenario**: Map complete digital infrastructure for a target organization

**Process**:
1. Start scan with multiple target domains
2. Enable Neo4j real-time streaming
3. Watch graph build relationships automatically
4. Use PageRank to identify core infrastructure
5. Export findings for reporting

### 2. Threat Hunting

**Scenario**: Investigate suspicious domain relationships

**Process**:
1. Import IOC domains to SpiderFoot
2. Run comprehensive scans with affiliate detection
3. Use graph analysis to find connected infrastructure
4. Apply risk scoring through centrality analysis
5. Generate investigation leads

### 3. OSINT Correlation

**Scenario**: Connect disparate intelligence sources

**Process**:
1. Import data from multiple OSINT sources
2. Use graph relationships to find connections
3. Apply machine learning on graph features
4. Discover non-obvious relationships
5. Generate intelligence reports

---

## 🔮 Advanced Features (v0.3+)

### Planned Enhancements

- **Machine Learning Integration** - Automated threat classification
- **Time-series Analysis** - Track infrastructure changes over time
- **Multi-tenant Support** - Isolated graphs per investigation
- **Federation** - Connect multiple Neo4j instances
- **Real-time Alerts** - Automated notifications on discoveries

### Community Contributions

- **Custom Algorithms** - Implement domain-specific graph algorithms
- **Visualization Plugins** - Create specialized visualization modes
- **Data Connectors** - Integrate additional OSINT sources
- **Export Formats** - Support for various intelligence formats

---

## 📚 Resources

### Documentation
- **Neo4j Documentation**: https://neo4j.com/docs/
- **Cypher Query Language**: https://neo4j.com/docs/cypher-manual/
- **Graph Data Science**: https://neo4j.com/docs/graph-data-science/

### Training
- **Neo4j GraphAcademy**: https://graphacademy.neo4j.com/
- **OSINT Graph Analysis**: Custom training materials

### Community
- **SpiderFoot BE GitHub**: Issues and discussions
- **Neo4j Community**: https://community.neo4j.com/
- **Graph Analytics Forum**: Specialized OSINT discussions

---

**🦇 SpiderFoot BE - When Graph Intelligence Meets OSINT** 🦇

*Powered by SpiderFoot | Enhanced with Neo4j Graph Technology*