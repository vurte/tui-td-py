"""Custom exceptions for tui-td-py."""


class TUITDError(Exception):
    """Base exception for all tui-td-py errors."""


class TUIConnectionError(TUITDError):
    """Raised when connection to tui-td MCP server fails.

    This covers:
    - Subprocess failed to start (tui-td not installed, command not found)
    - JSON-RPC protocol errors (parse errors, invalid responses)
    - Unexpected subprocess termination
    """


class TUITimeoutError(TUITDError):
    """Raised when a wait_for_* operation exceeds its timeout.

    Attributes:
        operation: The name of the operation that timed out (e.g. "wait_for_text")
        timeout: The timeout value in seconds
    """

    def __init__(self, operation: str, timeout: float) -> None:
        self.operation = operation
        self.timeout = timeout
        super().__init__(f"Timeout after {timeout:.1f}s waiting for: {operation}")


class TUIDriverError(TUITDError):
    """Raised when the driver is in an invalid state.

    Examples:
    - Calling send() before start()
    - Calling start() twice
    - Operating on a closed driver
    """
