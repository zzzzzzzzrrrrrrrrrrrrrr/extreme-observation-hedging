"""Errors at the provider boundary; messages never include query or credential values."""


class ConfigurationError(ValueError):
    """Missing or invalid connection configuration."""


class UnsupportedOperationError(ValueError):
    """An operation is not exposed by this adapter."""


class DataAccessError(RuntimeError):
    """A provider operation failed.

    ``original_error`` is retained for deliberate debugging. Its message may
    contain sensitive provider details, so it is not included in this error.
    """

    def __init__(self, provider, operation, original_error):
        self.provider = provider
        self.operation = operation
        self.original_error = original_error
        super().__init__(
            f"{provider}: {operation} failed ({type(original_error).__name__})."
        )
