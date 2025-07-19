"""Asynchronous Event Queue System for SpiderFoot

High-performance event processing pipeline with priority queues,
load balancing, and backpressure management.
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Optional, List, Dict, Any, Callable, Union, AsyncGenerator, Set
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict, deque
import logging
from contextlib import asynccontextmanager
import weakref

from spiderfoot import SpiderFootEvent


class EventPriority(IntEnum):
    """Event priority levels (lower number = higher priority)."""
    CRITICAL = 0    # Critical events that must be processed immediately
    HIGH = 1        # High priority events (e.g., new domains found)
    NORMAL = 2      # Normal priority events (default)
    LOW = 3         # Low priority events (e.g., additional metadata)
    BACKGROUND = 4  # Background processing events


class QueueStatus(Enum):
    """Event queue status."""
    RUNNING = "running"
    PAUSED = "paused"
    DRAINING = "draining"  # No new events, processing existing
    STOPPED = "stopped"


@dataclass
class QueuedEvent:
    """Event wrapper for queue processing."""
    event: SpiderFootEvent
    priority: EventPriority = EventPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    retries: int = 0
    max_retries: int = 3
    timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timeout is None:
            # Default timeout based on priority
            if self.priority <= EventPriority.HIGH:
                self.timeout = 60.0
            elif self.priority == EventPriority.NORMAL:
                self.timeout = 30.0
            else:
                self.timeout = 15.0
    
    @property
    def age(self) -> float:
        """Get event age in seconds."""
        return time.time() - self.created_at
    
    @property
    def is_expired(self) -> bool:
        """Check if event has expired."""
        return self.timeout and self.age > self.timeout
    
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.retries < self.max_retries


class AsyncEventQueue:
    """High-performance async event queue with priority processing.
    
    Features:
        - Priority-based event processing
        - Backpressure management
        - Dead letter queue for failed events
        - Event batching and streaming
        - Load balancing across workers
        - Circuit breaker for failing handlers
        - Metrics and monitoring
    """
    
    def __init__(self,
                 max_size: int = 10000,
                 max_workers: int = 10,
                 batch_size: int = 100,
                 drain_timeout: float = 30.0,
                 enable_dlq: bool = True) -> None:
        """Initialize async event queue.
        
        Args:
            max_size: Maximum queue size (for backpressure)
            max_workers: Maximum number of worker tasks
            batch_size: Batch size for bulk processing
            drain_timeout: Timeout when draining queue
            enable_dlq: Enable dead letter queue for failed events
        """
        self.max_size = max_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.drain_timeout = drain_timeout
        self.enable_dlq = enable_dlq
        
        # Priority queues for different event priorities
        self._queues: Dict[EventPriority, asyncio.Queue] = {
            priority: asyncio.Queue(maxsize=max_size // len(EventPriority))
            for priority in EventPriority
        }
        
        # Dead letter queue for failed events
        self._dlq: deque = deque(maxlen=1000)
        
        # Worker management
        self._workers: Set[asyncio.Task] = set()
        self._worker_semaphore = asyncio.Semaphore(max_workers)
        
        # Event handlers registry
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._handler_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        
        # Queue status and control
        self._status = QueueStatus.STOPPED
        self._shutdown_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Initially not paused
        
        # Statistics
        self.stats = defaultdict(int)
        self._start_time = time.time()
        
        # Circuit breaker for handlers
        self._circuit_breakers: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'failures': 0,
                'last_failure': 0,
                'state': 'closed',  # closed, open, half-open
                'failure_threshold': 5,
                'timeout': 60.0
            }
        )
        
        self.logger = logging.getLogger(f"spiderfoot.{self.__class__.__name__}")
        
    async def __aenter__(self) -> AsyncEventQueue:
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
        
    async def start(self) -> None:
        """Start the event queue processing."""
        if self._status != QueueStatus.STOPPED:
            return
            
        self._status = QueueStatus.RUNNING
        self._shutdown_event.clear()
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self._workers.add(worker)
            worker.add_done_callback(self._workers.discard)
            
        self.logger.info(f"Event queue started with {self.max_workers} workers")
        
    async def stop(self, timeout: Optional[float] = None) -> None:
        """Stop the event queue processing.
        
        Args:
            timeout: Timeout for graceful shutdown
        """
        if self._status == QueueStatus.STOPPED:
            return
            
        self.logger.info("Stopping event queue...")
        
        # Set status to draining
        self._status = QueueStatus.DRAINING
        
        # Wait for queues to drain or timeout
        drain_timeout = timeout or self.drain_timeout
        try:
            await asyncio.wait_for(self._wait_for_empty_queues(), timeout=drain_timeout)
        except asyncio.TimeoutError:
            self.logger.warning("Queue drain timeout, forcing shutdown")
            
        # Signal shutdown and wait for workers
        self._status = QueueStatus.STOPPED
        self._shutdown_event.set()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            
        self.logger.info("Event queue stopped")
        
    async def pause(self) -> None:
        """Pause event processing."""
        self._pause_event.clear()
        self._status = QueueStatus.PAUSED
        self.logger.info("Event queue paused")
        
    async def resume(self) -> None:
        """Resume event processing."""
        self._pause_event.set()
        if self._status == QueueStatus.PAUSED:
            self._status = QueueStatus.RUNNING
        self.logger.info("Event queue resumed")
        
    def register_handler(self, 
                        event_type: str, 
                        handler: Callable[[SpiderFootEvent], Any],
                        priority: int = 0) -> None:
        """Register an event handler.
        
        Args:
            event_type: Type of events to handle
            handler: Async handler function
            priority: Handler priority (lower = higher priority)
        """
        # Insert handler in priority order
        handlers = self._handlers[event_type]
        inserted = False
        
        for i, (existing_handler, existing_priority) in enumerate(handlers):
            if priority < existing_priority:
                handlers.insert(i, (handler, priority))
                inserted = True
                break
                
        if not inserted:
            handlers.append((handler, priority))
            
        self.logger.info(f"Registered handler for {event_type} with priority {priority}")
        
    def unregister_handler(self, event_type: str, handler: Callable) -> None:
        """Unregister an event handler."""
        handlers = self._handlers[event_type]
        self._handlers[event_type] = [
            (h, p) for h, p in handlers if h != handler
        ]
        
    async def put(self, 
                  event: SpiderFootEvent,
                  priority: EventPriority = EventPriority.NORMAL,
                  **kwargs) -> None:
        """Add event to queue.
        
        Args:
            event: SpiderFoot event to queue
            priority: Event priority
            **kwargs: Additional metadata for queued event
        """
        if self._status == QueueStatus.STOPPED:
            raise RuntimeError("Queue is stopped")
            
        # Check for backpressure
        queue = self._queues[priority]
        if queue.qsize() >= queue.maxsize:
            self.stats['backpressure_events'] += 1
            
            # For critical events, make room by dropping low priority events
            if priority <= EventPriority.HIGH:
                await self._make_room_for_priority(priority)
            else:
                raise asyncio.QueueFull("Event queue is full")
                
        queued_event = QueuedEvent(event=event, priority=priority, metadata=kwargs)
        await queue.put(queued_event)
        
        self.stats['events_queued'] += 1
        self.stats[f'events_queued_{priority.name.lower()}'] += 1
        
    async def _make_room_for_priority(self, priority: EventPriority) -> None:
        """Make room for high priority events by dropping low priority ones."""
        for drop_priority in reversed(EventPriority):
            if drop_priority <= priority:
                continue
                
            queue = self._queues[drop_priority]
            if not queue.empty():
                try:
                    dropped_event = queue.get_nowait()
                    self.stats['events_dropped'] += 1
                    self.logger.warning(f"Dropped {drop_priority.name} event for {priority.name}")
                    return
                except asyncio.QueueEmpty:
                    continue
                    
    async def _worker_loop(self, worker_id: str) -> None:
        """Main worker loop for processing events."""
        self.logger.debug(f"Worker {worker_id} started")
        
        while self._status != QueueStatus.STOPPED:
            try:
                # Wait if paused
                await self._pause_event.wait()
                
                # Get next event from highest priority queue
                event = await self._get_next_event()
                if event is None:
                    # No events available, short sleep
                    await asyncio.sleep(0.01)
                    continue
                    
                # Process the event
                async with self._worker_semaphore:
                    await self._process_event(event, worker_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
                
        self.logger.debug(f"Worker {worker_id} stopped")
        
    async def _get_next_event(self) -> Optional[QueuedEvent]:
        """Get next event from priority queues."""
        # Check queues in priority order
        for priority in EventPriority:
            queue = self._queues[priority]
            try:
                return queue.get_nowait()
            except asyncio.QueueEmpty:
                continue
                
        # If no events immediately available, wait on highest priority queue
        try:
            return await asyncio.wait_for(
                self._queues[EventPriority.CRITICAL].get(),
                timeout=0.1
            )
        except asyncio.TimeoutError:
            return None
            
    async def _process_event(self, queued_event: QueuedEvent, worker_id: str) -> None:
        """Process a single event."""
        event = queued_event.event
        event_type = event.eventType
        
        # Check if event has expired
        if queued_event.is_expired:
            self.stats['events_expired'] += 1
            self.logger.warning(f"Event {event_type} expired after {queued_event.age:.1f}s")
            return
            
        # Get handlers for this event type
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            self.stats['events_no_handler'] += 1
            return
            
        # Process with each handler
        for handler, priority in handlers:
            handler_name = f"{handler.__module__}.{handler.__name__}"
            
            # Check circuit breaker
            if not self._check_circuit_breaker(handler_name):
                continue
                
            try:
                start_time = time.time()
                
                # Execute handler with timeout
                if asyncio.iscoroutinefunction(handler):
                    await asyncio.wait_for(
                        handler(event),
                        timeout=queued_event.timeout
                    )
                else:
                    # Run sync handler in thread pool
                    await asyncio.get_event_loop().run_in_executor(
                        None, handler, event
                    )
                    
                # Record success
                duration = time.time() - start_time
                self._record_handler_success(handler_name, duration)
                
            except Exception as e:
                self._record_handler_failure(handler_name, e)
                
                # Retry logic
                if queued_event.can_retry():
                    queued_event.retries += 1
                    await self._retry_event(queued_event)
                elif self.enable_dlq:
                    self._add_to_dlq(queued_event, str(e))
                    
        self.stats['events_processed'] += 1
        
    def _check_circuit_breaker(self, handler_name: str) -> bool:
        """Check circuit breaker state for handler."""
        breaker = self._circuit_breakers[handler_name]
        current_time = time.time()
        
        if breaker['state'] == 'open':
            # Check if timeout has passed
            if current_time - breaker['last_failure'] > breaker['timeout']:
                breaker['state'] = 'half-open'
                self.logger.info(f"Circuit breaker {handler_name} entering half-open state")
            else:
                return False
                
        return True
        
    def _record_handler_success(self, handler_name: str, duration: float) -> None:
        """Record successful handler execution."""
        stats = self._handler_stats[handler_name]
        stats['successes'] += 1
        stats['total_duration'] += duration
        stats['last_success'] = time.time()
        
        # Reset circuit breaker on success
        breaker = self._circuit_breakers[handler_name]
        if breaker['state'] in ['open', 'half-open']:
            breaker['state'] = 'closed'
            breaker['failures'] = 0
            self.logger.info(f"Circuit breaker {handler_name} closed")
            
    def _record_handler_failure(self, handler_name: str, error: Exception) -> None:
        """Record handler failure."""
        stats = self._handler_stats[handler_name]
        stats['failures'] += 1
        stats['last_failure'] = time.time()
        
        # Update circuit breaker
        breaker = self._circuit_breakers[handler_name]
        breaker['failures'] += 1
        breaker['last_failure'] = time.time()
        
        if breaker['failures'] >= breaker['failure_threshold']:
            breaker['state'] = 'open'
            self.logger.warning(f"Circuit breaker {handler_name} opened after {breaker['failures']} failures")
            
        self.logger.error(f"Handler {handler_name} failed: {error}")
        
    async def _retry_event(self, queued_event: QueuedEvent) -> None:
        """Retry failed event."""
        # Exponential backoff
        delay = min(2 ** queued_event.retries, 60)
        await asyncio.sleep(delay)
        
        # Re-queue with lower priority
        retry_priority = min(queued_event.priority + 1, EventPriority.BACKGROUND)
        await self._queues[retry_priority].put(queued_event)
        
        self.stats['events_retried'] += 1
        
    def _add_to_dlq(self, queued_event: QueuedEvent, error: str) -> None:
        """Add failed event to dead letter queue."""
        dlq_entry = {
            'event': {
                'type': queued_event.event.eventType,
                'data': queued_event.event.data,
                'module': queued_event.event.module
            },
            'priority': queued_event.priority.name,
            'retries': queued_event.retries,
            'error': error,
            'failed_at': time.time()
        }
        
        self._dlq.append(dlq_entry)
        self.stats['events_dlq'] += 1
        
    async def _wait_for_empty_queues(self) -> None:
        """Wait for all queues to be empty."""
        while True:
            total_size = sum(queue.qsize() for queue in self._queues.values())
            if total_size == 0:
                break
            await asyncio.sleep(0.1)
            
    async def get_batch(self, 
                       size: Optional[int] = None,
                       timeout: float = 1.0) -> List[QueuedEvent]:
        """Get a batch of events for bulk processing.
        
        Args:
            size: Batch size (defaults to queue batch_size)
            timeout: Timeout for batch collection
            
        Returns:
            List of queued events
        """
        batch_size = size or self.batch_size
        batch = []
        deadline = time.time() + timeout
        
        while len(batch) < batch_size and time.time() < deadline:
            event = await self._get_next_event()
            if event is None:
                break
            batch.append(event)
            
        return batch
        
    async def stream_events(self, 
                           event_types: Optional[List[str]] = None,
                           priorities: Optional[List[EventPriority]] = None) -> AsyncGenerator[QueuedEvent, None]:
        """Stream events as they arrive.
        
        Args:
            event_types: Filter by event types
            priorities: Filter by priorities
            
        Yields:
            Queued events matching filters
        """
        while self._status != QueueStatus.STOPPED:
            event = await self._get_next_event()
            if event is None:
                await asyncio.sleep(0.01)
                continue
                
            # Apply filters
            if event_types and event.event.eventType not in event_types:
                # Re-queue if doesn't match filter
                await self._queues[event.priority].put(event)
                continue
                
            if priorities and event.priority not in priorities:
                # Re-queue if doesn't match filter
                await self._queues[event.priority].put(event)
                continue
                
            yield event
            
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        queue_sizes = {
            priority.name.lower(): queue.qsize() 
            for priority, queue in self._queues.items()
        }
        
        handler_stats = {}
        for handler_name, stats in self._handler_stats.items():
            handler_stats[handler_name] = dict(stats)
            # Calculate average duration
            if stats['successes'] > 0:
                handler_stats[handler_name]['avg_duration'] = \
                    stats['total_duration'] / stats['successes']
                    
        circuit_breaker_stats = {}
        for handler_name, breaker in self._circuit_breakers.items():
            circuit_breaker_stats[handler_name] = {
                'state': breaker['state'],
                'failures': breaker['failures']
            }
            
        return {
            'status': self._status.value,
            'uptime': time.time() - self._start_time,
            'queue_sizes': queue_sizes,
            'total_queued': sum(queue_sizes.values()),
            'dlq_size': len(self._dlq),
            'active_workers': len(self._workers),
            'handler_stats': handler_stats,
            'circuit_breakers': circuit_breaker_stats,
            'processing_stats': dict(self.stats)
        }
        
    def get_dlq_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events from dead letter queue."""
        return list(self._dlq)[-limit:]
        
    def clear_dlq(self) -> int:
        """Clear dead letter queue."""
        size = len(self._dlq)
        self._dlq.clear()
        return size


class EventBus:
    """Global event bus for managing multiple event queues."""
    
    def __init__(self):
        self.queues: Dict[str, AsyncEventQueue] = {}
        self.default_queue = "default"
        
    async def create_queue(self, 
                          name: str, 
                          **kwargs) -> AsyncEventQueue:
        """Create a new event queue."""
        if name in self.queues:
            raise ValueError(f"Queue {name} already exists")
            
        queue = AsyncEventQueue(**kwargs)
        await queue.start()
        self.queues[name] = queue
        return queue
        
    def get_queue(self, name: str = None) -> AsyncEventQueue:
        """Get an event queue by name."""
        queue_name = name or self.default_queue
        if queue_name not in self.queues:
            raise ValueError(f"Queue {queue_name} does not exist")
        return self.queues[queue_name]
        
    async def publish(self, 
                     event: SpiderFootEvent,
                     queue_name: str = None,
                     **kwargs) -> None:
        """Publish event to a queue."""
        queue = self.get_queue(queue_name)
        await queue.put(event, **kwargs)
        
    async def close_all(self) -> None:
        """Close all event queues."""
        for queue in self.queues.values():
            await queue.stop()
        self.queues.clear()


# Global event bus instance
event_bus = EventBus()