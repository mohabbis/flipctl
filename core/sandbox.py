"""
Sandboxing utilities for FlipCTL plugin execution.
Provides a framework for isolating plugin execution to enhance security.
"""

import os
import subprocess
import sys
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod


class SandboxError(Exception):
    """Raised when sandboxing fails."""
    pass


class BaseSandbox(ABC):
    """Abstract base class for sandbox implementations."""

    @abstractmethod
    def run(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function within the sandbox.

        Args:
            func: Function to execute
            *args: Positional arguments to function
            **kwargs: Keyword arguments to function

        Returns:
            Result of function execution

        Raises:
            SandboxError: If sandboxing fails
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this sandbox implementation is available on the system.

        Returns:
            True if sandbox can be used, False otherwise
        """
        pass


class NoSandbox(BaseSandbox):
    """No sandbox - runs code directly (default fallback)."""

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function directly without sandboxing."""
        return func(*args, **kwargs)

    def is_available(self) -> bool:
        """Always available."""
        return True


class ProcessIsolationSandbox(BaseSandbox):
    """
    Sandbox using process isolation (separate subprocess).
    Limits what the code can do by running in a restricted environment.
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize process isolation sandbox.

        Args:
            timeout: Maximum execution time in seconds
        """
        self.timeout = timeout

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function in a separate subprocess with restrictions.

        Note: This is a simplified implementation. In production, you would
        need to serialize the function and from and handle complex objects properly.
        """
        # This is a placeholder - real implementation would require
        # serializing the function and its arguments, running in a
        # restricted subprocess, and deserializing the result
        raise NotImplementedError(
            "Process isolation sandbox requires implementation "
            "with proper serialization/deserialization"
        )

    def is_available(self) -> bool:
        """Always available as long as subprocess works."""
        return True


class ResourceLimitedSandbox(BaseSandbox):
    """
    Sandbox that attempts to limit system resources using OS mechanisms.
    Note: This requires root/admin privileges on most systems for full effectiveness.
    """

    def __init__(self,
                 max_memory_mb: int = 100,
                 max_cpu_percent: int = 50,
                 max_processes: int = 10,
                 timeout: int = 30):
        """
        Initialize resource-limited sandbox.

        Args:
            max_memory_mb: Maximum memory usage in MB
            max_cpu_percent: Maximum CPU usage percentage
            max_processes: Maximum number of child processes
            timeout: Maximum execution time in seconds
        """
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.max_processes = max_processes
        self.timeout = timeout

    def _set_resource_limits(self):
        """Set resource limits for the current process (Unix/Linux only)."""
        if sys.platform.startswith('win'):
            # Windows implementation would use Job Objects
            # This is complex and beyond scope of this example
            return

        try:
            import resource

            # Limit memory
            max_bytes = self.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))

            # Limit CPU time (soft limit in seconds)
            # Note: This is CPU time, not wall clock time
            soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
            new_soft = min(self.timeout, hard) if hard != resource.RLIM_INF else self.timeout
            resource.setrlimit(resource.RLIMIT_CPU, (new_soft, hard))

            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (self.max_processes, self.max_processes))

            # Limit file size (optional)
            # resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024*1024, 10*1024*1024))  # 10MB

        except (ImportError, AttributeError, OSError) as e:
            # If we can't set limits, log but continue
            import logging
            logging.warning(f"Could not set resource limits: {e}")

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with resource limits applied.

        Warning: This only limits the current process, not subprocesses
        spawned by the function. For true isolation, use ProcessIsolationSandbox.
        """
        # Apply limits
        original_limits = {}
        try:
            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                import resource
                # Save current limits
                try:
                    original_limits['RLIMIT_AS'] = resource.getrlimit(resource.RLIMIT_AS)
                except (AttributeError, OSError):
                    pass
                try:
                    original_limits['RLIMIT_CPU'] = resource.getrlimit(resource.RLIMIT_CPU)
                except (AttributeError, OSError):
                    pass
                try:
                    original_limits['RLIMIT_NPROC'] = resource.getrlimit(resource.RLIMIT_NPROC)
                except (AttributeError, OSError):
                    pass

                # Set new limits
                self._set_resource_limits()

            # Execute the function
            return func(*args, **kwargs)

        finally:
            # Restore original limits (best effort)
            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                try:
                    import resource
                    for resource_type, (soft, hard) in original_limits.items():
                        if hasattr(resource, resource_type):
                            try:
                                resource.setrlimit(getattr(resource, resource_type), (soft, hard))
                            except (OSError, ValueError):
                                pass  # Ignore errors on restore
                except ImportError:
                    pass

    def is_available(self) -> bool:
        """Check if resource limiting is available."""
        if sys.platform.startswith('win'):
            # Windows job objects are complex; return False for now
            return False
        try:
            import resource
            return True
        except ImportError:
            return False


class SandboxManager:
    """Manages selection and use of sandbox implementations."""

    def __init__(self):
        self.sandboxes: List[BaseSandbox] = []
        self._available_sandbox: Optional[BaseSandbox] = None
        self._initialize()

    def _initialize(self):
        """Initialize available sandboxes and select the best one."""
        # Define sandbox preference order (most secure to least)
        sandbox_classes = [
            # ProcessIsolationSandbox,  # Would be best but needs implementation
            ResourceLimitedSandbox,
            NoSandbox  # Always last resort
        ]

        for sandbox_class in sandbox_classes:
            try:
                sandbox = sandbox_class()
                if sandbox.is_available():
                    self.sandboxes.append(sandbox)
                    # Use the first available sandbox (most preferred)
                    if self._available_sandbox is None:
                        self._available_sandbox = sandbox
            except Exception as e:
                # Skip sandboxes that fail to initialize
                import logging
                logging.debug(f"Skipping sandbox {sandbox_class.__name__}: {e}")

        if not self._available_sandbox:
            # Fallback to no sandbox
            self._available_sandbox = NoSandbox()
            self.sandboxes.append(self._available_sandbox)

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function using the best available sandbox.

        Args:
            func: Function to execute
            *args: Positional arguments to function
            **kwargs: Keyword arguments to function

        Returns:
            Result of function execution
        """
        if self._available_sandbox is None:
            self._available_sandbox = NoSandbox()  # Final fallback

        return self._available_sandbox.run(func, *args, **kwargs)

    def get_sandbox_info(self) -> Dict[str, Any]:
        """
        Get information about available sandboxes.

        Returns:
            Dictionary with sandbox information
        """
        return {
            "selected_sandbox": self._available_sandbox.__class__.__name__ if self._available_sandbox else None,
            "available_sandboxes": [s.__class__.__name__ for s in self.sandboxes],
            "is_sandboxed": self._available_sandbox.__class__.__name__ != "NoSandbox"
        }


# Global sandbox manager instance
sandbox_manager = SandboxManager()


def sandboxed(func: Callable) -> Callable:
    """
    Decorator to execute a function in a sandbox.

    Usage:
        @sandboxed
        def my_function(arg1, arg2):
            return arg1 + arg2
    """
    def wrapper(*args, **kwargs):
        return sandbox_manager.execute(func, *args, **kwargs)
    return wrapper


def get_sandbox_manager() -> SandboxManager:
    """Get the global sandbox manager instance."""
    return sandbox_manager