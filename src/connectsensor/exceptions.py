class KingspanDBError(Exception):
    """Exception raised for tank history database errors."""


class KingspanAPIError(Exception):
    """Base class for exceptions raised for internal errors from Kingspan API."""


class KingspanInvalidCredentials(KingspanAPIError):
    """Username and/or password were invalid."""


class KingspanTimeoutError(KingspanAPIError):
    """Kingspan API timed out."""
