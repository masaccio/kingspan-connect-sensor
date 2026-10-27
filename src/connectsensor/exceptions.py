"""Exceptions possible in the Kingspan API."""

from enum import StrEnum


class KingspanErrorCode(StrEnum):
    """Structured error codes mapping directly to Home Assistant translations."""

    AUTH_FAILED = "invalid_auth"
    CANNOT_CONNECT = "cannot_connect"
    TIMEOUT = "timeout"
    NO_DATA = "no_data"
    UNKNOWN = "unknown"


class KingspanAPIError(Exception):
    """Base class for exceptions raised for internal errors from Kingspan API."""

    def __init__(self, message: str, code: KingspanErrorCode = KingspanErrorCode.UNKNOWN) -> None:
        """Create an exception object with message codes."""
        super().__init__(message)
        self.code = code
        self.message = message


class KingspanInvalidCredentialsError(KingspanAPIError):
    """Username and/or password were invalid."""

    def __init__(self, message: str = "Invalid authentication") -> None:
        """Create an invalid credentials exception object."""
        super().__init__(message, KingspanErrorCode.AUTH_FAILED)


class KingspanTimeoutError(KingspanAPIError):
    """Kingspan API timed out."""

    def __init__(self, message: str) -> None:
        """Create a timeout error exception object."""
        super().__init__(message, KingspanErrorCode.TIMEOUT)


class KingspanNoDataError(KingspanAPIError):
    """Tank reported no level data."""

    def __init__(self, message: str) -> None:
        """Create ano data error exception object."""
        super().__init__(message, KingspanErrorCode.NO_DATA)


class KingspanDBError(Exception):
    """Exception raised for tank history database errors."""
