#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Neo4j Integration Framework

Provides seamless integration between SpiderFoot's async event system
and Neo4j graph database for real-time OSINT analysis.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from .neo4j_async import AsyncNeo4jClient, Neo4jConfig, Neo4jEventStreamer
from .event_queue_async import AsyncEventQueue, EventPriority
from .event import SpiderFootEvent


@dataclass
class GraphMetrics:
    """Graph database metrics and statistics."""
    total_nodes: int = 0
    total_relationships: int = 0
    events_streamed: int = 0
    events_failed: int = 0
    batch_imports: int = 0
    last_activity: float = 0.0


class Neo4jEventProcessor:
    """Process SpiderFoot events for Neo4j graph database."""
    
    def __init__(self, config: Neo4jConfig):
        self.config = config
        self.neo4j_client = None
        self.event_streamer = None
        self.metrics = GraphMetrics()
        self.log = logging.getLogger('spiderfoot.neo4j_processor')
        
        # Event filtering
        self.excluded_event_types: Set[str] = {
            'ROOT', 'SCAN_HOST_NOVALIDATE', 'SCAN_ERROR'
        }
        
        # Rate limiting for real-time streaming
        self._last_stream_time = 0.0
        self._stream_interval = 0.1  # Minimum 100ms between streams
        
    async def initialize(self) -> bool:
        """Initialize Neo4j processor."""
        try:
            # Initialize Neo4j client
            self.neo4j_client = AsyncNeo4jClient(self.config)
            await self.neo4j_client.connect()
            
            # Create indexes and constraints
            await self.neo4j_client.create_indexes()
            
            # Initialize event streamer
            self.event_streamer = Neo4jEventStreamer(self.neo4j_client)
            await self.event_streamer.start_streaming()
            
            self.log.info("Neo4j event processor initialized")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to initialize Neo4j processor: {e}")
            return False
            
    async def shutdown(self) -> None:
        """Shutdown Neo4j processor."""
        try:
            if self.event_streamer:
                await self.event_streamer.stop_streaming()
                
            if self.neo4j_client:
                await self.neo4j_client.close()
                
            self.log.info("Neo4j event processor shutdown complete")
            
        except Exception as e:
            self.log.error(f"Error during Neo4j processor shutdown: {e}")
            
    async def process_event(self, event: SpiderFootEvent, 
                          source_event: Optional[SpiderFootEvent] = None) -> bool:
        """Process single event for graph database."""
        # Filter excluded event types
        if event.eventType in self.excluded_event_types:
            return False
            
        try:
            # Apply rate limiting
            current_time = asyncio.get_event_loop().time()
            if current_time - self._last_stream_time < self._stream_interval:
                await asyncio.sleep(self._stream_interval)
                
            # Stream to Neo4j
            await self.event_streamer.queue_event(event, source_event)
            self._last_stream_time = current_time
            
            # Update metrics
            self.metrics.events_streamed += 1
            self.metrics.last_activity = current_time
            
            return True
            
        except Exception as e:
            self.log.error(f"Failed to process event {event.eventType}: {e}")
            self.metrics.events_failed += 1
            return False
            
    async def batch_import(self, events: List[SpiderFootEvent]) -> int:
        """Import events in batch mode."""
        if not self.neo4j_client:
            self.log.warning("Neo4j client not initialized for batch import")
            return 0
            
        try:
            # Filter events
            filtered_events = [
                e for e in events 
                if e.eventType not in self.excluded_event_types
            ]
            
            if not filtered_events:
                return 0
                
            # Import batch
            imported = await self.neo4j_client.import_events_batch(filtered_events)
            
            # Update metrics
            self.metrics.batch_imports += 1
            self.metrics.last_activity = asyncio.get_event_loop().time()
            
            self.log.info(f"Batch imported {imported} events to Neo4j")
            return imported
            
        except Exception as e:
            self.log.error(f"Batch import failed: {e}")
            return 0
            
    async def suggest_targets(self, algorithm: str = 'pagerank', 
                            target_type: str = 'DOMAIN_NAME',
                            limit: int = 20) -> List[Dict[str, Any]]:
        """Generate target suggestions using graph algorithms."""
        if not self.neo4j_client:
            return []
            
        try:
            suggestions = await self.neo4j_client.suggest_targets(
                target_type=target_type,
                algorithm=algorithm,
                limit=limit
            )
            
            self.log.info(f"Generated {len(suggestions)} target suggestions")
            return suggestions
            
        except Exception as e:
            self.log.error(f"Target suggestion failed: {e}")
            return []
            
    async def get_graph_statistics(self) -> Dict[str, Any]:
        """Get graph database statistics."""
        if not self.neo4j_client:
            return {}
            
        try:
            async with self.neo4j_client.driver.session(
                database=self.config.database
            ) as session:
                # Get node count
                result = await session.run("MATCH (n) RETURN count(n) as node_count")
                record = await result.single()
                node_count = record['node_count'] if record else 0
                
                # Get relationship count
                result = await session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
                record = await result.single()
                rel_count = record['rel_count'] if record else 0
                
                # Update metrics
                self.metrics.total_nodes = node_count
                self.metrics.total_relationships = rel_count
                
                return {
                    'nodes': node_count,
                    'relationships': rel_count,
                    'events_streamed': self.metrics.events_streamed,
                    'events_failed': self.metrics.events_failed,
                    'batch_imports': self.metrics.batch_imports,
                    'last_activity': self.metrics.last_activity
                }
                
        except Exception as e:
            self.log.error(f"Failed to get graph statistics: {e}")
            return {}


class Neo4jAsyncEventHandler:
    """Async event handler for integrating Neo4j with SpiderFoot's event system."""
    
    def __init__(self, event_queue: AsyncEventQueue, neo4j_config: Neo4jConfig):
        self.event_queue = event_queue
        self.neo4j_processor = Neo4jEventProcessor(neo4j_config)
        self.log = logging.getLogger('spiderfoot.neo4j_handler')
        
        # Event tracking
        self._processed_events: Set[str] = set()
        self._event_relationships: Dict[str, str] = {}  # child -> parent mapping
        
    async def initialize(self) -> bool:
        """Initialize the Neo4j event handler."""
        try:
            # Initialize Neo4j processor
            if not await self.neo4j_processor.initialize():
                return False
                
            # Register event handler with event queue
            await self._register_event_handlers()
            
            self.log.info("Neo4j async event handler initialized")
            return True
            
        except Exception as e:
            self.log.error(f"Failed to initialize Neo4j event handler: {e}")
            return False
            
    async def shutdown(self) -> None:
        """Shutdown the event handler."""
        await self.neo4j_processor.shutdown()
        
    async def _register_event_handlers(self) -> None:
        """Register handlers for different event types."""
        # Handle all event types by default
        self.event_queue.register_handler("*", self._handle_any_event)
        
        # Specific handlers for important event types
        domain_events = ['DOMAIN_NAME', 'INTERNET_NAME', 'AFFILIATE_DOMAIN_NAME']
        for event_type in domain_events:
            self.event_queue.register_handler(event_type, self._handle_domain_event)
            
        email_events = ['EMAILADDR', 'AFFILIATE_EMAILADDR']
        for event_type in email_events:
            self.event_queue.register_handler(event_type, self._handle_email_event)
            
    async def _handle_any_event(self, event: SpiderFootEvent) -> None:
        """Handle any SpiderFoot event."""
        try:
            # Skip if already processed
            event_hash = self._get_event_hash(event)
            if event_hash in self._processed_events:
                return
                
            # Find source event
            source_event = self._find_source_event(event)
            
            # Process event
            success = await self.neo4j_processor.process_event(event, source_event)
            
            if success:
                self._processed_events.add(event_hash)
                
                # Track parent-child relationship
                if source_event:
                    source_hash = self._get_event_hash(source_event)
                    self._event_relationships[event_hash] = source_hash
                    
        except Exception as e:
            self.log.error(f"Error handling event {event.eventType}: {e}")
            
    async def _handle_domain_event(self, event: SpiderFootEvent) -> None:
        """Handle domain-related events with special processing."""
        # Standard event processing
        await self._handle_any_event(event)
        
        # Additional domain-specific processing
        if event.eventType in ['DOMAIN_NAME', 'INTERNET_NAME']:
            try:
                # Generate target suggestions based on this domain
                suggestions = await self.neo4j_processor.suggest_targets(
                    algorithm='pagerank',
                    target_type='DOMAIN_NAME',
                    limit=5
                )
                
                # Log interesting suggestions
                for suggestion in suggestions[:3]:  # Top 3
                    if not suggestion['scanned']:
                        self.log.info(
                            f"Target suggestion: {suggestion['data']} "
                            f"(score: {suggestion['score']:.4f})"
                        )
                        
            except Exception as e:
                self.log.debug(f"Target suggestion failed for {event.data}: {e}")
                
    async def _handle_email_event(self, event: SpiderFootEvent) -> None:
        """Handle email-related events with special processing."""
        # Standard event processing
        await self._handle_any_event(event)
        
        # Extract domain from email for additional processing
        if '@' in event.data:
            domain = event.data.split('@')[1].lower()
            
            # Create virtual domain event for graph relationships
            try:
                # This helps with creating proper email -> domain relationships
                self.log.debug(f"Email {event.data} -> domain {domain}")
                
            except Exception as e:
                self.log.debug(f"Email domain processing failed: {e}")
                
    def _get_event_hash(self, event: SpiderFootEvent) -> str:
        """Get unique hash for an event."""
        import hashlib
        event_str = f"{event.eventType}:{event.data}:{getattr(event, 'module', '')}"
        return hashlib.sha256(event_str.encode('utf-8')).hexdigest()
        
    def _find_source_event(self, event: SpiderFootEvent) -> Optional[SpiderFootEvent]:
        """Find the source event for relationship creation."""
        # SpiderFoot events should have sourceEvent attribute
        if hasattr(event, 'sourceEvent') and event.sourceEvent:
            return event.sourceEvent
            
        # Fallback: try to find based on event chain
        if hasattr(event, 'sourceEventHash') and event.sourceEventHash:
            # Would need access to event storage to resolve this
            pass
            
        return None
        
    async def get_metrics(self) -> Dict[str, Any]:
        """Get processing metrics."""
        graph_stats = await self.neo4j_processor.get_graph_statistics()
        
        return {
            'processed_events': len(self._processed_events),
            'tracked_relationships': len(self._event_relationships),
            'graph_statistics': graph_stats
        }


class Neo4jScanManager:
    """Manage Neo4j integration for entire SpiderFoot scans."""
    
    def __init__(self, neo4j_config: Neo4jConfig):
        self.config = neo4j_config
        self.active_handlers: Dict[str, Neo4jAsyncEventHandler] = {}
        self.log = logging.getLogger('spiderfoot.neo4j_scan_manager')
        
    async def start_scan_integration(self, scan_id: str, 
                                   event_queue: AsyncEventQueue) -> bool:
        """Start Neo4j integration for a scan."""
        try:
            if scan_id in self.active_handlers:
                self.log.warning(f"Neo4j integration already active for scan {scan_id}")
                return True
                
            # Create event handler for this scan
            handler = Neo4jAsyncEventHandler(event_queue, self.config)
            
            if await handler.initialize():
                self.active_handlers[scan_id] = handler
                self.log.info(f"Neo4j integration started for scan {scan_id}")
                return True
            else:
                self.log.error(f"Failed to start Neo4j integration for scan {scan_id}")
                return False
                
        except Exception as e:
            self.log.error(f"Error starting Neo4j integration for scan {scan_id}: {e}")
            return False
            
    async def stop_scan_integration(self, scan_id: str) -> bool:
        """Stop Neo4j integration for a scan."""
        try:
            handler = self.active_handlers.get(scan_id)
            if not handler:
                self.log.warning(f"No active Neo4j integration for scan {scan_id}")
                return True
                
            await handler.shutdown()
            del self.active_handlers[scan_id]
            
            self.log.info(f"Neo4j integration stopped for scan {scan_id}")
            return True
            
        except Exception as e:
            self.log.error(f"Error stopping Neo4j integration for scan {scan_id}: {e}")
            return False
            
    async def get_scan_metrics(self, scan_id: str) -> Dict[str, Any]:
        """Get metrics for a specific scan."""
        handler = self.active_handlers.get(scan_id)
        if not handler:
            return {}
            
        return await handler.get_metrics()
        
    async def shutdown_all(self) -> None:
        """Shutdown all active integrations."""
        for scan_id in list(self.active_handlers.keys()):
            await self.stop_scan_integration(scan_id)
            
        self.log.info("All Neo4j integrations shut down")