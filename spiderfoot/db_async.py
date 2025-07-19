"""Asynchronous Database Operations for SpiderFoot

High-performance async database operations with connection pooling,
batch processing, and optimized queries.
"""

from __future__ import annotations
import asyncio
import sqlite3
import aiosqlite
import json
import time
from typing import Optional, List, Dict, Any, Union, Tuple, AsyncGenerator
from pathlib import Path
from contextlib import asynccontextmanager
import logging
from collections import defaultdict

from spiderfoot import SpiderFootEvent


class AsyncSpiderFootDb:
    """Asynchronous SpiderFoot database operations.
    
    Features:
        - Connection pooling for better performance
        - Async context managers for transactions
        - Batch insert/update operations
        - Streaming query results for large datasets
        - Optimized queries with prepared statements
        - Event buffering and batch processing
        - Database health monitoring
    """
    
    def __init__(self, 
                 db_path: str,
                 max_connections: int = 10,
                 timeout: float = 30.0,
                 batch_size: int = 100,
                 buffer_timeout: float = 1.0) -> None:
        """Initialize async database operations.
        
        Args:
            db_path: Path to SQLite database file
            max_connections: Maximum concurrent connections
            timeout: Database operation timeout
            batch_size: Default batch size for operations
            buffer_timeout: Time to wait before flushing buffers
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.batch_size = batch_size
        self.buffer_timeout = buffer_timeout
        
        # Connection pool management
        self._connection_pool: List[aiosqlite.Connection] = []
        self._pool_semaphore = asyncio.Semaphore(max_connections)
        self._pool_lock = asyncio.Lock()
        
        # Event buffering for batch processing
        self._event_buffer: List[Tuple[str, SpiderFootEvent]] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = defaultdict(int)
        self.logger = logging.getLogger(f"spiderfoot.{self.__class__.__name__}")
        
        # Prepared statements cache
        self._prepared_statements: Dict[str, str] = {}
        
    async def __aenter__(self) -> AsyncSpiderFootDb:
        """Async context manager entry."""
        await self._initialize_pool()
        self._start_buffer_flush_task()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
        
    async def _initialize_pool(self) -> None:
        """Initialize database connection pool."""
        self.logger.info(f"Initializing database pool with {self.max_connections} connections")
        
        for _ in range(self.max_connections):
            conn = await aiosqlite.connect(
                self.db_path,
                timeout=self.timeout,
                isolation_level=None  # Autocommit mode
            )
            
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")
            await conn.execute("PRAGMA temp_store=memory")
            
            self._connection_pool.append(conn)
            
    @asynccontextmanager
    async def _get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a connection from the pool."""
        async with self._pool_semaphore:
            async with self._pool_lock:
                if not self._connection_pool:
                    raise RuntimeError("No available database connections")
                conn = self._connection_pool.pop()
                
            try:
                yield conn
            finally:
                async with self._pool_lock:
                    self._connection_pool.append(conn)
                    
    def _start_buffer_flush_task(self) -> None:
        """Start the buffer flush background task."""
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._buffer_flush_loop())
            
    async def _buffer_flush_loop(self) -> None:
        """Background task to flush event buffers."""
        while True:
            try:
                await asyncio.sleep(self.buffer_timeout)
                await self._flush_event_buffer()
            except asyncio.CancelledError:
                # Final flush before shutdown
                await self._flush_event_buffer()
                break
            except Exception as e:
                self.logger.error(f"Error in buffer flush loop: {e}")
                
    async def _flush_event_buffer(self) -> None:
        """Flush buffered events to database."""
        async with self._buffer_lock:
            if not self._event_buffer:
                return
                
            buffer_copy = self._event_buffer.copy()
            self._event_buffer.clear()
            
        if buffer_copy:
            await self._batch_insert_events(buffer_copy)
            self.stats['events_flushed'] += len(buffer_copy)
            
    async def _batch_insert_events(self, events: List[Tuple[str, SpiderFootEvent]]) -> None:
        """Batch insert events into database."""
        async with self._get_connection() as conn:
            # Group events by scan instance
            events_by_scan = defaultdict(list)
            for scan_id, event in events:
                events_by_scan[scan_id].append(event)
                
            # Insert events for each scan
            for scan_id, scan_events in events_by_scan.items():
                await self._insert_scan_events(conn, scan_id, scan_events)
                
    async def _insert_scan_events(self, 
                                  conn: aiosqlite.Connection, 
                                  scan_id: str, 
                                  events: List[SpiderFootEvent]) -> None:
        """Insert events for a specific scan."""
        event_data = []
        
        for event in events:
            event_data.append((
                scan_id,
                int(time.time() * 1000),  # timestamp in milliseconds
                event.eventType,
                event.confidence,
                event.visibility,
                event.risk,
                event.module,
                event.data,
                event.sourceEvent.hash if event.sourceEvent else "",
                event.hash,
                json.dumps({
                    'actualSource': getattr(event, 'actualSource', None),
                    'moduleDataSource': getattr(event, 'moduleDataSource', {}),
                }) if hasattr(event, 'actualSource') or hasattr(event, 'moduleDataSource') else "{}"
            ))
            
        # Batch insert with prepared statement
        await conn.executemany("""
            INSERT INTO tbl_scan_results 
            (scan_instance_id, scan_result_utime, scan_result_type, 
             scan_result_confidence, scan_result_visibility, scan_result_risk,
             scan_result_module, scan_result_data, scan_result_source_data,
             scan_result_hash, scan_result_extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, event_data)
        
        await conn.commit()
        self.stats['events_inserted'] += len(events)
        
    async def store_event_async(self, scan_id: str, event: SpiderFootEvent, buffer: bool = True) -> None:
        """Store event asynchronously.
        
        Args:
            scan_id: Scan instance ID
            event: SpiderFoot event to store
            buffer: Whether to buffer the event for batch processing
        """
        if buffer:
            # Add to buffer for batch processing
            async with self._buffer_lock:
                self._event_buffer.append((scan_id, event))
                
                # Flush if buffer is full
                if len(self._event_buffer) >= self.batch_size:
                    buffer_copy = self._event_buffer.copy()
                    self._event_buffer.clear()
                    # Process in background to avoid blocking
                    asyncio.create_task(self._batch_insert_events(buffer_copy))
        else:
            # Immediate insert
            await self._batch_insert_events([(scan_id, event)])
            
    async def get_scan_events_stream(self, 
                                   scan_id: str,
                                   event_types: Optional[List[str]] = None,
                                   chunk_size: int = 1000) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Stream scan events in chunks for large result sets.
        
        Args:
            scan_id: Scan instance ID
            event_types: Filter by event types
            chunk_size: Number of events per chunk
            
        Yields:
            Chunks of event dictionaries
        """
        async with self._get_connection() as conn:
            # Build query
            where_clause = "WHERE scan_instance_id = ?"
            params = [scan_id]
            
            if event_types:
                placeholders = ",".join("?" * len(event_types))
                where_clause += f" AND scan_result_type IN ({placeholders})"
                params.extend(event_types)
                
            query = f"""
                SELECT scan_result_utime, scan_result_type, scan_result_data,
                       scan_result_module, scan_result_source_data, scan_result_hash,
                       scan_result_confidence, scan_result_visibility, scan_result_risk,
                       scan_result_extra
                FROM tbl_scan_results 
                {where_clause}
                ORDER BY scan_result_utime
            """
            
            cursor = await conn.execute(query, params)
            
            while True:
                rows = await cursor.fetchmany(chunk_size)
                if not rows:
                    break
                    
                # Convert rows to dictionaries
                events = []
                for row in rows:
                    event_dict = {
                        'utime': row[0],
                        'type': row[1],
                        'data': row[2],
                        'module': row[3],
                        'source_data': row[4],
                        'hash': row[5],
                        'confidence': row[6],
                        'visibility': row[7],
                        'risk': row[8],
                        'extra': json.loads(row[9]) if row[9] else {}
                    }
                    events.append(event_dict)
                    
                yield events
                self.stats['events_streamed'] += len(events)
                
            await cursor.close()
            
    async def search_events_async(self, 
                                criteria: Dict[str, Any],
                                limit: int = 1000,
                                offset: int = 0) -> List[Dict[str, Any]]:
        """Search events with criteria asynchronously.
        
        Args:
            criteria: Search criteria dictionary
            limit: Maximum number of results
            offset: Results offset for pagination
            
        Returns:
            List of matching event dictionaries
        """
        async with self._get_connection() as conn:
            # Build dynamic query
            where_conditions = []
            params = []
            
            for key, value in criteria.items():
                if key == "scan_id":
                    where_conditions.append("scan_instance_id = ?")
                    params.append(value)
                elif key == "event_type":
                    if isinstance(value, list):
                        placeholders = ",".join("?" * len(value))
                        where_conditions.append(f"scan_result_type IN ({placeholders})")
                        params.extend(value)
                    else:
                        where_conditions.append("scan_result_type = ?")
                        params.append(value)
                elif key == "module":
                    where_conditions.append("scan_result_module = ?")
                    params.append(value)
                elif key == "data_contains":
                    where_conditions.append("scan_result_data LIKE ?")
                    params.append(f"%{value}%")
                elif key == "min_confidence":
                    where_conditions.append("scan_result_confidence >= ?")
                    params.append(value)
                elif key == "since_timestamp":
                    where_conditions.append("scan_result_utime >= ?")
                    params.append(value)
                    
            # Build final query
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
                
            query = f"""
                SELECT scan_instance_id, scan_result_utime, scan_result_type, 
                       scan_result_data, scan_result_module, scan_result_source_data,
                       scan_result_hash, scan_result_confidence, scan_result_visibility,
                       scan_result_risk, scan_result_extra
                FROM tbl_scan_results 
                {where_clause}
                ORDER BY scan_result_utime DESC
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
            
            # Convert to dictionaries
            results = []
            for row in rows:
                result = {
                    'scan_id': row[0],
                    'utime': row[1],
                    'type': row[2],
                    'data': row[3],
                    'module': row[4],
                    'source_data': row[5],
                    'hash': row[6],
                    'confidence': row[7],
                    'visibility': row[8],
                    'risk': row[9],
                    'extra': json.loads(row[10]) if row[10] else {}
                }
                results.append(result)
                
            self.stats['search_queries'] += 1
            return results
            
    async def get_scan_summary_async(self, scan_id: str) -> Dict[str, Any]:
        """Get scan summary statistics asynchronously.
        
        Args:
            scan_id: Scan instance ID
            
        Returns:
            Dictionary with scan statistics
        """
        async with self._get_connection() as conn:
            # Get basic scan info
            scan_cursor = await conn.execute("""
                SELECT scan_name, scan_target, scan_status, scan_start_time, scan_end_time
                FROM tbl_scan_instance 
                WHERE scan_instance_id = ?
            """, (scan_id,))
            
            scan_row = await scan_cursor.fetchone()
            await scan_cursor.close()
            
            if not scan_row:
                return {}
                
            # Get event type counts
            events_cursor = await conn.execute("""
                SELECT scan_result_type, COUNT(*) as count
                FROM tbl_scan_results 
                WHERE scan_instance_id = ?
                GROUP BY scan_result_type
                ORDER BY count DESC
            """, (scan_id,))
            
            event_types = {}
            total_events = 0
            
            async for row in events_cursor:
                event_types[row[0]] = row[1]
                total_events += row[1]
                
            await events_cursor.close()
            
            # Get module statistics
            modules_cursor = await conn.execute("""
                SELECT scan_result_module, COUNT(*) as count
                FROM tbl_scan_results 
                WHERE scan_instance_id = ?
                GROUP BY scan_result_module
                ORDER BY count DESC
            """, (scan_id,))
            
            modules = {}
            async for row in modules_cursor:
                modules[row[0]] = row[1]
                
            await modules_cursor.close()
            
            summary = {
                'scan_name': scan_row[0],
                'scan_target': scan_row[1], 
                'scan_status': scan_row[2],
                'scan_start_time': scan_row[3],
                'scan_end_time': scan_row[4],
                'total_events': total_events,
                'event_types': event_types,
                'modules': modules,
                'duration': scan_row[4] - scan_row[3] if scan_row[4] else None
            }
            
            self.stats['summary_queries'] += 1
            return summary
            
    async def batch_update_events(self, 
                                updates: List[Tuple[str, Dict[str, Any]]]) -> int:
        """Batch update events.
        
        Args:
            updates: List of (event_hash, update_fields) tuples
            
        Returns:
            Number of updated events
        """
        if not updates:
            return 0
            
        async with self._get_connection() as conn:
            updated_count = 0
            
            for event_hash, fields in updates:
                # Build dynamic update query
                set_clauses = []
                params = []
                
                for key, value in fields.items():
                    if key in ['confidence', 'visibility', 'risk']:
                        set_clauses.append(f"scan_result_{key} = ?")
                        params.append(value)
                    elif key == 'extra':
                        set_clauses.append("scan_result_extra = ?")
                        params.append(json.dumps(value))
                        
                if set_clauses:
                    query = f"""
                        UPDATE tbl_scan_results 
                        SET {', '.join(set_clauses)}
                        WHERE scan_result_hash = ?
                    """
                    params.append(event_hash)
                    
                    cursor = await conn.execute(query, params)
                    updated_count += cursor.rowcount
                    await cursor.close()
                    
            await conn.commit()
            self.stats['events_updated'] += updated_count
            return updated_count
            
    async def delete_scan_events(self, scan_id: str, event_types: Optional[List[str]] = None) -> int:
        """Delete scan events asynchronously.
        
        Args:
            scan_id: Scan instance ID
            event_types: Optional list of event types to delete
            
        Returns:
            Number of deleted events
        """
        async with self._get_connection() as conn:
            if event_types:
                placeholders = ",".join("?" * len(event_types))
                query = f"""
                    DELETE FROM tbl_scan_results 
                    WHERE scan_instance_id = ? AND scan_result_type IN ({placeholders})
                """
                params = [scan_id] + event_types
            else:
                query = "DELETE FROM tbl_scan_results WHERE scan_instance_id = ?"
                params = [scan_id]
                
            cursor = await conn.execute(query, params)
            deleted_count = cursor.rowcount
            await cursor.close()
            await conn.commit()
            
            self.stats['events_deleted'] += deleted_count
            return deleted_count
            
    async def optimize_database(self) -> None:
        """Optimize database performance."""
        async with self._get_connection() as conn:
            self.logger.info("Starting database optimization")
            
            # Analyze tables for better query planning
            await conn.execute("ANALYZE")
            
            # Vacuum to reclaim space and defragment
            await conn.execute("VACUUM")
            
            # Update statistics
            await conn.execute("PRAGMA optimize")
            
            self.logger.info("Database optimization completed")
            
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database health and performance statistics."""
        async with self._get_connection() as conn:
            # Database size
            size_cursor = await conn.execute("PRAGMA page_count")
            page_count = (await size_cursor.fetchone())[0]
            await size_cursor.close()
            
            page_size_cursor = await conn.execute("PRAGMA page_size") 
            page_size = (await page_size_cursor.fetchone())[0]
            await page_size_cursor.close()
            
            db_size_mb = (page_count * page_size) / (1024 * 1024)
            
            # Table counts
            tables_cursor = await conn.execute("""
                SELECT name, 
                       (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=t.name) as row_count
                FROM sqlite_master t WHERE type='table' AND name LIKE 'tbl_%'
            """)
            
            table_stats = {}
            async for row in tables_cursor:
                # Get actual row count
                count_cursor = await conn.execute(f"SELECT COUNT(*) FROM {row[0]}")
                count = (await count_cursor.fetchone())[0]
                await count_cursor.close()
                table_stats[row[0]] = count
                
            await tables_cursor.close()
            
            # Cache stats
            cache_cursor = await conn.execute("PRAGMA cache_size")
            cache_size = (await cache_cursor.fetchone())[0]
            await cache_cursor.close()
            
            return {
                'database_size_mb': db_size_mb,
                'page_count': page_count,
                'page_size': page_size,
                'cache_size': cache_size,
                'table_stats': table_stats,
                'connection_pool_size': len(self._connection_pool),
                'operation_stats': dict(self.stats)
            }
            
    async def close(self) -> None:
        """Close database connections and cleanup."""
        # Cancel flush task
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
                
        # Flush remaining events
        await self._flush_event_buffer()
        
        # Close all connections
        async with self._pool_lock:
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()
            
        self.logger.info("Async database connections closed")


class AsyncDatabaseManager:
    """Manager for multiple async database instances."""
    
    def __init__(self):
        self.databases: Dict[str, AsyncSpiderFootDb] = {}
        
    async def get_database(self, 
                          db_path: str, 
                          **kwargs) -> AsyncSpiderFootDb:
        """Get or create async database instance."""
        if db_path not in self.databases:
            db = AsyncSpiderFootDb(db_path, **kwargs)
            await db.__aenter__()
            self.databases[db_path] = db
            
        return self.databases[db_path]
        
    async def close_all(self) -> None:
        """Close all database instances."""
        for db in self.databases.values():
            await db.close()
        self.databases.clear()


# Global database manager instance
_db_manager = AsyncDatabaseManager()