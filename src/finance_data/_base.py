"""Small shared lifecycle; provider semantics remain in their adapters."""

from .errors import ConfigurationError, DataAccessError, UnsupportedOperationError


class ManagedAdapter:
    provider = "provider"

    def __init__(self, *, client=None, client_factory=None):
        if client is not None and client_factory is not None:
            raise ValueError("Pass either client or client_factory, not both.")
        self._provided_client = client
        self._client_factory = client_factory
        self._client = None
        self._context_depth = 0

    @property
    def is_open(self):
        return self._client is not None

    @property
    def client(self):
        """The native client. Requires explicit open() or context entry first."""
        if not self.is_open:
            raise RuntimeError(f"{self.provider}: open the adapter before accessing its client.")
        return self._client

    def _invoke(self, operation, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ConfigurationError, UnsupportedOperationError, DataAccessError):
            raise
        except Exception as error:
            raise DataAccessError(self.provider, operation, error) from None

    def open(self):
        if not self.is_open:
            if self._provided_client is not None:
                self._client = self._provided_client
            else:
                factory = self._client_factory or self._create_client
                self._client = self._invoke("open", factory)
                if self._client is None:
                    raise ConfigurationError("A client factory must return a usable client.")
        return self

    def close(self):
        if not self.is_open:
            return
        client, self._client = self._client, None
        if self._provided_client is None:
            self._invoke("close", self._close_client, client)

    def _create_client(self):
        raise NotImplementedError

    def _close_client(self, client):
        close = getattr(client, "close", None)
        if callable(close):
            close()

    def __enter__(self):
        self.open()
        self._context_depth += 1
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._context_depth -= 1
        if self._context_depth == 0:
            try:
                self.close()
            except Exception as close_error:
                if exc is None:
                    raise
                exc.add_note(f"Resource cleanup also failed: {close_error}")
        return False
