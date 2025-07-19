#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpiderFoot Neo4j Graph Integration Module

Provides real-time graph database integration for SpiderFoot scanning results.
Creates intelligent relationship graphs and enables advanced graph analysis.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from spiderfoot import SpiderFootPlugin, SpiderFootHelpers
from spiderfoot.event import SpiderFootEvent
from spiderfoot.neo4j_async import AsyncNeo4jClient, Neo4jConfig, Neo4jEventStreamer


class sfp_neo4j_graph(SpiderFootPlugin):
    """SpiderFoot Neo4j Graph Integration Module."""

    meta = {
        'name': "Neo4j Graph Database",
        'summary': "Stream scan results to Neo4j graph database for advanced analysis and visualization.",
        'flags': ['slow', 'invoke'],
        'useCases': ['Investigate', 'Footprint', 'Passive'],
        'categories': ["Content Analysis"],
        'dataSource': {
            'website': "https://neo4j.com",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [
                "https://neo4j.com/docs/",
                "https://neo4j.com/developer/graph-data-science/"
            ],
            'description': "Graph database for storing and analyzing interconnected OSINT data."
        }
    }

    opts = {
        'neo4j_uri': 'bolt://localhost:7687',
        'neo4j_username': 'neo4j', 
        'neo4j_password': 'spiderfoot',
        'neo4j_database': 'neo4j',
        'max_connections': 10,
        'enable_realtime': True,
        'enable_batch_import': True,
        'batch_size': 1000,
        'create_indexes': True,
        'enable_domain_hierarchy': True,
        'enable_graph_algorithms': False,
        'suggest_targets': False,
        'target_suggestion_algorithm': 'pagerank',
        'max_target_suggestions': 50
    }

    optdescs = {
        'neo4j_uri': 'Neo4j database URI (bolt://localhost:7687)',
        'neo4j_username': 'Neo4j username',
        'neo4j_password': 'Neo4j password',
        'neo4j_database': 'Neo4j database name',
        'max_connections': 'Maximum concurrent connections to Neo4j',
        'enable_realtime': 'Enable real-time event streaming to graph',
        'enable_batch_import': 'Enable batch import of historical data',
        'batch_size': 'Number of events to import in each batch',
        'create_indexes': 'Automatically create indexes and constraints',
        'enable_domain_hierarchy': 'Create domain hierarchy relationships',
        'enable_graph_algorithms': 'Run graph algorithms for analysis',
        'suggest_targets': 'Generate target suggestions based on graph centrality',
        'target_suggestion_algorithm': 'Algorithm for target suggestions (pagerank, betweenness, closeness)',
        'max_target_suggestions': 'Maximum number of target suggestions to generate'
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        """Initialize the module."""
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False
        
        # Update options
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        # Validate required options
        if not self.opts.get('neo4j_uri'):
            self.sf.error("Neo4j URI is required")
            self.errorState = True
            return

        # Initialize Neo4j configuration
        self.config = Neo4jConfig(
            uri=self.opts['neo4j_uri'],
            username=self.opts['neo4j_username'],
            password=self.opts['neo4j_password'],
            database=self.opts['neo4j_database'],
            max_connections=self.opts['max_connections']
        )
        
        # Initialize components
        self.neo4j_client = None
        self.event_streamer = None
        self.scan_events = []  # Store events for batch processing
        
        self.sf.info(f"Neo4j Graph module initialized for {self.config.uri}")

    async def _initialize_neo4j(self):
        """Initialize Neo4j client and components."""
        if self.neo4j_client:
            return True
            
        try:
            self.neo4j_client = AsyncNeo4jClient(self.config)
            await self.neo4j_client.connect()
            
            # Create indexes if enabled
            if self.opts['create_indexes']:
                await self.neo4j_client.create_indexes()
                self.sf.info("Neo4j indexes and constraints created")
            
            # Initialize event streamer if real-time is enabled
            if self.opts['enable_realtime']:
                self.event_streamer = Neo4jEventStreamer(self.neo4j_client)
                await self.event_streamer.start_streaming()
                self.sf.info("Real-time event streaming enabled")
                
            return True
            
        except Exception as e:
            self.sf.error(f"Failed to initialize Neo4j: {e}")
            self.errorState = True
            return False

    def handleEvent(self, event):
        """Handle incoming SpiderFoot events."""
        if self.errorState:
            return

        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        # Skip self-generated events
        if srcModuleName == "sfp_neo4j_graph":
            return

        # Skip unwanted event types
        if eventName in ['ROOT']:
            return

        self.sf.debug(f"Received event {eventName} from {srcModuleName}")

        # Store event for batch processing
        if self.opts['enable_batch_import']:
            self.scan_events.append(event)

        # Stream event in real-time if enabled
        if self.opts['enable_realtime'] and self.event_streamer:
            # Run async operation in sync context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Create task for running event loop
                    asyncio.create_task(
                        self._handle_realtime_event(event)
                    )
                else:
                    # Run directly if no loop is running
                    loop.run_until_complete(
                        self._handle_realtime_event(event)
                    )
            except Exception as e:
                self.sf.error(f"Real-time streaming failed: {e}")

        # Generate target suggestions if enabled
        if self.opts['suggest_targets'] and eventName in ['DOMAIN_NAME', 'INTERNET_NAME']:
            try:
                loop = asyncio.get_event_loop()
                suggestions = loop.run_until_complete(
                    self._generate_target_suggestions(eventData)
                )
                self._emit_target_suggestions(suggestions)
            except Exception as e:
                self.sf.error(f"Target suggestion failed: {e}")

    async def _handle_realtime_event(self, event):
        """Handle real-time event streaming."""
        try:
            # Initialize Neo4j if needed
            if not self.neo4j_client:
                if not await self._initialize_neo4j():
                    return

            # Find source event
            source_event = None
            if hasattr(event, 'sourceEvent') and event.sourceEvent:
                source_event = event.sourceEvent

            # Queue event for streaming
            await self.event_streamer.queue_event(event, source_event)
            
        except Exception as e:
            self.sf.error(f"Real-time event handling failed: {e}")

    async def _generate_target_suggestions(self, current_target: str) -> List[Dict[str, Any]]:
        """Generate target suggestions based on graph analysis."""
        if not self.neo4j_client:
            if not await self._initialize_neo4j():
                return []

        try:
            # Get suggestions based on algorithm
            algorithm = self.opts['target_suggestion_algorithm']
            limit = self.opts['max_target_suggestions']
            
            suggestions = await self.neo4j_client.suggest_targets(
                target_type='DOMAIN_NAME',
                algorithm=algorithm,
                limit=limit
            )
            
            # Filter out already scanned targets
            new_suggestions = []
            for suggestion in suggestions:
                if not suggestion['scanned'] and suggestion['data'] != current_target:
                    new_suggestions.append(suggestion)
                    
            return new_suggestions[:limit//2]  # Limit to reasonable number
            
        except Exception as e:
            self.sf.error(f"Target suggestion generation failed: {e}")
            return []

    def _emit_target_suggestions(self, suggestions: List[Dict[str, Any]]):
        """Emit target suggestions as new events."""
        for suggestion in suggestions:
            target_data = suggestion['data']
            score = suggestion['score']
            
            # Create event for suggested target
            evt = SpiderFootEvent(
                "TARGET_WEB_CONTENT", 
                target_data,
                self.__name__,
                None  # No source event for suggestions
            )
            
            # Add metadata about the suggestion
            evt.confidence = min(100, int(score * 100))
            
            self.notifyListeners(evt)
            self.sf.info(f"Suggested target: {target_data} (score: {score:.4f})")

    def start(self):
        """Called when scan starts."""
        self.sf.info("Neo4j Graph module starting")
        
        # Initialize Neo4j in async context
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._initialize_neo4j())
            loop.close()
        except Exception as e:
            self.sf.error(f"Failed to start Neo4j module: {e}")
            self.errorState = True

    def stop(self):
        """Called when scan stops."""
        self.sf.info("Neo4j Graph module stopping")
        
        # Process any remaining events in batch
        if self.opts['enable_batch_import'] and self.scan_events:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_batch_import())
                loop.close()
            except Exception as e:
                self.sf.error(f"Batch import failed: {e}")

        # Cleanup
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._cleanup())
            loop.close()
        except Exception as e:
            self.sf.error(f"Cleanup failed: {e}")

    async def _process_batch_import(self):
        """Process batch import of collected events."""
        if not self.scan_events:
            return

        try:
            if not self.neo4j_client:
                if not await self._initialize_neo4j():
                    return

            batch_size = self.opts['batch_size']
            total_events = len(self.scan_events)
            
            self.sf.info(f"Starting batch import of {total_events} events")
            
            imported = await self.neo4j_client.import_events_batch(
                self.scan_events, 
                batch_size=batch_size
            )
            
            self.sf.info(f"Batch import completed: {imported}/{total_events} events")
            
        except Exception as e:
            self.sf.error(f"Batch import failed: {e}")

    async def _cleanup(self):
        """Cleanup Neo4j resources."""
        try:
            # Stop event streaming
            if self.event_streamer:
                await self.event_streamer.stop_streaming()
                
            # Close Neo4j connection
            if self.neo4j_client:
                await self.neo4j_client.close()
                
            self.sf.info("Neo4j resources cleaned up")
            
        except Exception as e:
            self.sf.error(f"Cleanup error: {e}")

    def handleAnalysis(self, scanId):
        """Perform post-scan analysis."""
        if self.errorState or not self.opts['enable_graph_algorithms']:
            return

        self.sf.info("Starting Neo4j graph analysis")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_graph_analysis(scanId))
            loop.close()
        except Exception as e:
            self.sf.error(f"Graph analysis failed: {e}")

    async def _run_graph_analysis(self, scanId):
        """Run graph algorithms for analysis."""
        if not self.neo4j_client:
            return

        try:
            # Run PageRank analysis
            self.sf.info("Running PageRank analysis")
            top_nodes = []
            
            async for node_data, score in self.neo4j_client.run_graph_algorithm('pagerank'):
                if len(top_nodes) >= 10:  # Top 10 nodes
                    break
                top_nodes.append((node_data['data'], score))

            # Log top nodes
            for data, score in top_nodes:
                self.sf.info(f"High centrality node: {data} (score: {score:.4f})")

            # Generate analysis summary event
            analysis_summary = {
                'scanId': scanId,
                'algorithm': 'pagerank',
                'topNodes': top_nodes,
                'totalEvents': len(self.scan_events)
            }
            
            evt = SpiderFootEvent(
                "GRAPH_ANALYSIS_SUMMARY",
                str(analysis_summary),
                self.__name__,
                None
            )
            self.notifyListeners(evt)
            
        except Exception as e:
            self.sf.error(f"Graph analysis execution failed: {e}")