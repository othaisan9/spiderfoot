# 🦇 SpiderFoot BE API Reference

## Overview

SpiderFoot BE provides a comprehensive RESTful API for programmatic access to OSINT scanning capabilities, async framework features, and Neo4j graph analysis.

**Base URL**: `http://localhost:5001/api`  
**Authentication**: API Key (optional, see Security section)  
**Content-Type**: `application/json`

---

## 📋 **Table of Contents**

1. [Core Scanning API](#core-scanning-api)
2. [Async Framework API](#async-framework-api)  
3. [Neo4j Graph API](#neo4j-graph-api)
4. [Module Management API](#module-management-api)
5. [Statistics and Monitoring](#statistics-and-monitoring)
6. [Authentication & Security](#authentication--security)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)

---

## 🕷️ **Core Scanning API**

### **Start New Scan**
```http
POST /api/scans
Content-Type: application/json

{
  "target": "example.com",
  "modules": ["sfp_dns", "sfp_whois", "sfp_neo4j_graph"],
  "scan_name": "Example Investigation",
  "scan_type": "passive",
  "use_async": true
}
```

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "status": "starting",
  "target": "example.com",
  "modules_enabled": 45,
  "estimated_duration": "10-15 minutes",
  "async_enabled": true,
  "neo4j_enabled": true
}
```

### **Get Scan Status**
```http
GET /api/scans/{scan_id}/status
```

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "status": "running",
  "progress": 67.5,
  "events_found": 1247,
  "modules_completed": 32,
  "modules_total": 45,
  "estimated_remaining": "5 minutes",
  "async_stats": {
    "concurrent_operations": 15,
    "queue_size": 234,
    "events_per_second": 12.4
  }
}
```

### **Get Scan Results**
```http
GET /api/scans/{scan_id}/results?format=json&limit=1000&offset=0
```

**Query Parameters:**
- `format`: `json`, `csv`, `xml` (default: `json`)
- `limit`: Results per page (default: 1000, max: 10000)
- `offset`: Pagination offset (default: 0)
- `event_type`: Filter by event type (optional)
- `confidence_min`: Minimum confidence score (0-100)
- `risk_min`: Minimum risk score (0-100)

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "total_results": 1247,
  "page": 1,
  "results": [
    {
      "event_id": "evt_001",
      "event_type": "DOMAIN_NAME",
      "data": "subdomain.example.com",
      "module": "sfp_dns",
      "confidence": 100,
      "risk": 25,
      "generated": "2025-01-19T19:45:32.123Z",
      "source_event": "evt_000"
    }
  ]
}
```

### **Stop Scan**
```http
POST /api/scans/{scan_id}/stop
```

### **Delete Scan**
```http
DELETE /api/scans/{scan_id}
```

---

## ⚡ **Async Framework API**

### **Get Async Statistics**
```http
GET /api/async/stats
```

**Response:**
```json
{
  "framework_version": "1.0.0",
  "active_scans": 3,
  "total_async_operations": 156,
  "event_queue_size": 234,
  "connection_pools": {
    "http_client": {
      "active_connections": 8,
      "max_connections": 50,
      "requests_per_second": 23.7
    },
    "dns_resolver": {
      "cache_hit_rate": 78.5,
      "queries_per_second": 15.2
    }
  },
  "performance_metrics": {
    "avg_response_time": "0.156s",
    "concurrent_operations": 15,
    "memory_usage": "245MB"
  }
}
```

### **Configure Async Settings**
```http
PUT /api/async/config
Content-Type: application/json

{
  "max_concurrent_operations": 20,
  "http_connection_pool_size": 50,
  "dns_cache_ttl": 3600,
  "rate_limit_requests_per_second": 10
}
```

### **Get Event Queue Status**
```http
GET /api/async/queue
```

**Response:**
```json
{
  "queue_size": 234,
  "processing_rate": 12.4,
  "priority_distribution": {
    "high": 45,
    "medium": 167,
    "low": 22
  },
  "workers": {
    "active": 8,
    "idle": 2,
    "total": 10
  }
}
```

---

## 🧠 **Neo4j Graph API**

### **Get Graph Data**
```http
GET /api/neo4j/graph/{scan_id}?algorithm=pagerank&nodeType=DOMAIN_NAME&limit=500
```

**Query Parameters:**
- `algorithm`: `pagerank`, `betweenness`, `closeness` (default: `pagerank`)
- `nodeType`: Filter by node type (optional)
- `limit`: Maximum nodes to return (default: 500, max: 5000)
- `min_score`: Minimum centrality score (optional)

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "algorithm": "pagerank",
  "nodes": [
    {
      "id": "node_001",
      "hash": "sha256_hash",
      "data": "example.com",
      "type": "DOMAIN_NAME",
      "confidence": 100,
      "risk": 45,
      "scanned": true,
      "affiliate": false,
      "centrality_score": 0.8745,
      "generated": "2025-01-19T19:45:32.123Z"
    }
  ],
  "relationships": [
    {
      "id": "rel_001",
      "source": "node_001",
      "target": "node_002",
      "type": "SUBDOMAIN_OF",
      "weight": 1.0
    }
  ],
  "statistics": {
    "total_nodes": 1247,
    "total_relationships": 2134,
    "node_types": {
      "DOMAIN_NAME": 234,
      "INTERNET_NAME": 567,
      "EMAILADDR": 123,
      "IP_ADDRESS": 234
    }
  }
}
```

### **Get Target Suggestions**
```http
GET /api/neo4j/suggestions/{scan_id}?algorithm=pagerank&limit=20&unscanned_only=true
```

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "algorithm": "pagerank",
  "suggestions": [
    {
      "data": "target.example.com",
      "type": "DOMAIN_NAME",
      "score": 0.7234,
      "confidence": 85,
      "risk": 60,
      "scanned": false,
      "reasons": [
        "High centrality score",
        "Connected to known infrastructure",
        "Multiple email associations"
      ]
    }
  ]
}
```

### **Run Graph Algorithm**
```http
POST /api/neo4j/algorithm/{scan_id}
Content-Type: application/json

{
  "algorithm": "pagerank",
  "parameters": {
    "iterations": 20,
    "damping_factor": 0.85
  },
  "node_filter": {
    "types": ["DOMAIN_NAME", "INTERNET_NAME"],
    "min_confidence": 50
  }
}
```

### **Get Node Relationships**
```http
GET /api/neo4j/nodes/{node_hash}/relationships?depth=3&types=SUBDOMAIN_OF,RESOLVED_TO
```

**Response:**
```json
{
  "node": {
    "hash": "sha256_hash",
    "data": "example.com",
    "type": "DOMAIN_NAME"
  },
  "relationships": [
    {
      "path": ["example.com", "subdomain.example.com", "192.168.1.1"],
      "types": ["SUBDOMAIN_OF", "RESOLVED_TO"],
      "distance": 2
    }
  ]
}
```

### **Export Graph Data**
```http
POST /api/neo4j/export/{scan_id}
Content-Type: application/json

{
  "format": "graphml",
  "include_attributes": true,
  "node_filter": {
    "min_confidence": 70
  }
}
```

---

## 🔧 **Module Management API**

### **List Available Modules**
```http
GET /api/modules
```

**Response:**
```json
{
  "total_modules": 156,
  "categories": {
    "Passive DNS": 12,
    "Search Engines": 15,
    "Social Networks": 8,
    "Data Export": 3
  },
  "modules": [
    {
      "name": "sfp_neo4j_graph",
      "description": "Neo4j Graph Database Integration",
      "category": "Data Export",
      "async_supported": true,
      "enabled": true,
      "version": "2.0.0"
    }
  ]
}
```

### **Get Module Configuration**
```http
GET /api/modules/{module_name}/config
```

### **Update Module Configuration**
```http
PUT /api/modules/{module_name}/config
Content-Type: application/json

{
  "neo4j_uri": "bolt://localhost:7687",
  "enable_realtime": true,
  "batch_size": 1000
}
```

### **Enable/Disable Module**
```http
POST /api/modules/{module_name}/toggle
Content-Type: application/json

{
  "enabled": true
}
```

---

## 📊 **Statistics and Monitoring**

### **System Health**
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.2.0",
  "uptime": "5 days, 12:34:56",
  "services": {
    "core": "healthy",
    "async_framework": "healthy",
    "neo4j": "healthy",
    "database": "healthy"
  },
  "performance": {
    "cpu_usage": 34.5,
    "memory_usage": 67.2,
    "disk_usage": 23.8
  }
}
```

### **Performance Metrics**
```http
GET /api/metrics?timespan=1h&granularity=5m
```

**Response:**
```json
{
  "timespan": "1h",
  "granularity": "5m",
  "metrics": [
    {
      "timestamp": "2025-01-19T19:40:00Z",
      "scans_active": 3,
      "events_per_second": 12.4,
      "async_operations": 15,
      "memory_usage_mb": 245,
      "neo4j_queries_per_second": 5.2
    }
  ]
}
```

### **Get Scan Statistics**
```http
GET /api/scans/{scan_id}/statistics
```

**Response:**
```json
{
  "scan_id": "20250119194500.123456",
  "duration": "00:15:32",
  "events_total": 1247,
  "events_by_type": {
    "DOMAIN_NAME": 234,
    "IP_ADDRESS": 156,
    "EMAILADDR": 89
  },
  "modules_executed": 45,
  "async_performance": {
    "concurrent_peak": 20,
    "avg_response_time": "0.156s",
    "total_api_calls": 3456
  },
  "neo4j_statistics": {
    "nodes_created": 1247,
    "relationships_created": 2134,
    "graph_algorithms_run": 3
  }
}
```

---

## 🔐 **Authentication & Security**

### **Generate API Key**
```http
POST /api/auth/keys
Content-Type: application/json

{
  "name": "Investigation API Key",
  "permissions": ["scans:read", "scans:write", "neo4j:read"],
  "expires_in_days": 30
}
```

**Response:**
```json
{
  "api_key": "sfbe_1234567890abcdef",
  "name": "Investigation API Key",
  "permissions": ["scans:read", "scans:write", "neo4j:read"],
  "expires_at": "2025-02-18T19:45:32.123Z",
  "created_at": "2025-01-19T19:45:32.123Z"
}
```

### **Using API Key**
```http
GET /api/scans
Authorization: Bearer sfbe_1234567890abcdef
```

### **Revoke API Key**
```http
DELETE /api/auth/keys/{api_key_id}
```

---

## ❌ **Error Handling**

### **Standard Error Response**
```json
{
  "error": {
    "code": "SCAN_NOT_FOUND",
    "message": "Scan with ID '20250119194500.123456' not found",
    "details": {
      "scan_id": "20250119194500.123456",
      "timestamp": "2025-01-19T19:45:32.123Z"
    }
  }
}
```

### **HTTP Status Codes**
- **200**: Success
- **201**: Created
- **400**: Bad Request (invalid parameters)
- **401**: Unauthorized (invalid API key)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found
- **429**: Too Many Requests (rate limited)
- **500**: Internal Server Error
- **503**: Service Unavailable

### **Common Error Codes**
- `INVALID_TARGET`: Target format is invalid
- `MODULE_NOT_FOUND`: Specified module doesn't exist
- `SCAN_NOT_FOUND`: Scan ID doesn't exist
- `NEO4J_UNAVAILABLE`: Neo4j database connection failed
- `ASYNC_QUEUE_FULL`: Event queue is at capacity
- `RATE_LIMIT_EXCEEDED`: API rate limit exceeded

---

## ⏱️ **Rate Limiting**

### **Rate Limit Headers**
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642619152
X-RateLimit-Window: 3600
```

### **Rate Limits by Endpoint**
| Endpoint Category | Requests per Hour | Burst Limit |
|-------------------|-------------------|-------------|
| **Scan Operations** | 100 | 10 |
| **Graph API** | 1000 | 50 |
| **Statistics** | 500 | 25 |
| **Configuration** | 50 | 5 |

### **Rate Limit Response**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded for this endpoint",
    "details": {
      "limit": 100,
      "window": "1 hour",
      "reset_at": "2025-01-19T20:45:32.123Z"
    }
  }
}
```

---

## 💡 **Usage Examples**

### **Python Client Example**
```python
import requests
import json

class SpiderFootBEClient:
    def __init__(self, base_url, api_key=None):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def start_scan(self, target, modules=None):
        data = {
            "target": target,
            "modules": modules or ["sfp_dns", "sfp_neo4j_graph"],
            "use_async": True
        }
        response = requests.post(
            f"{self.base_url}/api/scans",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def get_graph_data(self, scan_id, algorithm="pagerank"):
        response = requests.get(
            f"{self.base_url}/api/neo4j/graph/{scan_id}",
            headers=self.headers,
            params={"algorithm": algorithm}
        )
        return response.json()

# Usage
client = SpiderFootBEClient("http://localhost:5001")
scan = client.start_scan("example.com")
graph_data = client.get_graph_data(scan["scan_id"])
```

### **JavaScript Client Example**
```javascript
class SpiderFootBEClient {
    constructor(baseUrl, apiKey = null) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Content-Type': 'application/json'
        };
        if (apiKey) {
            this.headers['Authorization'] = `Bearer ${apiKey}`;
        }
    }
    
    async startScan(target, modules = ['sfp_dns', 'sfp_neo4j_graph']) {
        const response = await fetch(`${this.baseUrl}/api/scans`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                target: target,
                modules: modules,
                use_async: true
            })
        });
        return await response.json();
    }
    
    async getGraphData(scanId, algorithm = 'pagerank') {
        const response = await fetch(
            `${this.baseUrl}/api/neo4j/graph/${scanId}?algorithm=${algorithm}`,
            { headers: this.headers }
        );
        return await response.json();
    }
}

// Usage
const client = new SpiderFootBEClient('http://localhost:5001');
const scan = await client.startScan('example.com');
const graphData = await client.getGraphData(scan.scan_id);
```

---

## 🔄 **Webhooks (Coming Soon)**

### **Register Webhook**
```http
POST /api/webhooks
Content-Type: application/json

{
  "url": "https://your-server.com/webhook",
  "events": ["scan.completed", "neo4j.target_suggested"],
  "secret": "your_webhook_secret"
}
```

### **Webhook Event Example**
```json
{
  "event": "scan.completed",
  "scan_id": "20250119194500.123456",
  "timestamp": "2025-01-19T20:15:32.123Z",
  "data": {
    "duration": "00:15:32",
    "events_found": 1247,
    "neo4j_nodes_created": 1247
  }
}
```

---

**🦇 SpiderFoot BE API - Programmatic OSINT at Scale** 🦇

*For more examples and tutorials, visit our [GitHub repository](https://github.com/your-repo/spiderfoot-be)*