class DBError(Exception):
    """Exception raised for tank history database errors"""

    pass


class APIError(Exception):
    """Exception raised for internal errors from Kingspan API"""

    pass
