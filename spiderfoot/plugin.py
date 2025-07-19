"""SpiderFoot Plugin Base Class with Type Hints

This module provides the base class for all SpiderFoot plugins with
comprehensive type hints for better code quality and IDE support.
"""

from __future__ import annotations
from contextlib import suppress
from typing import Optional, List, Dict, Any, Union, Tuple, TYPE_CHECKING
import io
import logging
import os
import queue
import sys
import threading
from time import sleep
import traceback

from .threadpool import SpiderFootThreadPool

if TYPE_CHECKING:
    from spiderfoot import SpiderFoot, SpiderFootDb, SpiderFootEvent, SpiderFootTarget

# begin logging overrides
# these are copied from the python logging module
# https://github.com/python/cpython/blob/main/Lib/logging/__init__.py

if hasattr(sys, 'frozen'):  # support for py2exe
    _srcfile = f"logging{os.sep}__init__{__file__[-4:]}"
elif __file__[-4:].lower() in ['.pyc', '.pyo']:
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)


class SpiderFootPluginLogger(logging.Logger):
    """Used only in SpiderFootPlugin to prevent modules
    from having to initialize their own loggers.

    Preserves filename, module, line numbers, etc. from the caller.
    """

    def findCaller(self, stack_info: bool = False, stacklevel: int = 1) -> Tuple[str, int, str, Optional[str]]:
        """Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

        Args:
            stack_info: Include stack trace in log record
            stacklevel: Number of stack frames to skip

        Returns:
            Tuple containing (filename, line number, function name, stack trace)
        """
        f = logging.currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        orig_f = f
        while f and stacklevel > 1:
            f = f.f_back
            stacklevel -= 1
        if not f:
            f = orig_f
        rv = "(unknown file)", 0, "(unknown function)", None
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename in (logging._srcfile, _srcfile):  # This is the only change
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write('Stack (most recent call last):\n')
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == '\n':
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv  # noqa R504

# end of logging overrides


class SpiderFootPlugin:
    """SpiderFootPlugin module object

    Attributes:
        _stopScanning: Will be set to True by the controller if the user aborts scanning
        _listenerModules: Modules that will be notified when this module produces events
        _currentEvent: Current event being processed
        _currentTarget: Target currently being acted against
        __name__: Name of this module, set at startup time
        __sfdb__: Direct handle to the database - not to be directly used
                  by modules except the sfp__stor_db module.
        __scanId__: ID of the scan the module is running against
        __dataSource__: (Unused) tracking of data sources
        __outputFilter__: If set, events not matching this list are dropped
        _priority: Priority, smaller numbers should run first
        errorState: error state of the module
        socksProxy: SOCKS proxy
        meta: Plugin meta information
        sf: SpiderFoot object
        opts: Configuration options
        optdescs: Option descriptions
        maxThreads: Maximum number of threads
    """

    # Class attributes with type hints
    _stopScanning: bool = False
    _listenerModules: List[SpiderFootPlugin] = []
    _currentEvent: Optional[SpiderFootEvent] = None
    _currentTarget: Optional[SpiderFootTarget] = None
    __name__: str = "module_name_not_set!"
    __sfdb__: Optional[SpiderFootDb] = None
    __scanId__: Optional[str] = None
    __dataSource__: Optional[str] = None
    __outputFilter__: Optional[List[str]] = None
    _priority: int = 1
    meta: Optional[Dict[str, Any]] = None
    errorState: bool = False
    socksProxy: Optional[str] = None
    incomingEventQueue: Optional[queue.Queue[SpiderFootEvent]] = None
    outgoingEventQueue: Optional[queue.Queue[SpiderFootEvent]] = None
    sf: Optional[SpiderFoot] = None
    opts: Dict[str, Any] = {}
    optdescs: Dict[str, str] = {}
    maxThreads: int = 1

    def __init__(self) -> None:
        """Initialize the plugin."""
        # Holds the thread object when module threading is enabled
        self.thread: Optional[threading.Thread] = None
        # logging overrides
        self._log: Optional[SpiderFootPluginLogger] = None
        # Shared thread pool for all modules
        self.sharedThreadPool: Optional[SpiderFootThreadPool] = None
        # Reset listenerModules to avoid sharing between instances
        self._listenerModules = []
    
    def setSharedThreadPool(self, sharedThreadPool: SpiderFootThreadPool) -> None:
        """Set the shared thread pool for async processing.
        
        Args:
            sharedThreadPool: The shared thread pool instance
        """
        self.sharedThreadPool = sharedThreadPool

    @property
    def log(self) -> SpiderFootPluginLogger:
        """Get the logger instance for this plugin.
        
        Returns:
            SpiderFootPluginLogger instance
        """
        if self._log is None:
            logging.setLoggerClass(SpiderFootPluginLogger)  # temporarily set logger class
            self._log = logging.getLogger(f"spiderfoot.{self.__name__}")  # init SpiderFootPluginLogger
            logging.setLoggerClass(logging.Logger)  # reset logger class to default
        return self._log

    def _updateSocket(self, socksProxy: str) -> None:
        """Hack to override module's use of socket, replacing it with
        one that uses the supplied SOCKS server.

        Args:
            socksProxy: SOCKS proxy server address
        """
        self.socksProxy = socksProxy

    def clearListeners(self) -> None:
        """Used to clear any listener relationships, etc. This is needed because
        Python seems to cache local variables even between threads."""
        self._listenerModules = []
        self._stopScanning = False

    def setup(self, sf: SpiderFoot, userOpts: Dict[str, Any] = {}) -> None:
        """Will always be overridden by the implementer.

        Args:
            sf: SpiderFoot object
            userOpts: User-provided options
        """
        pass

    def debug(self, *args: Any, **kwargs: Any) -> None:
        """For logging.
        A wrapper around logging.debug() that adds the scanId to LogRecord

        Args:
            *args: passed through to logging.debug()
            **kwargs: passed through to logging.debug()
        """
        self.log.debug(*args, extra={'scanId': self.__scanId__}, **kwargs)

    def info(self, *args: Any, **kwargs: Any) -> None:
        """For logging.
        A wrapper around logging.info() that adds the scanId to LogRecord

        Args:
            *args: passed through to logging.info()
            **kwargs: passed through to logging.info()
        """
        self.log.info(*args, extra={'scanId': self.__scanId__}, **kwargs)

    def error(self, *args: Any, **kwargs: Any) -> None:
        """For logging.
        A wrapper around logging.error() that adds the scanId to LogRecord

        Args:
            *args: passed through to logging.error()
            **kwargs: passed through to logging.error()
        """
        self.log.error(*args, extra={'scanId': self.__scanId__}, **kwargs)

    def enrichTarget(self, target: str) -> None:
        """Find aliases for a target.

        Note: rarely used in special cases

        Args:
            target: Target to enrich
        """
        pass

    def setTarget(self, target: SpiderFootTarget) -> None:
        """Assigns the current target this module is acting against.

        Args:
            target: Target object

        Raises:
            TypeError: target argument was invalid type
        """
        from spiderfoot import SpiderFootTarget

        if not isinstance(target, SpiderFootTarget):
            raise TypeError(f"target is {type(target)}; expected SpiderFootTarget")

        self._currentTarget = target

    def setDbh(self, dbh: SpiderFootDb) -> None:
        """Used to set the database handle, which is only to be used
        by modules in very rare/exceptional cases (e.g. sfp__stor_db)

        Args:
            dbh: Database handle
        """
        self.__sfdb__ = dbh

    def setScanId(self, scanId: str) -> None:
        """Set the scan ID.

        Args:
            scanId: Scan instance ID

        Raises:
            TypeError: scanId argument was invalid type
        """
        if not isinstance(scanId, str):
            raise TypeError(f"scanId is {type(scanId)}; expected str")

        self.__scanId__ = scanId

    def getScanId(self) -> str:
        """Get the scan ID.

        Returns:
            Scan ID

        Raises:
            TypeError: Module called getScanId() but no scanId is set.
        """
        if not self.__scanId__:
            raise TypeError("Module called getScanId() but no scanId is set.")

        return self.__scanId__

    def getTarget(self) -> SpiderFootTarget:
        """Gets the current target this module is acting against.

        Returns:
            Current target

        Raises:
            TypeError: Module called getTarget() but no target is set.
        """
        if not self._currentTarget:
            raise TypeError("Module called getTarget() but no target is set.")

        return self._currentTarget

    def registerListener(self, listener: SpiderFootPlugin) -> None:
        """Listener modules which will get notified once we have data for them to
        work with.

        Args:
            listener: Listener module
        """
        self._listenerModules.append(listener)

    def setOutputFilter(self, types: List[str]) -> None:
        """Set the output filter for event types.
        
        Args:
            types: List of event types to allow
        """
        self.__outputFilter__ = types

    def tempStorage(self) -> Dict[str, Any]:
        """For future use. Module temporary storage.

        A dictionary used to persist state (in memory) for a module.

        Todo:
            Move all module state to use this, which then would enable a scan to be paused/resumed.

        Note:
            Required for SpiderFoot HX compatibility of modules.

        Returns:
            Module temporary state data
        """
        return {}

    def notifyListeners(self, sfEvent: SpiderFootEvent) -> None:
        """Call the handleEvent() method of every other plug-in listening for
        events from this plug-in. Remember that those plug-ins will be called
        within the same execution context of this thread, not on their own.

        Args:
            sfEvent: Event to notify listeners about

        Raises:
            TypeError: sfEvent argument was invalid type
        """
        from spiderfoot import SpiderFootEvent

        if not isinstance(sfEvent, SpiderFootEvent):
            raise TypeError(f"sfEvent is {type(sfEvent)}; expected SpiderFootEvent")

        eventName = sfEvent.eventType
        eventData = sfEvent.data

        # Be strict about what events to pass on, unless they are
        # the ROOT event or the event type of the target.
        if self.__outputFilter__ and eventName not in ['ROOT', self.getTarget().targetType, *self.__outputFilter__]:
            return

        storeOnly = False  # Under some conditions, only store and don't notify

        if not eventData:
            return

        if self.checkForStop():
            return

        # Look back to ensure the original notification for an element
        # is what's linked to children. For instance, sfp_dns may find
        # xyz.abc.com, and then sfp_ripe obtains some raw data for the
        # same, and then sfp_dns finds xyz.abc.com in there, we should
        # suppress the notification of that to other modules, as the
        # original xyz.abc.com notification from sfp_dns will trigger
        # those modules anyway. This also avoids messy iterations that
        # traverse many many levels.

        # storeOnly is used in this case so that the source to dest
        # relationship is made, but no further events are triggered
        # from dest, as we are already operating on dest's original
        # notification from one of the upstream events.

        prevEvent = sfEvent.sourceEvent
        while prevEvent is not None:
            if (prevEvent.sourceEvent is not None and 
                prevEvent.sourceEvent.eventType == sfEvent.eventType and 
                prevEvent.sourceEvent.data.lower() == eventData.lower()):
                storeOnly = True
                break
            prevEvent = prevEvent.sourceEvent

        # output to queue if applicable
        if self.outgoingEventQueue is not None:
            self.outgoingEventQueue.put(sfEvent)
        # otherwise, call other modules directly
        else:
            self._listenerModules.sort(key=lambda m: m._priority)

            for listener in self._listenerModules:
                if eventName not in listener.watchedEvents() and '*' not in listener.watchedEvents():
                    continue

                if storeOnly and "__stor" not in listener.__module__:
                    continue

                listener._currentEvent = sfEvent

                # Check if we've been asked to stop in the meantime, so that
                # notifications stop triggering module activity.
                if self.checkForStop():
                    return

                try:
                    listener.handleEvent(sfEvent)
                except Exception as e:
                    if self.sf:
                        self.sf.error(f"Module ({listener.__module__}) encountered an error: {e}")
                    # set errorState
                    self.errorState = True
                    # clear incoming queue
                    if self.incomingEventQueue:
                        with suppress(queue.Empty):
                            while True:
                                self.incomingEventQueue.get_nowait()

    def checkForStop(self) -> bool:
        """For modules to use to check for when they should give back control.

        Returns:
            True if scan should stop
        """
        # Stop if module is in error state.
        if self.errorState:
            return True

        # If threading is enabled, check the _stopScanning attribute instead.
        # This is to prevent each thread needing its own sqlite db handle.
        if self.outgoingEventQueue is not None and self.incomingEventQueue is not None:
            return self._stopScanning

        if not self.__scanId__ or not self.__sfdb__:
            return False

        scanstatus = self.__sfdb__.scanInstanceGet(self.__scanId__)

        if not scanstatus:
            return False

        if scanstatus[5] == "ABORT-REQUESTED":
            self._stopScanning = True
            return True

        return False

    @property
    def running(self) -> bool:
        """Indicates whether the module is currently processing data.
        Modules that process data in pools/batches typically override this method.

        Returns:
            True if the module is currently processing data.
        """
        if self.sharedThreadPool:
            return self.sharedThreadPool.countQueuedTasks(f"{self.__name__}_threadWorker") > 0
        return False

    def watchedEvents(self) -> List[str]:
        """What events is this module interested in for input. The format is a list
        of event types that are applied to event types that this module wants to
        be notified of, or * if it wants everything.
        Will usually be overridden by the implementer, unless it is interested
        in all events (default behavior).

        Returns:
            List of events this modules watches
        """
        return ['*']

    def producedEvents(self) -> List[str]:
        """What events this module produces
        This is to support the end user in selecting modules based on events
        produced.

        Returns:
            List of events produced by this module
        """
        return []

    def handleEvent(self, sfEvent: SpiderFootEvent) -> None:
        """Handle events to this module.
        Will usually be overridden by the implementer, unless it doesn't handle any events.

        Args:
            sfEvent: Event to handle
        """
        return

    def asdict(self) -> Dict[str, Any]:
        """Convert the module to a dictionary representation.
        
        Returns:
            Dictionary containing module information
        """
        return {
            'name': self.meta.get('name') if self.meta else None,
            'descr': self.meta.get('summary') if self.meta else None,
            'cats': self.meta.get('categories', []) if self.meta else [],
            'group': self.meta.get('useCases', []) if self.meta else [],
            'labels': self.meta.get('flags', []) if self.meta else [],
            'provides': self.producedEvents(),
            'consumes': self.watchedEvents(),
            'meta': self.meta,
            'opts': self.opts,
            'optdescs': self.optdescs,
        }

    def start(self) -> None:
        """Start the module's thread worker."""
        self.thread = threading.Thread(target=self.threadWorker)
        self.thread.start()

    def finish(self) -> None:
        """Perform final/cleanup functions before module exits
        Note that this function may be called multiple times
        Overridden by the implementer
        """
        return

    def threadWorker(self) -> None:
        """Main thread worker for the module."""
        try:
            # Handle incoming events
            while not self.checkForStop():
                if self.incomingEventQueue:
                    try:
                        sfEvent = self.incomingEventQueue.get(timeout=0.1)
                        # Handle 'FINISHED' signal
                        if sfEvent == 'FINISHED':
                            self.finished()
                            break
                        self.handleEvent(sfEvent)
                    except queue.Empty:
                        sleep(0.01)
                else:
                    break
        except Exception as e:
            import traceback
            if self.sf:
                self.sf.error(f"Exception in module {self.__name__}: {e}")
                self.sf.debug(traceback.format_exc())
            self.errorState = True