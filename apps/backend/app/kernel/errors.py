from __future__ import annotations


class KernelExecutionCancelledError(RuntimeError):
    """Raised when a delegated execution is cooperatively cancelled."""
