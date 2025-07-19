#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async Neo4j client for SpiderFoot BE integration.

Provides high-performance graph database operations with:
- Async connection pooling
- Real-time event streaming
- Batch processing optimization
- Graph algorithm integration
"""

import asyncio
import hashlib
import logging
import re
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple
from dataclasses import dataclass
import json

try:
    from neo4j import AsyncGraphDatabase, AsyncSession
    from neo4j.exceptions import ServiceUnavailable, TransientError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    
try:
    import tld
    TLD_AVAILABLE = True
except ImportError:
    TLD_AVAILABLE = False
from .event import SpiderFootEvent


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration."""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "spiderfoot"
    max_connections: int = 10
    connection_timeout: float = 30.0
    database: str = "neo4j"


class AsyncNeo4jClient:
    """High-performance async Neo4j client for SpiderFoot data."""
    
    # Regex for cleaning Neo4j labels
    SANITARY_REGEX = re.compile(r'\w+')
    
    def __init__(self, config: Neo4jConfig):
        """Initialize async Neo4j client."""
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j package required for graph database operations")
            
        self.config = config
        self.driver = None
        self.log = logging.getLogger('spiderfoot.neo4j_async')
        self._uniqueness_constraints = set()
        self._connection_pool_size = 0
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.config.uri,
                auth=(self.config.username, self.config.password),
                max_connection_pool_size=self.config.max_connections,
                connection_timeout=self.config.connection_timeout
            )
            
            # Test connection
            await self.driver.verify_connectivity()
            self.log.info(f"Connected to Neo4j at {self.config.uri}")
            
        except ServiceUnavailable as e:
            raise ConnectionError(f"Unable to connect to Neo4j at {self.config.uri}: {e}")
            
    async def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            self.log.info("Neo4j connection closed")
            
    async def clear_database(self) -> None:
        """Clear entire Neo4j database."""
        async with self.driver.session(database=self.config.database) as session:
            # Delete relationships first
            await session.run("MATCH (a)-[r]->() DELETE r")
            # Delete nodes
            await session.run("MATCH (a) DELETE a")
            
        self.log.info("Neo4j database cleared")
        
    async def create_indexes(self) -> None:
        """Create necessary indexes and constraints."""
        async with self.driver.session(database=self.config.database) as session:
            # Create constraints for common node types
            common_types = [
                'DOMAIN_NAME', 'INTERNET_NAME', 'EMAILADDR', 'IP_ADDRESS',
                'URL', 'AFFILIATE_DOMAIN_NAME', 'AFFILIATE_INTERNET_NAME'
            ]
            
            for node_type in common_types:
                try:
                    await session.run(
                        f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node_type}) "
                        f"REQUIRE n.hash IS UNIQUE"
                    )
                    self._uniqueness_constraints.add(node_type)
                except Exception as e:
                    self.log.debug(f"Constraint for {node_type} already exists or failed: {e}")
                    
        self.log.info(f"Created {len(self._uniqueness_constraints)} uniqueness constraints")
        
    async def import_events_batch(self, events: List[SpiderFootEvent], 
                                batch_size: int = 1000) -> int:
        """Import SpiderFoot events in batches."""
        total_imported = 0
        
        # Group events by hash for relationship building
        event_map = {self._hash_string(event.data): event for event in events}
        
        # Process in batches
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            imported = await self._import_batch(batch, event_map)
            total_imported += imported
            
            if i % (batch_size * 5) == 0:  # Log every 5 batches
                self.log.info(f"Imported {total_imported:,} events...")
                
        self.log.info(f"Batch import complete: {total_imported:,} events")
        return total_imported
        
    async def stream_event(self, event: SpiderFootEvent, 
                          source_event: Optional[SpiderFootEvent] = None) -> bool:
        """Stream single event to Neo4j in real-time."""
        try:
            async with self.driver.session(database=self.config.database) as session:
                # Create event node
                event_node = await self._create_event_node(session, event)
                
                # Create relationship if source event exists
                if source_event:
                    await self._create_relationship(session, source_event, event)
                    
                # Create domain hierarchy if applicable
                if event.eventType in ('INTERNET_NAME', 'EMAILADDR'):
                    await self._create_domain_hierarchy(session, event)
                    
                return True
                
        except Exception as e:
            self.log.error(f"Failed to stream event {event.eventType}: {e}")
            return False
            
    async def run_graph_algorithm(self, algorithm: str, 
                                 node_label: Optional[str] = None) -> AsyncGenerator[Tuple[Dict, float], None]:
        """Run graph algorithm and yield results."""
        async with self.driver.session(database=self.config.database) as session:
            # Project graph for algorithms
            await self._project_graph(session)
            
            # Algorithm mapping
            algorithm_queries = {
                'pagerank': """
                    CALL gds.pageRank.stream('spiderfoot_graph')
                    YIELD nodeId, score
                    RETURN gds.util.asNode(nodeId) AS node, score
                    ORDER BY score DESC
                """,
                'betweenness': """
                    CALL gds.betweenness.stream('spiderfoot_graph')
                    YIELD nodeId, score
                    RETURN gds.util.asNode(nodeId) AS node, score
                    ORDER BY score DESC
                """,
                'closeness': """
                    CALL gds.closeness.stream('spiderfoot_graph')
                    YIELD nodeId, centrality
                    RETURN gds.util.asNode(nodeId) AS node, centrality
                    ORDER BY centrality DESC
                """
            }
            
            query = algorithm_queries.get(algorithm.lower())
            if not query:
                raise ValueError(f"Unknown algorithm: {algorithm}")
                
            async for record in session.run(query):
                node_data = dict(record['node'])
                score = record.get('score', record.get('centrality', 0))
                
                # Filter by node label if specified
                if not node_label or node_label in record['node'].labels:
                    yield (node_data, score)
                    
    async def suggest_targets(self, target_type: str, algorithm: str = 'pagerank',
                            limit: int = 50) -> List[Dict[str, Any]]:
        """Suggest new targets based on graph centrality."""
        suggestions = []
        
        async for node_data, score in self.run_graph_algorithm(algorithm, target_type):
            if len(suggestions) >= limit:
                break
                
            suggestion = {
                'data': node_data.get('data', ''),
                'score': score,
                'scanned': node_data.get('scanned', False),
                'affiliate': node_data.get('affiliate', False),
                'confidence': node_data.get('confidence', 100),
                'risk': node_data.get('risk', 0)
            }
            suggestions.append(suggestion)
            
        return suggestions
        
    async def get_node_relationships(self, node_data: str, 
                                   max_depth: int = 3) -> Dict[str, Any]:
        """Get all relationships for a specific node."""
        async with self.driver.session(database=self.config.database) as session:
            query = """
                MATCH path = (start {data: $data})-[*1..$max_depth]-(connected)
                RETURN path
                LIMIT 1000
            """
            
            result = await session.run(query, data=node_data, max_depth=max_depth)
            
            nodes = set()
            relationships = set()
            
            async for record in result:
                path = record['path']
                for node in path.nodes:
                    nodes.add(json.dumps(dict(node), sort_keys=True))
                for rel in path.relationships:
                    relationships.add(json.dumps({
                        'type': rel.type,
                        'start': rel.start_node['data'],
                        'end': rel.end_node['data']
                    }, sort_keys=True))
                    
            return {
                'nodes': [json.loads(n) for n in nodes],
                'relationships': [json.loads(r) for r in relationships]
            }
            
    async def _import_batch(self, batch: List[SpiderFootEvent], 
                          event_map: Dict[str, SpiderFootEvent]) -> int:
        """Import a single batch of events."""
        async with self.driver.session(database=self.config.database) as session:
            tx = await session.begin_transaction()
            
            try:
                imported = 0
                
                for event in batch:
                    # Create event node
                    await self._create_event_node(tx, event)
                    
                    # Find source event for relationship
                    if hasattr(event, 'sourceEvent') and event.sourceEvent:
                        source_hash = self._hash_string(event.sourceEvent.data)
                        source_event = event_map.get(source_hash)
                        
                        if source_event:
                            await self._create_relationship(tx, source_event, event)
                            
                    # Create domain hierarchy
                    if event.eventType in ('INTERNET_NAME', 'EMAILADDR'):
                        await self._create_domain_hierarchy(tx, event)
                        
                    imported += 1
                    
                await tx.commit()
                return imported
                
            except Exception as e:
                await tx.rollback()
                self.log.error(f"Batch import failed: {e}")
                return 0
                
    async def _create_event_node(self, session, event: SpiderFootEvent) -> Dict[str, Any]:
        """Create a node for SpiderFoot event."""
        # Process event type (handle AFFILIATE_ prefix)
        event_type = event.eventType
        affiliate = False
        
        if event_type.startswith('AFFILIATE_'):
            event_type = event_type.replace('AFFILIATE_', '')
            affiliate = True
            
        # Sanitize for Neo4j label
        clean_type = self._sanitize_string(event_type)
        
        # Prepare data
        data = event.data
        if event_type in ('INTERNET_NAME', 'DOMAIN_NAME', 'EMAILADDR'):
            data = data.lower()
            
        # Create uniqueness constraint if needed
        if clean_type not in self._uniqueness_constraints:
            try:
                await session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{clean_type}) "
                    f"REQUIRE n.hash IS UNIQUE"
                )
                self._uniqueness_constraints.add(clean_type)
            except Exception:
                pass  # Constraint may already exist
                
        # Node properties
        properties = {
            'data': data,
            'hash': self._hash_string(data),
            'confidence': getattr(event, 'confidence', 100),
            'visibility': getattr(event, 'visibility', 100),
            'risk': getattr(event, 'risk', 0),
            'generated': getattr(event, 'generated', time.time()),
            'affiliate': affiliate,
            'scanned': not affiliate
        }
        
        # Create/merge node
        query = f"""
            MERGE (n:{clean_type} {{hash: $hash}})
            SET n += $properties
            RETURN n
        """
        
        result = await session.run(query, hash=properties['hash'], properties=properties)
        record = await result.single()
        return dict(record['n']) if record else {}
        
    async def _create_relationship(self, session, source_event: SpiderFootEvent, 
                                 target_event: SpiderFootEvent) -> None:
        """Create relationship between events."""
        source_hash = self._hash_string(source_event.data)
        target_hash = self._hash_string(target_event.data)
        
        # Determine relationship type (based on module or default)
        rel_type = getattr(target_event, 'module', 'DISCOVERED_BY')
        if rel_type.startswith('sfp_'):
            rel_type = rel_type[4:]  # Remove sfp_ prefix
        rel_type = self._sanitize_string(rel_type).upper()
        
        query = f"""
            MATCH (source {{hash: $source_hash}})
            MATCH (target {{hash: $target_hash}})
            MERGE (source)-[r:{rel_type}]->(target)
            RETURN r
        """
        
        await session.run(query, source_hash=source_hash, target_hash=target_hash)
        
    async def _create_domain_hierarchy(self, session, event: SpiderFootEvent) -> None:
        """Create domain hierarchy relationships."""
        data = event.data.lower()
        
        if event.eventType == 'EMAILADDR':
            # Extract domain from email
            domain = data.split('@')[-1]
            await self._create_parent_domain_relationship(session, data, domain, 'INTERNET_NAME')
        elif event.eventType == 'INTERNET_NAME':
            # Create parent domain relationships
            parts = data.split('.')
            if len(parts) > 2:
                parent_domain = '.'.join(parts[1:])
                if TLD_AVAILABLE:
                    domain_type = 'DOMAIN_NAME' if tld.is_tld(parent_domain) else 'INTERNET_NAME'
                else:
                    # Simple fallback: check if it contains only one dot (likely TLD)
                    domain_type = 'DOMAIN_NAME' if parent_domain.count('.') <= 1 else 'INTERNET_NAME'
                await self._create_parent_domain_relationship(session, data, parent_domain, domain_type)
                
    async def _create_parent_domain_relationship(self, session, child_data: str, 
                                               parent_data: str, parent_type: str) -> None:
        """Create PARENT_DOMAIN relationship."""
        child_hash = self._hash_string(child_data)
        parent_hash = self._hash_string(parent_data)
        
        # Create parent node
        parent_properties = {
            'data': parent_data,
            'hash': parent_hash,
            'generated': time.time()
        }
        
        clean_parent_type = self._sanitize_string(parent_type)
        
        query = f"""
            MATCH (child {{hash: $child_hash}})
            MERGE (parent:{clean_parent_type} {{hash: $parent_hash}})
            SET parent += $parent_properties
            MERGE (child)-[:PARENT_DOMAIN]->(parent)
        """
        
        await session.run(query, 
                         child_hash=child_hash, 
                         parent_hash=parent_hash,
                         parent_properties=parent_properties)
        
    async def _project_graph(self, session) -> None:
        """Project graph for algorithm execution."""
        # Drop existing projection
        try:
            await session.run("CALL gds.graph.drop('spiderfoot_graph')")
        except Exception:
            pass  # Graph doesn't exist
            
        # Create new projection
        await session.run("""
            CALL gds.graph.project('spiderfoot_graph', '*', '*')
        """)
        
    def _sanitize_string(self, s: str) -> str:
        """Sanitize string for Neo4j label/property names."""
        return ''.join(self.SANITARY_REGEX.findall('_'.join(str(s).split())))
        
    def _hash_string(self, s: str) -> str:
        """Generate SHA256 hash of string."""
        return hashlib.sha256(str(s).encode('utf-8')).hexdigest()


class Neo4jEventStreamer:
    """Real-time event streaming to Neo4j."""
    
    def __init__(self, neo4j_client: AsyncNeo4jClient):
        self.client = neo4j_client
        self.log = logging.getLogger('spiderfoot.neo4j_streamer')
        self._stream_queue = asyncio.Queue(maxsize=10000)
        self._streaming_task = None
        
    async def start_streaming(self) -> None:
        """Start background streaming task."""
        if self._streaming_task and not self._streaming_task.done():
            return
            
        self._streaming_task = asyncio.create_task(self._stream_worker())
        self.log.info("Neo4j event streaming started")
        
    async def stop_streaming(self) -> None:
        """Stop background streaming task."""
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
                
        self.log.info("Neo4j event streaming stopped")
        
    async def queue_event(self, event: SpiderFootEvent, 
                         source_event: Optional[SpiderFootEvent] = None) -> None:
        """Queue event for streaming to Neo4j."""
        try:
            self._stream_queue.put_nowait((event, source_event))
        except asyncio.QueueFull:
            self.log.warning("Neo4j stream queue full, dropping event")
            
    async def _stream_worker(self) -> None:
        """Background worker for streaming events."""
        while True:
            try:
                # Get event from queue with timeout
                event, source_event = await asyncio.wait_for(
                    self._stream_queue.get(), timeout=1.0
                )
                
                # Stream to Neo4j
                success = await self.client.stream_event(event, source_event)
                if success:
                    self._stream_queue.task_done()
                else:
                    self.log.warning(f"Failed to stream event: {event.eventType}")
                    
            except asyncio.TimeoutError:
                # Continue loop on timeout
                continue
            except asyncio.CancelledError:
                # Clean shutdown
                break
            except Exception as e:
                self.log.error(f"Stream worker error: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop