class VwdpError(Exception):
    """Base application exception."""


class ExternalApiError(VwdpError):
    """Raised when an external API call fails after retries."""


class ValidationFailedError(VwdpError):
    """Raised when a dataset cannot pass validation."""
