from __future__ import annotations


class BulkheadInjectionError(Exception):
    """Raised when retrieved content scores at or above the policy threshold
    and the policy mode is ``strict``.

    The message always contains the word "bulkhead".
    """

    def __init__(self, score: float, flags: list[str]):
        self.score = score
        self.flags = flags
        super().__init__(
            f"[bulkhead] Injection risk too high to proceed. "
            f"score={score:.2f} flags={flags}. "
            f"Set policy='warn' to proceed anyway or sanitize the input."
        )


class BulkheadConfigError(Exception):
    """Raised for invalid Bulkhead configuration.

    The message always contains the word "bulkhead".
    """

    def __init__(self, message: str):
        super().__init__(f"[bulkhead] Configuration error: {message}")
